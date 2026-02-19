import hashlib
import hmac
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from review_agent.review_orchestrator import ReviewOrchestrator
from review_agent.settings import get_settings

app = FastAPI(title="Automated PR Reviewer Webhook")
logger = logging.getLogger(__name__)


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
    _append_webhook_log(
        f"accepted delivery_id={delivery_id} repo={repo_full_name} pr={pr_number} action={action}"
    )

    background_tasks.add_task(
        _process_pr_review_task,
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
    }


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
    repo_full_name: str,
    pr_number: int,
    action: str,
    delivery_id: str,
) -> None:
    try:
        _append_webhook_log(
            f"start delivery_id={delivery_id} repo={repo_full_name} pr={pr_number} action={action}"
        )
        settings = get_settings()
        orchestrator = ReviewOrchestrator(settings=settings)
        result = orchestrator.run_pr_review(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            action=action,
            output_dir="artifacts/webhook",
            enable_delegation=True,
            auto_commit_refactors=False,
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
