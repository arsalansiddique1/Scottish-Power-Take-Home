import json
import logging
import re
from pathlib import Path
from typing import Any, Protocol

import yaml

from review_agent.analyzers.static_analyzer import build_analysis_text
from review_agent.models import ChangedFile, Finding, RuleDefinition

logger = logging.getLogger(__name__)


class ChatClientProtocol(Protocol):
    def chat(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        timeout_seconds: float,
    ) -> str: ...


class LLMReviewer:
    def __init__(
        self,
        client: ChatClientProtocol,
        model_profiles_path: str | Path,
        profile: str = "fast",
        temperature: float = 0.0,
        timeout_seconds: float = 180.0,
        rules: list[RuleDefinition] | None = None,
    ) -> None:
        self._client = client
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds
        self._model = self._load_model(model_profiles_path, profile)
        self._rules = sorted((rules or []), key=lambda rule: rule.id)

    def review_files(
        self,
        changed_files: list[ChangedFile],
        static_findings: list[Finding] | None = None,
    ) -> list[Finding]:
        baseline = list(static_findings or [])
        llm_findings: list[Finding] = []

        for changed_file in sorted(changed_files, key=lambda c: c.file_path):
            if not self._is_llm_reviewable_file(changed_file.file_path):
                continue
            per_file = self._review_with_retry(changed_file)
            llm_findings.extend(per_file)

        merged = baseline + llm_findings
        return self._stable_sort(merged)

    def _review_with_retry(self, changed_file: ChangedFile) -> list[Finding]:
        prompt = self._build_prompt(changed_file)
        attempts = 2
        for _ in range(attempts):
            try:
                raw = self._client.chat(
                    model=self._model,
                    prompt=prompt,
                    temperature=self._temperature,
                    timeout_seconds=self._timeout_seconds,
                )
                return self._parse_response(raw, changed_file.file_path)
            except ValueError:
                continue
            except Exception as exc:
                logger.warning(
                    "llm_review_transport_error file=%s model=%s error=%s",
                    changed_file.file_path,
                    self._model,
                    exc,
                )
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
                    rule_id=self._normalize_rule_id(str(item.get("rule_id", "LLM_SEMANTIC_REVIEW"))),
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
                    docs_ref=str(item.get("docs_ref", "")).strip() or None,
                    reasoning=str(item.get("reasoning", "")).strip() or None,
                    source="llm",
                )
            )

        return findings

    def _build_prompt(self, changed_file: ChangedFile) -> str:
        code_context = build_analysis_text(changed_file)
        if len(code_context) > 6000:
            code_context = code_context[:6000]
        rules_context = self._rules_prompt_context()
        diff_context = self._diff_prompt_context(changed_file.patch)
        return (
            "You are a strict code reviewer. Return JSON only."
            " Output either a JSON array or an object with key 'findings'."
            " Each finding must include: rule_id, category(style|quality|security|best_practice),"
            " severity(low|medium|high|critical), line, title, description, suggestion, evidence, confidence,"
            " docs_ref, reasoning."
            " Only emit findings for provided rules unless you must emit LLM_SEMANTIC_REVIEW."
            "\n\n"
            f"File path: {changed_file.file_path}\n"
            f"File status: {changed_file.status}\n"
            f"Additions: {changed_file.additions} | Deletions: {changed_file.deletions} | Changes: {changed_file.changes}\n"
            "Rules context:\n"
            f"{rules_context}\n\n"
            "Diff chunk context:\n"
            f"{diff_context}\n\n"
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

    def _normalize_rule_id(self, rule_id: str) -> str:
        normalized = rule_id.strip()
        known_rule_ids = {rule.id for rule in self._rules}
        if normalized in known_rule_ids or normalized == "LLM_SEMANTIC_REVIEW":
            return normalized
        return "LLM_SEMANTIC_REVIEW"

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

    def _is_llm_reviewable_file(self, file_path: str) -> bool:
        lowered = file_path.lower()
        return lowered.endswith(
            (
                ".py",
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".java",
                ".go",
                ".rs",
                ".rb",
                ".php",
                ".swift",
                ".kt",
                ".c",
                ".h",
                ".cpp",
                ".hpp",
                ".cs",
            )
        )

    def _rules_prompt_context(self) -> str:
        if not self._rules:
            return "[]"
        payload = [
            {
                "id": rule.id,
                "category": rule.category,
                "severity": rule.severity,
                "description": rule.description,
                "recommendation": rule.recommendation,
                "docs_ref": rule.docs_ref,
                "languages": rule.languages,
            }
            for rule in self._rules
        ]
        return json.dumps(payload, ensure_ascii=True)

    def _diff_prompt_context(self, patch: str) -> str:
        if not patch.strip():
            return "[]"
        hunk_header_re = re.compile(r"^@@\s*-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s*@@")
        chunks: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for raw_line in patch.splitlines():
            header = hunk_header_re.match(raw_line)
            if header:
                if current is not None:
                    chunks.append(current)
                current = {
                    "source_start": int(header.group(1)),
                    "source_count": int(header.group(2) or 1),
                    "target_start": int(header.group(3)),
                    "target_count": int(header.group(4) or 1),
                    "added_lines": [],
                    "removed_lines": [],
                }
                continue
            if current is None:
                continue
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                current["added_lines"].append(raw_line[1:160])
                continue
            if raw_line.startswith("-") and not raw_line.startswith("---"):
                current["removed_lines"].append(raw_line[1:160])
        if current is not None:
            chunks.append(current)
        return json.dumps(chunks[:8], ensure_ascii=True)
