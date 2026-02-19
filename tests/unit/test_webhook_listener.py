import hashlib
import hmac
import json
import zipfile
from io import BytesIO

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from review_agent.webhook_listener import _RUN_STATE, _verify_signature, app


@pytest.fixture(autouse=True)
def clear_run_state() -> None:
    _RUN_STATE.clear()
    yield
    _RUN_STATE.clear()


def test_verify_signature_accepts_valid_signature() -> None:
    secret = "top-secret"
    payload = b'{"a":1}'
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    _verify_signature(secret=secret, payload=payload, signature_header=f"sha256={digest}")


def test_verify_signature_rejects_invalid_signature() -> None:
    with pytest.raises(HTTPException):
        _verify_signature(secret="x", payload=b"{}", signature_header="sha256=deadbeef")


def test_webhook_status_returns_not_found_for_unknown_run() -> None:
    client = TestClient(app)
    response = client.get("/webhook/status/unknown-run")
    assert response.status_code == 404


def test_webhook_status_returns_run_state() -> None:
    client = TestClient(app)
    _RUN_STATE["run-test"] = {
        "status": "running",
        "delivery_id": "d1",
        "repo": "owner/repo",
        "pr_number": 1,
        "action": "synchronize",
        "error": "",
        "artifacts": {},
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:10+00:00",
    }

    response = client.get("/webhook/status/run-test")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-test"
    assert payload["status"] == "running"


def test_webhook_artifacts_returns_zip_when_ready(tmp_path) -> None:
    client = TestClient(app)

    summary = tmp_path / "summary.json"
    findings = tmp_path / "findings.jsonl"
    metrics = tmp_path / "metrics.csv"
    summary.write_text(json.dumps({"ok": True}), encoding="utf-8")
    findings.write_text('{"rule_id":"X"}\n', encoding="utf-8")
    metrics.write_text("run_id,total_findings\nr1,1\n", encoding="utf-8")

    _RUN_STATE["run-artifacts"] = {
        "status": "success",
        "delivery_id": "d2",
        "repo": "owner/repo",
        "pr_number": 1,
        "action": "synchronize",
        "error": "",
        "artifacts": {
            "summary_json": str(summary),
            "findings_jsonl": str(findings),
            "metrics_csv": str(metrics),
        },
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:10+00:00",
    }

    response = client.get("/webhook/artifacts/run-artifacts")
    assert response.status_code == 200
    with zipfile.ZipFile(BytesIO(response.content), "r") as zip_file:
        names = set(zip_file.namelist())
    assert names == {"summary.json", "findings.jsonl", "metrics.csv"}
