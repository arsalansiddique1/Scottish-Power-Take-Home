import csv
import json
from pathlib import Path

from review_agent.artifact_writer import ArtifactWriter
from review_agent.models import Finding


def _sample_findings() -> list[Finding]:
    return [
        Finding(
            rule_id="SECURITY_UNSAFE_EXEC",
            category="security",
            severity="high",
            confidence=0.9,
            file_path="src/example.py",
            line=1,
            title="Unsafe exec",
            description="exec/eval detected",
            suggestion="Avoid eval",
            evidence="eval(user_input)",
            source="static",
        )
    ]


def test_artifact_writer_creates_required_files(tmp_path: Path) -> None:
    writer = ArtifactWriter(output_dir=tmp_path)
    result = writer.write(
        findings=_sample_findings(),
        summary_comment="summary",
        run_metadata={"run_id": "r1", "head_sha": "abc"},
    )

    findings_path = Path(result["findings_jsonl"])
    summary_path = Path(result["summary_json"])
    metrics_path = Path(result["metrics_csv"])

    assert findings_path.exists()
    assert summary_path.exists()
    assert metrics_path.exists()

    findings_lines = findings_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(findings_lines) == 1
    assert json.loads(findings_lines[0])["rule_id"] == "SECURITY_UNSAFE_EXEC"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["total_findings"] == 1
    assert summary["run_metadata"]["run_id"] == "r1"

    rows = list(csv.DictReader(metrics_path.open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["run_id"] == "r1"
    assert rows[0]["high"] == "1"
