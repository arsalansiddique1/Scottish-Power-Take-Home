import ast

from review_agent.models import ChangedFile, VerificationResult


class VerificationAgent:
    def verify(self, changed_files: list[ChangedFile]) -> VerificationResult:
        issues: list[str] = []

        for changed_file in changed_files:
            if changed_file.file_path.endswith(".py"):
                content = changed_file.content
                if not content.strip():
                    issues.append(f"empty_content:{changed_file.file_path}")
                    continue
                try:
                    ast.parse(content)
                except SyntaxError as exc:
                    issues.append(
                        f"syntax_error:{changed_file.file_path}:{exc.lineno}:{exc.msg}"
                    )

        return VerificationResult(passed=not issues, details=issues)
