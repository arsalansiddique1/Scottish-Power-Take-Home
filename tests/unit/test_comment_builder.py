from review_agent.comment_builder import build_line_comments, build_summary_comment
from review_agent.models import Finding


def _findings() -> list[Finding]:
    return [
        Finding(
            rule_id="SECURITY_HARDCODED_SECRET",
            category="security",
            severity="high",
            confidence=0.92,
            file_path="src/a.py",
            line=3,
            title="Potential secret",
            description="Potential hardcoded secret detected.",
            suggestion="Move value to environment variables.",
            evidence="api_key = 'abc'",
            source="static",
        ),
        Finding(
            rule_id="STYLE_LINE_LENGTH",
            category="style",
            severity="low",
            confidence=0.95,
            file_path="src/b.py",
            line=10,
            title="Line length",
            description="Line exceeds configured maximum length.",
            suggestion="Wrap long expression.",
            evidence="x = 'very long line'",
            source="llm",
        ),
    ]


def test_build_line_comments_are_actionable_and_deduplicated() -> None:
    findings = _findings()
    comments = build_line_comments(findings + [findings[0]], run_id="run-1")

    assert len(comments) == 2
    assert comments[0].path == "src/a.py"
    assert "What:" in comments[0].body
    assert "Fix:" in comments[0].body
    assert "Run: `run-1`" in comments[0].body


def test_build_summary_comment_contains_metadata_and_counts() -> None:
    summary = build_summary_comment(
        _findings(),
        run_id="run-xyz",
        head_sha="abc123",
        model_name="qwen2.5-coder:7b",
        config_version="v1",
        prompt_version="p1",
    )

    assert "run_id: `run-xyz`" in summary
    assert "head_sha: `abc123`" in summary
    assert "total_findings: `2`" in summary
    assert "Top Findings" in summary
