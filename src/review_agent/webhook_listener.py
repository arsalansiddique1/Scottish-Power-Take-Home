import hashlib
import hmac
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from review_agent.review_orchestrator import ReviewOrchestrator
from review_agent.settings import get_settings

app = FastAPI(title="Automated PR Reviewer Webhook")


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
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

    orchestrator = ReviewOrchestrator(settings=settings)
    result = orchestrator.run_pr_review(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        action=action,
        output_dir="artifacts/webhook",
        use_live_llm=False,
        enable_delegation=True,
        auto_commit_refactors=False,
    )

    return {"status": "processed", "result": result}


def _verify_signature(secret: str, payload: bytes, signature_header: str) -> None:
    if not secret:
        raise HTTPException(status_code=400, detail="Missing WEBHOOK_SECRET")
    if not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing/invalid signature header")

    provided = signature_header.split("=", 1)[1]
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(provided, digest):
        raise HTTPException(status_code=401, detail="Webhook signature mismatch")
