import json
from pathlib import Path

from review_agent.review_orchestrator import ReviewOrchestrator
from review_agent.settings import Settings


def test_end_to_end_fixture_review(tmp_path: Path) -> None:
    orchestrator = ReviewOrchestrator(settings=Settings())
    result = orchestrator.run_fixture_review(
        payload_path="examples/sample_pr_payload.json",
        patch_path="examples/sample_diff.patch",
        output_dir=tmp_path,
        run_id="e2e-run-001",
        use_live_llm=False,
    )

    assert result["run_id"] == "e2e-run-001"
    assert result["total_findings"] >= 1
    assert result["line_comments"] >= 1

    artifacts = result["artifacts"]
    findings_path = Path(str(artifacts["findings_jsonl"]))
    summary_path = Path(str(artifacts["summary_json"]))
    metrics_path = Path(str(artifacts["metrics_csv"]))

    assert findings_path.exists()
    assert summary_path.exists()
    assert metrics_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["run_metadata"]["run_id"] == "e2e-run-001"
    assert summary["total_findings"] == result["total_findings"]


def test_end_to_end_fixture_review_is_deterministic(tmp_path: Path) -> None:
    orchestrator = ReviewOrchestrator(settings=Settings())

    output_a = tmp_path / "run_a"
    output_b = tmp_path / "run_b"

    result_a = orchestrator.run_fixture_review(
        payload_path="examples/sample_pr_payload.json",
        patch_path="examples/sample_diff.patch",
        output_dir=output_a,
        run_id="stable-run",
        use_live_llm=False,
    )
    result_b = orchestrator.run_fixture_review(
        payload_path="examples/sample_pr_payload.json",
        patch_path="examples/sample_diff.patch",
        output_dir=output_b,
        run_id="stable-run",
        use_live_llm=False,
    )

    assert result_a["total_findings"] == result_b["total_findings"]

    findings_a = Path(str(result_a["artifacts"]["findings_jsonl"])).read_text(encoding="utf-8")
    findings_b = Path(str(result_b["artifacts"]["findings_jsonl"])).read_text(encoding="utf-8")
    assert findings_a == findings_b


def test_end_to_end_fixture_review_with_delegation(tmp_path: Path) -> None:
    orchestrator = ReviewOrchestrator(settings=Settings())
    result = orchestrator.run_fixture_review(
        payload_path="examples/sample_pr_payload.json",
        patch_path="examples/sample_diff.patch",
        output_dir=tmp_path / "delegation",
        run_id="delegate-run",
        use_live_llm=False,
        enable_delegation=True,
    )

    assert result["delegation_status"] in {
        "delegated_verified",
        "delegated_failed_verification",
        "skipped",
    }
    assert isinstance(result["delegation_reasons"], list)
    assert isinstance(result["refactor_actions"], list)
