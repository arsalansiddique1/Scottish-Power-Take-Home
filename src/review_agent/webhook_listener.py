import hashlib
import hmac
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile
import io

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from review_agent.github_adapter import GithubAdapter
from review_agent.review_orchestrator import ReviewOrchestrator
from review_agent.settings import get_settings

app = FastAPI(title="Automated PR Reviewer Webhook")
logger = logging.getLogger(__name__)

_RUN_STATE: dict[str, dict[str, Any]] = {}
AUTO_REFACTOR_COMMIT_PREFIX = "chore(refactor-agent):"


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
    x_github_delivery: str = Header(default=""),
) -> dict[str, Any]:
    settings = get_settings()
    payload_bytes = await request.body()
    _verify_signature(
        secret=settings.webhook_secret,
        payload=payload_bytes,
        signature_header=x_hub_signature_256,
    )

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": "unsupported_event"}

    payload = await request.json()
    action = str(payload.get("action", ""))
    if action not in {"opened", "synchronize", "reopened", "ready_for_review"}:
        return {"status": "ignored", "reason": f"action:{action}"}

    repo_full_name = str(payload.get("repository", {}).get("full_name", ""))
    pr_number = int(payload.get("pull_request", {}).get("number", 0))

    if not repo_full_name or not pr_number:
        raise HTTPException(status_code=400, detail="Invalid pull_request payload")

    if not settings.github_token:
        raise HTTPException(status_code=400, detail="Missing GITHUB_TOKEN")

    delivery_id = x_github_delivery or "unknown-delivery"
    run_id = f"run-{uuid4().hex[:12]}"
    _append_webhook_log(
        f"accepted delivery_id={delivery_id} run_id={run_id} repo={repo_full_name} pr={pr_number} action={action}"
    )
    _RUN_STATE[run_id] = {
        "status": "accepted",
        "delivery_id": delivery_id,
        "repo": repo_full_name,
        "pr_number": pr_number,
        "action": action,
        "error": "",
        "artifacts": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    background_tasks.add_task(
        _process_pr_review_task,
        run_id=run_id,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        action=action,
        delivery_id=delivery_id,
    )

    # Respond immediately to avoid GitHub webhook delivery timeouts.
    return {
        "status": "accepted",
        "repo": repo_full_name,
        "pr_number": pr_number,
        "action": action,
        "delivery_id": delivery_id,
        "run_id": run_id,
        "status_url": f"/webhook/status/{run_id}",
        "artifacts_url": f"/webhook/artifacts/{run_id}",
    }


@app.get("/webhook/status/{run_id}")
async def webhook_status(run_id: str) -> dict[str, Any]:
    state = _RUN_STATE.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown run_id")
    return {
        "run_id": run_id,
        "status": state.get("status", "unknown"),
        "delivery_id": state.get("delivery_id", ""),
        "repo": state.get("repo", ""),
        "pr_number": state.get("pr_number", 0),
        "action": state.get("action", ""),
        "error": state.get("error", ""),
        "artifacts": state.get("artifacts", {}),
        "created_at": state.get("created_at", ""),
        "updated_at": state.get("updated_at", ""),
    }


@app.get("/webhook/artifacts/{run_id}")
async def webhook_artifacts(run_id: str) -> StreamingResponse:
    state = _RUN_STATE.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown run_id")
    if state.get("status") != "success":
        raise HTTPException(status_code=409, detail="Artifacts not ready")

    artifacts = state.get("artifacts", {})
    paths = [
        Path(str(artifacts.get("summary_json", ""))),
        Path(str(artifacts.get("findings_jsonl", ""))),
        Path(str(artifacts.get("metrics_csv", ""))),
    ]
    if any(not p.exists() for p in paths):
        raise HTTPException(status_code=404, detail="Artifact files missing")

    buf = io.BytesIO()
    with ZipFile(buf, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for path in paths:
            zip_file.write(path, arcname=path.name)
    buf.seek(0)
    filename = f"pr-review-artifacts-{run_id}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)


def _verify_signature(secret: str, payload: bytes, signature_header: str) -> None:
    if not secret:
        raise HTTPException(status_code=400, detail="Missing WEBHOOK_SECRET")
    if not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing/invalid signature header")

    provided = signature_header.split("=", 1)[1]
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(provided, digest):
        raise HTTPException(status_code=401, detail="Webhook signature mismatch")


def _process_pr_review_task(
    run_id: str,
    repo_full_name: str,
    pr_number: int,
    action: str,
    delivery_id: str,
) -> None:
    try:
        _update_run_state(run_id, status="running")
        _append_webhook_log(
            f"start delivery_id={delivery_id} run_id={run_id} repo={repo_full_name} pr={pr_number} action={action}"
        )
        settings = get_settings()
        github_adapter = GithubAdapter(token=settings.github_token)
        context = github_adapter.get_pr_context(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            action=action,
        )
        commit_history = github_adapter.get_commit_history(context=context, limit=1)
        if commit_history:
            latest_message = (commit_history[0].message or "").strip().lower()
            if latest_message.startswith(AUTO_REFACTOR_COMMIT_PREFIX):
                _append_webhook_log(
                    "ignored_self_refactor_commit "
                    f"delivery_id={delivery_id} run_id={run_id} "
                    f"repo={repo_full_name} pr={pr_number}"
                )
                _update_run_state(
                    run_id,
                    status="success",
                    error="",
                    artifacts={},
                )
                return
        orchestrator = ReviewOrchestrator(settings=settings)
        result = orchestrator.run_pr_review(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            action=action,
            output_dir=f"artifacts/webhook/{run_id}",
            run_id=run_id,
            enable_delegation=True,
            auto_commit_refactors=True,
        )
        _update_run_state(
            run_id,
            status="success",
            error="",
            artifacts=result.get("artifacts", {}),
        )
        _append_webhook_log(
            f"result delivery_id={delivery_id} run_id={result.get('run_id')} "
            f"findings={result.get('total_findings')} comments={result.get('line_comments')}"
        )
        _append_webhook_log(
            "success "
            f"delivery_id={delivery_id} findings={result.get('total_findings', 0)} "
            f"comments={result.get('line_comments', 0)}"
        )
    except Exception as exc:
        logger.exception("webhook background task failed delivery_id=%s", delivery_id)
        _update_run_state(run_id, status="failed", error=str(exc))
        _append_webhook_log(f"error delivery_id={delivery_id} error={exc}")
        _write_failure_trace(delivery_id)


def _append_webhook_log(message: str) -> None:
    out_dir = Path("artifacts/webhook")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with (out_dir / "webhook.log").open("a", encoding="utf-8") as handle:
        handle.write(f"{ts} {message}\n")


def _write_failure_trace(delivery_id: str) -> None:
    out_dir = Path("artifacts/webhook")
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / f"error_{delivery_id}.log"
    trace_path.write_text(traceback.format_exc(), encoding="utf-8")


def _update_run_state(run_id: str, **updates: Any) -> None:
    if run_id not in _RUN_STATE:
        _RUN_STATE[run_id] = {"created_at": datetime.now(timezone.utc).isoformat()}
    _RUN_STATE[run_id].update(updates)
    _RUN_STATE[run_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
