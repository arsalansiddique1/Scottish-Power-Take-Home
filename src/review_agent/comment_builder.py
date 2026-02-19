from collections import Counter
import re

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

        normalized_problem = _issue_fingerprint(finding)
        key = (finding.file_path, line, normalized_problem)
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
                line=line,
                body=_line_comment_body(finding, run_id),
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


def _line_comment_body(finding: Finding, run_id: str) -> str:
    return (
        f"[{finding.severity.upper()}][{finding.category}] `{finding.rule_id}`\n\n"
        f"What: {finding.description}\n"
        f"Why: {finding.title}\n"
        f"Fix: {finding.suggestion}\n"
        f"Evidence: `{finding.evidence}`\n"
        f"Confidence: `{finding.confidence:.2f}`\n"
        f"Run: `{run_id}`"
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
