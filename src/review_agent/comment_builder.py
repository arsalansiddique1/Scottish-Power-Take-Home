from collections import Counter

from review_agent.models import Finding, PRLineComment


def build_line_comments(findings: list[Finding], run_id: str) -> list[PRLineComment]:
    comments: list[PRLineComment] = []
    seen: set[tuple[str, int, str]] = set()
    for finding in findings:
        key = (finding.file_path, finding.line, finding.rule_id)
        if key in seen:
            continue
        seen.add(key)
        comments.append(
            PRLineComment(
                path=finding.file_path,
                line=finding.line,
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
