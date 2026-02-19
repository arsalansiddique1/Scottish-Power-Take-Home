import json
import re
from pathlib import Path
from typing import Any

import yaml

from review_agent.analyzers.llm_client import LLMClientProtocol
from review_agent.analyzers.static_analyzer import build_analysis_text
from review_agent.models import ChangedFile, Finding


class LLMReviewer:
    def __init__(
        self,
        client: LLMClientProtocol,
        model_profiles_path: str | Path,
        profile: str = "fast",
        temperature: float = 0.0,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._client = client
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds
        self._model = self._load_model(model_profiles_path, profile)

    def review_files(
        self,
        changed_files: list[ChangedFile],
        static_findings: list[Finding] | None = None,
    ) -> list[Finding]:
        baseline = list(static_findings or [])
        llm_findings: list[Finding] = []

        for changed_file in sorted(changed_files, key=lambda c: c.file_path):
            per_file = self._review_with_retry(changed_file)
            llm_findings.extend(per_file)

        merged = baseline + llm_findings
        return self._stable_sort(merged)

    def _review_with_retry(self, changed_file: ChangedFile) -> list[Finding]:
        prompt = self._build_prompt(changed_file)
        attempts = 2
        for _ in range(attempts):
            raw = self._client.chat(
                model=self._model,
                prompt=prompt,
                temperature=self._temperature,
                timeout_seconds=self._timeout_seconds,
            )
            try:
                return self._parse_response(raw, changed_file.file_path)
            except ValueError:
                continue
        return []

    def _parse_response(self, response_text: str, file_path: str) -> list[Finding]:
        payload = self._extract_json_payload(response_text)

        if isinstance(payload, dict):
            candidate = payload.get("findings", [])
        elif isinstance(payload, list):
            candidate = payload
        else:
            raise ValueError("LLM response is not a list or finding wrapper object")

        findings: list[Finding] = []
        for item in candidate:
            if not isinstance(item, dict):
                continue
            category = self._normalize_category(str(item.get("category", "quality")))
            severity = self._normalize_severity(str(item.get("severity", "medium")))
            confidence = self._clamp_confidence(item.get("confidence", 0.7))
            line = int(item.get("line", 1) or 1)

            findings.append(
                Finding(
                    rule_id=str(item.get("rule_id", "LLM_SEMANTIC_REVIEW")),
                    category=category,
                    severity=severity,
                    confidence=confidence,
                    file_path=file_path,
                    line=line,
                    end_line=int(item.get("end_line")) if item.get("end_line") else None,
                    title=str(item.get("title", "Semantic review finding")),
                    description=str(item.get("description", "Potential improvement found.")),
                    suggestion=str(item.get("suggestion", "Review this change.")),
                    evidence=str(item.get("evidence", "")),
                    source="llm",
                )
            )

        return findings

    def _build_prompt(self, changed_file: ChangedFile) -> str:
        code_context = build_analysis_text(changed_file)
        return (
            "You are a strict code reviewer. Return JSON only."
            " Output either a JSON array or an object with key 'findings'."
            " Each finding must include: rule_id, category(style|quality|security|best_practice),"
            " severity(low|medium|high|critical), line, title, description, suggestion, evidence, confidence."
            "\n\n"
            f"File path: {changed_file.file_path}\n"
            "Changed code:\n"
            f"{code_context}\n"
        )

    def _load_model(self, path: str | Path, profile: str) -> str:
        loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        models: dict[str, Any] = dict(loaded.get("models", {}))
        if profile not in models:
            raise ValueError(f"Unknown model profile: {profile}")
        model = str(models[profile].get("model", "")).strip()
        if not model:
            raise ValueError(f"Empty model in profile: {profile}")
        return model

    def _extract_json_payload(self, text: str) -> Any:
        trimmed = text.strip()
        if not trimmed:
            raise ValueError("Empty response")

        cleaned = self._strip_code_fences(trimmed)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        match = re.search(r"(\{.*\}|\[.*\])", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON payload found")
        return json.loads(match.group(1))

    def _strip_code_fences(self, text: str) -> str:
        value = text
        if value.startswith("```"):
            value = re.sub(r"^```[a-zA-Z0-9_\-]*\n", "", value)
            value = re.sub(r"\n```$", "", value)
        return value.strip()

    def _normalize_category(self, category: str) -> str:
        allowed = {"style", "quality", "security", "best_practice"}
        if category in allowed:
            return category
        return "quality"

    def _normalize_severity(self, severity: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        if severity in allowed:
            return severity
        return "medium"

    def _clamp_confidence(self, confidence: Any) -> float:
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            value = 0.7
        return max(0.0, min(1.0, value))

    def _stable_sort(self, findings: list[Finding]) -> list[Finding]:
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(
            findings,
            key=lambda f: (
                f.file_path,
                severity_order[f.severity],
                f.line,
                f.rule_id,
                f.source,
            ),
        )
