import json
import re
from pathlib import Path
from typing import Any, Protocol

import yaml
from review_agent.analyzers.static_analyzer import build_analysis_text
from review_agent.models import ChangedFile, Finding, RefactorAction


class ChatClientProtocol(Protocol):
    def chat(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        timeout_seconds: float,
    ) -> str: ...


class RefactoringAgent:
    def __init__(
        self,
        client: ChatClientProtocol | None = None,
        model_profiles_path: str | Path = "config/model_profiles.yaml",
        profile: str = "fast",
        temperature: float = 0.0,
        timeout_seconds: float = 180.0,
    ) -> None:
        self._client = client
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds
        self._model = self._load_model(model_profiles_path, profile) if client else ""

    def apply(
        self,
        changed_files: list[ChangedFile],
        findings: list[Finding] | None = None,
    ) -> tuple[list[ChangedFile], list[RefactorAction]]:
        updated_files: list[ChangedFile] = []
        actions: list[RefactorAction] = []
        findings = findings or []
        findings_by_file: dict[str, list[Finding]] = {}
        for finding in findings:
            findings_by_file.setdefault(finding.file_path, []).append(finding)

        for changed_file in changed_files:
            code = build_analysis_text(changed_file)
            transformed = code
            file_actions: list[RefactorAction] = []

            if self._is_refactorable_file(changed_file.file_path):
                llm_transformed, llm_actions = self._apply_llm_refactor(
                    changed_file.file_path,
                    transformed,
                    findings_by_file.get(changed_file.file_path, []),
                )
                if llm_transformed != transformed and llm_actions:
                    transformed = llm_transformed
                    file_actions.extend(llm_actions)

            transformed, action1 = self._rename_camel_case_assignments(changed_file.file_path, transformed)
            if action1:
                file_actions.append(action1)

            transformed, action2 = self._simplify_duplicate_return_branches(
                changed_file.file_path, transformed
            )
            if action2:
                file_actions.append(action2)

            updated_files.append(
                changed_file.model_copy(update={"content": transformed, "patch": changed_file.patch})
            )
            actions.extend(file_actions)

        return updated_files, actions

    def _apply_llm_refactor(
        self,
        file_path: str,
        content: str,
        findings: list[Finding],
    ) -> tuple[str, list[RefactorAction]]:
        if not self._client or not content.strip():
            return content, []
        if not findings:
            return content, []
        prompt = self._build_refactor_prompt(file_path=file_path, content=content, findings=findings)
        try:
            raw = self._client.chat(
                model=self._model,
                prompt=prompt,
                temperature=self._temperature,
                timeout_seconds=self._timeout_seconds,
            )
        except Exception:
            return content, []

        payload = self._extract_json(raw)
        if not isinstance(payload, dict):
            return content, []
        transformed = str(payload.get("transformed_code", "")).strip("\n")
        apply_change = bool(payload.get("apply", False))
        if not apply_change or not transformed or transformed == content:
            return content, []

        actions = self._parse_actions(file_path=file_path, payload=payload)
        if not actions:
            actions = [
                RefactorAction(
                    file_path=file_path,
                    action_type="llm_refactor",
                    description="LLM refactoring update applied.",
                    applied=True,
                )
            ]
        return transformed, actions

    def _build_refactor_prompt(
        self,
        *,
        file_path: str,
        content: str,
        findings: list[Finding],
    ) -> str:
        finding_lines = [
            f"- {f.rule_id} @ line {f.line}: {f.description} | suggestion={f.suggestion}"
            for f in findings[:10]
        ]
        truncated_content = content[:8000]
        return (
            "You are a safe refactoring agent. Return JSON only.\n"
            "Output schema:\n"
            "{\n"
            '  "apply": true|false,\n'
            '  "transformed_code": "full file content after refactor",\n'
            '  "actions": [{"action_type":"...","description":"..."}]\n'
            "}\n"
            "Rules:\n"
            "- Preserve behavior.\n"
            "- Focus on rename variable, simplify conditionals, and extract small helpers when safe.\n"
            "- Do not add unrelated changes.\n"
            "- If uncertain, set apply=false.\n\n"
            f"File: {file_path}\n"
            "Findings:\n"
            f"{chr(10).join(finding_lines)}\n\n"
            "Current code:\n"
            f"{truncated_content}\n"
        )

    def _extract_json(self, text: str) -> Any:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned)
            cleaned = re.sub(r"\n```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if not match:
                return {}
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}

    def _parse_actions(self, file_path: str, payload: dict[str, Any]) -> list[RefactorAction]:
        raw_actions = payload.get("actions", [])
        if not isinstance(raw_actions, list):
            return []
        parsed: list[RefactorAction] = []
        for action in raw_actions:
            if not isinstance(action, dict):
                continue
            parsed.append(
                RefactorAction(
                    file_path=file_path,
                    action_type=str(action.get("action_type", "llm_refactor")),
                    description=str(action.get("description", "LLM refactoring update applied.")),
                    applied=True,
                )
            )
        return parsed

    def _rename_camel_case_assignments(
        self, file_path: str, content: str
    ) -> tuple[str, RefactorAction | None]:
        pattern = re.compile(r"^(\s*)([a-z]+[A-Z][A-Za-z0-9]*)\s*=", re.MULTILINE)
        matches = list(pattern.finditer(content))
        if not matches:
            return content, None

        updated = content
        for match in matches:
            original = match.group(2)
            snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", original).lower()
            updated = re.sub(rf"\b{original}\b", snake, updated)

        action = RefactorAction(
            file_path=file_path,
            action_type="rename_variable",
            description="Converted camelCase variable names to snake_case.",
            applied=True,
        )
        return updated, action

    def _simplify_duplicate_return_branches(
        self, file_path: str, content: str
    ) -> tuple[str, RefactorAction | None]:
        pattern = re.compile(
            r"if\s+([^\n]+):\n\s+return\s+([^\n]+)\n\s+else:\n\s+return\s+\2",
            re.MULTILINE,
        )
        if not pattern.search(content):
            return content, None

        updated = pattern.sub(lambda m: f"# simplified duplicated branch\nreturn {m.group(2)}", content)
        action = RefactorAction(
            file_path=file_path,
            action_type="simplify_conditional",
            description="Collapsed duplicated if/else return branches.",
            applied=True,
        )
        return updated, action

    def _load_model(self, path: str | Path, profile: str) -> str:
        loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        models: dict[str, Any] = dict(loaded.get("models", {}))
        if profile not in models:
            raise ValueError(f"Unknown model profile: {profile}")
        model = str(models[profile].get("model", "")).strip()
        if not model:
            raise ValueError(f"Empty model in profile: {profile}")
        return model

    def _is_refactorable_file(self, file_path: str) -> bool:
        return file_path.endswith((".py", ".js", ".ts", ".tsx", ".java", ".go", ".rs", ".cs"))
