import re

from review_agent.analyzers.static_analyzer import build_analysis_text
from review_agent.models import ChangedFile, RefactorAction


class RefactoringAgent:
    def apply(self, changed_files: list[ChangedFile]) -> tuple[list[ChangedFile], list[RefactorAction]]:
        updated_files: list[ChangedFile] = []
        actions: list[RefactorAction] = []

        for changed_file in changed_files:
            code = build_analysis_text(changed_file)
            transformed = code

            transformed, action1 = self._rename_camel_case_assignments(changed_file.file_path, transformed)
            if action1:
                actions.append(action1)

            transformed, action2 = self._simplify_duplicate_return_branches(
                changed_file.file_path, transformed
            )
            if action2:
                actions.append(action2)

            updated_files.append(
                changed_file.model_copy(update={"content": transformed, "patch": changed_file.patch})
            )

        return updated_files, actions

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
