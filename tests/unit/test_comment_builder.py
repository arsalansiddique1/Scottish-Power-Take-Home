from review_agent.comment_builder import build_line_comments, build_summary_comment
from review_agent.models import ChangedFile, Finding


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


def test_build_line_comments_anchor_to_reviewable_lines_and_skip_unanchorable() -> None:
    findings = [
        Finding(
            rule_id="QUALITY_1",
            category="quality",
            severity="medium",
            confidence=0.9,
            file_path="src/a.py",
            line=21,
            title="Potential issue",
            description="Something might be wrong",
            suggestion="Adjust logic",
            evidence="if x == y:",
            source="llm",
        ),
        Finding(
            rule_id="QUALITY_2",
            category="quality",
            severity="medium",
            confidence=0.9,
            file_path="src/a.py",
            line=200,
            title="Far away issue",
            description="This cannot be mapped to diff",
            suggestion="Investigate",
            evidence="def old():",
            source="llm",
        ),
    ]
    changed_files = [
        ChangedFile(
            file_path="src/a.py",
            status="modified",
            reviewable_lines=[10, 20, 30],
        )
    ]

    comments = build_line_comments(findings, run_id="run-1", changed_files=changed_files)

    assert len(comments) == 1
    assert comments[0].path == "src/a.py"
    assert comments[0].line == 20


def test_build_line_comments_skip_files_without_reviewable_lines() -> None:
    findings = [
        Finding(
            rule_id="STYLE_1",
            category="style",
            severity="low",
            confidence=0.9,
            file_path="deleted.py",
            line=5,
            title="Old style issue",
            description="File is deleted",
            suggestion="N/A",
            evidence="print('x')",
            source="llm",
        )
    ]
    changed_files = [
        ChangedFile(
            file_path="deleted.py",
            status="removed",
            reviewable_lines=[],
        )
    ]

    comments = build_line_comments(findings, run_id="run-1", changed_files=changed_files)

    assert comments == []


def test_build_line_comments_dedupes_equivalent_findings() -> None:
    findings = [
        Finding(
            rule_id="RULE_A",
            category="quality",
            severity="high",
            confidence=0.95,
            file_path="src/a.py",
            line=12,
            title="Use context manager",
            description="File handle may leak",
            suggestion="Use with open(...)",
            evidence="f = open(path)",
            source="static",
        ),
        Finding(
            rule_id="RULE_B",
            category="best_practice",
            severity="high",
            confidence=0.91,
            file_path="src/a.py",
            line=12,
            title="Use context manager.",
            description="File handle may leak.",
            suggestion="Use with open(...)",
            evidence="f = open(path)",
            source="llm",
        ),
    ]
    changed_files = [
        ChangedFile(
            file_path="src/a.py",
            status="modified",
            reviewable_lines=[12],
        )
    ]

    comments = build_line_comments(findings, run_id="run-1", changed_files=changed_files)

    assert len(comments) == 1
