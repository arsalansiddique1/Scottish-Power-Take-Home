from collections import Counter
import re
from pathlib import Path

from review_agent.models import ChangedFile, Finding, PRLineComment


def build_line_comments(
    findings: list[Finding],
    run_id: str,
    changed_files: list[ChangedFile] | None = None,
    max_comments: int = 15,
    max_comments_per_file: int = 4,
    confidence_threshold: float = 0.65,
) -> list[PRLineComment]:
    reviewable_map = _build_reviewable_line_map(changed_files or [])
    file_line_map = _build_file_line_map(changed_files or [])
    ranked_findings = sorted(
        findings,
        key=lambda f: (_severity_rank(f.severity), -f.confidence, f.file_path, f.line, f.rule_id),
    )

    comments: list[PRLineComment] = []
    seen: set[tuple[str, int, str]] = set()
    per_file_count: dict[str, int] = {}

    for finding in ranked_findings:
        if finding.confidence < confidence_threshold:
            continue

        line = _anchor_line_to_reviewable(finding.file_path, finding.line, reviewable_map)
        if line is None:
            continue
        start_line, end_line = _comment_line_range(finding, line, reviewable_map)
        if start_line is None or end_line is None:
            continue

        normalized_problem = _issue_fingerprint(finding)
        key = (finding.file_path, end_line, normalized_problem)
        if key in seen:
            continue
        if per_file_count.get(finding.file_path, 0) >= max_comments_per_file:
            continue
        if len(comments) >= max_comments:
            break

        seen.add(key)
        per_file_count[finding.file_path] = per_file_count.get(finding.file_path, 0) + 1
        comments.append(
            PRLineComment(
                path=finding.file_path,
                start_line=start_line if start_line != end_line else None,
                line=end_line,
                body=_line_comment_body(
                    finding=finding,
                    run_id=run_id,
                    line_text=_line_text_for_comment(finding, end_line, file_line_map),
                ),
                start_side="RIGHT" if start_line != end_line else None,
            )
        )
    return comments


def build_summary_comment(
    findings: list[Finding],
    *,
    run_id: str,
    head_sha: str,
    model_name: str,
    config_version: str,
    prompt_version: str,
    delegation_status: str = "not-run",
) -> str:
    by_severity = Counter(f.severity for f in findings)
    by_category = Counter(f.category for f in findings)

    total = len(findings)
    top = sorted(
        findings,
        key=lambda f: ({"critical": 0, "high": 1, "medium": 2, "low": 3}[f.severity], f.file_path, f.line),
    )[:3]

    lines = [
        "## Automated Review Summary",
        f"- run_id: `{run_id}`",
        f"- head_sha: `{head_sha}`",
        f"- model: `{model_name}`",
        f"- config_version: `{config_version}`",
        f"- prompt_version: `{prompt_version}`",
        f"- delegation_status: `{delegation_status}`",
        f"- total_findings: `{total}`",
        "- severity_counts: "
        f"critical={by_severity.get('critical', 0)}, "
        f"high={by_severity.get('high', 0)}, "
        f"medium={by_severity.get('medium', 0)}, "
        f"low={by_severity.get('low', 0)}",
        "- category_counts: "
        f"security={by_category.get('security', 0)}, "
        f"quality={by_category.get('quality', 0)}, "
        f"style={by_category.get('style', 0)}, "
        f"best_practice={by_category.get('best_practice', 0)}",
        "",
        "### Top Findings",
    ]

    if not top:
        lines.append("- No actionable findings.")
    else:
        for finding in top:
            lines.append(
                f"- [{finding.severity.upper()}] `{finding.rule_id}` at "
                f"`{finding.file_path}:{finding.line}` - {finding.title}"
            )

    return "\n".join(lines)


def _line_comment_body(finding: Finding, run_id: str, line_text: str) -> str:
    docs_line = f"\nDocs: `{finding.docs_ref}`" if finding.docs_ref else ""
    reasoning_line = f"\nReasoning: {finding.reasoning}" if finding.reasoning else ""
    problematic = (finding.problematic_code or line_text).strip()
    code_block = (
        f"\n\nProblematic code:\n```{_language_from_path(finding.file_path)}\n{problematic}\n```"
        if problematic
        else ""
    )
    suggestion_block = _build_suggestion_block(finding, line_text)

    return (
        f"[{finding.severity.upper()}][{finding.category}] `{finding.rule_id}`\n\n"
        f"What: {finding.description}\n"
        f"Why: {finding.title}\n"
        f"Fix: {finding.suggestion}\n"
        f"Evidence: `{finding.evidence}`\n"
        f"Confidence: `{finding.confidence:.2f}`\n"
        f"Run: `{run_id}`"
        f"{docs_line}"
        f"{reasoning_line}"
        f"{code_block}"
        f"{suggestion_block}"
    )


def _severity_rank(severity: str) -> int:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return order.get(severity, 4)


def _build_reviewable_line_map(changed_files: list[ChangedFile]) -> dict[str, set[int]]:
    line_map: dict[str, set[int]] = {}
    for changed_file in changed_files:
        line_map[changed_file.file_path] = set(changed_file.reviewable_lines)
    return line_map


def _anchor_line_to_reviewable(
    file_path: str,
    line: int,
    reviewable_map: dict[str, set[int]],
) -> int | None:
    if line <= 0:
        return None

    # If we don't have patch metadata for the file, fallback to raw line anchoring.
    if file_path not in reviewable_map:
        return line

    allowed_lines = reviewable_map[file_path]
    if not allowed_lines:
        return None
    if line in allowed_lines:
        return line

    closest = min(allowed_lines, key=lambda candidate: abs(candidate - line))
    if abs(closest - line) <= 2:
        return closest
    return None


def _issue_fingerprint(finding: Finding) -> str:
    parts = [
        _normalize_text(finding.title),
        _normalize_text(finding.description),
        _normalize_text(finding.suggestion),
        _normalize_text(finding.evidence),
    ]
    return "|".join(parts)


def _normalize_text(value: str) -> str:
    lowered = value.lower().strip()
    collapsed = re.sub(r"\s+", " ", lowered)
    return re.sub(r"[^a-z0-9 ]+", "", collapsed)


def _build_file_line_map(changed_files: list[ChangedFile]) -> dict[str, dict[int, str]]:
    mapping: dict[str, dict[int, str]] = {}
    for changed_file in changed_files:
        if not changed_file.content.strip():
            continue
        lines = changed_file.content.splitlines()
        mapping[changed_file.file_path] = {idx: line for idx, line in enumerate(lines, start=1)}
    return mapping


def _line_text_for_comment(
    finding: Finding,
    anchored_line: int,
    file_line_map: dict[str, dict[int, str]],
) -> str:
    per_file = file_line_map.get(finding.file_path, {})
    return per_file.get(anchored_line, finding.evidence or "")


def _language_from_path(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
    }
    return mapping.get(suffix, "")


def _build_suggestion_block(finding: Finding, line_text: str) -> str:
    if finding.replacement_code and finding.replacement_code.strip():
        return f"\n\nSuggested fix:\n```suggestion\n{finding.replacement_code.rstrip()}\n```"

    replacement = _suggested_replacement(finding, line_text)
    if replacement is None:
        replacement = _fallback_replacement(finding, line_text)
    return f"\n\nSuggested fix:\n```suggestion\n{replacement}\n```"


def _suggested_replacement(finding: Finding, line_text: str) -> str | None:
    stripped = line_text.strip()
    if not stripped:
        return None

    if finding.rule_id == "STYLE_NAMING_CONVENTION":
        match = re.search(r"^\s*([a-z]+[A-Z][A-Za-z0-9]*)\s*=", line_text)
        if not match:
            return None
        original = match.group(1)
        snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", original).lower()
        return re.sub(rf"\b{original}\b", snake, line_text)

    if finding.rule_id == "SECURITY_HARDCODED_SECRET":
        assignment_match = re.search(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line_text)
        if not assignment_match:
            return None
        name = assignment_match.group(1)
        env_name = re.sub(r"[^A-Za-z0-9_]", "_", name).upper()
        leading = re.match(r"^\s*", line_text).group(0)
        return f'{leading}{name} = os.getenv("{env_name}")'

    return None


def _comment_line_range(
    finding: Finding,
    anchored_line: int,
    reviewable_map: dict[str, set[int]],
) -> tuple[int | None, int | None]:
    span_lines = _problematic_span_lines(finding)
    start_line = anchored_line
    end_line = anchored_line + span_lines - 1
    if span_lines <= 1:
        return anchored_line, anchored_line

    if not _is_reviewable_range(finding.file_path, start_line, end_line, reviewable_map):
        return anchored_line, anchored_line
    return start_line, end_line


def _problematic_span_lines(finding: Finding) -> int:
    if finding.end_line and finding.end_line >= finding.line:
        return (finding.end_line - finding.line) + 1
    if finding.problematic_code and finding.problematic_code.strip():
        return max(1, len([line for line in finding.problematic_code.splitlines() if line.strip()]))
    return 1


def _is_reviewable_range(
    file_path: str,
    start_line: int,
    end_line: int,
    reviewable_map: dict[str, set[int]],
) -> bool:
    if start_line <= 0 or end_line < start_line:
        return False
    if file_path not in reviewable_map:
        return True
    allowed = reviewable_map[file_path]
    if not allowed:
        return False
    return all(line in allowed for line in range(start_line, end_line + 1))


def _fallback_replacement(finding: Finding, line_text: str) -> str:
    base = line_text.rstrip() if line_text.strip() else (finding.evidence or "TODO")
    note = _shorten(finding.suggestion, limit=80)
    comment_prefix = _comment_prefix_for_path(finding.file_path)
    if comment_prefix:
        return f"{base} {comment_prefix} TODO(review): {note}"
    return f"{base}  TODO(review): {note}"


def _comment_prefix_for_path(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix in {".py", ".rb", ".sh"}:
        return "#"
    if suffix in {".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".c", ".cpp", ".cs"}:
        return "//"
    return ""


def _shorten(value: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", value.strip())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
