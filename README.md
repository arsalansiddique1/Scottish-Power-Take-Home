# Automated PR Reviewer

Webhook-driven automated PR reviewer with:
- rule-aware static + LLM analysis
- line-level GitHub PR comments (with suggestion blocks)
- LangGraph delegation (review -> refactor -> verification)
- machine-readable artifacts (`JSONL` / `JSON` / `CSV`)
- optional LangSmith tracing

## Reviewer Quick Setup

### 1. Prerequisites
- Python `3.11` or `3.12`
- Poetry `2.x`
- Ollama running locally (`http://localhost:11434`)
- GitHub Personal Access Token with repo access
- ngrok (or equivalent tunnel) for webhook testing

### 2. Install dependencies
```bash
poetry install
```

### 3. Create `.env`
Use this template:

```env
GITHUB_TOKEN=ghp_xxx
WEBHOOK_SECRET=replace_with_random_secret

LLM_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5-coder:7b
LLM_PROFILE=fast
LLM_TIMEOUT_SECONDS=180

LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=automated-pr-reviewer
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

### 4. Verify local setup
```bash
poetry run review-agent healthcheck
poetry run review-agent run-fixture-review --run-id sample-run --output-dir artifacts/sample
```

## Run Webhook Service

Start the app:
```bash
poetry run uvicorn review_agent.webhook_listener:app --host 0.0.0.0 --port 8000
```

Start ngrok:
```bash
ngrok http 8000
```

Use webhook endpoint:
`https://<ngrok-domain>/webhook/github`

## Configure GitHub Webhook

In repository `Settings -> Webhooks -> Add webhook`:
- Payload URL: `https://<ngrok-domain>/webhook/github`
- Content type: `application/json`
- Secret: same value as `.env` `WEBHOOK_SECRET`
- Events: `Pull requests` (and optionally `Push` for diagnostics)

Expected behavior:
- PR open/update triggers webhook
- Service runs review in background
- Comments + summary posted to PR

## Webhook API

- `POST /webhook/github`
- `GET /webhook/status/{run_id}`
- `GET /webhook/artifacts/{run_id}`

Artifacts are written under:
- `artifacts/webhook/<run_id>/findings.jsonl`
- `artifacts/webhook/<run_id>/summary.json`
- `artifacts/webhook/<run_id>/metrics.csv`

## Baseline Analysis Pipeline

1. Ingest PR metadata, files, patches, full file contents, commit history.
2. Parse reviewable diff lines from patch hunks.
3. Load coding rules from `config/coding_standards.yaml` (7 baseline rules).
4. Run static detectors (`regex`, `AST`, `heuristic`, `line_length`).
5. Run LLM reviewer with rule catalog + diff context + file metadata.
6. Build anchored PR comments and publish to GitHub.
7. Write deterministic artifacts and summary.

## Delegation (Advanced)

When enabled, LangGraph runs:
- `decide_delegation` -> `run_refactor` -> `run_verification`

Delegation thresholds are configured in:
- `config/thresholds.yaml`

Refactor behavior:
- LLM-assisted refactor proposals
- deterministic fallback refactors
- syntax safety checks
- rollback to original content on invalid refactor output

Auto-commit behavior:
- Webhook path can auto-commit verified refactors.
- Self-trigger loop guards are implemented:
- skip if latest commit is already from `chore(refactor-agent):...`
- cap automated refactor commits per PR history

## Optional LangSmith Tracing

Set:
```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_xxx
LANGSMITH_PROJECT=automated-pr-reviewer
```

You should see traces for:
- static analysis
- LLM review
- delegation graph
- publish comments
- artifact writing

## Troubleshooting

- `Webhook signature mismatch`
  - Ensure GitHub webhook secret exactly matches `.env` `WEBHOOK_SECRET`.

- `ModuleNotFoundError: langchain_ollama`
  - Run `poetry install` and start using `poetry run ...`.

- `422 pull_request_review_thread.line could not be resolved`
  - Anchoring fallback is implemented; unresolved comments are skipped instead of failing entire run.

- Webhook accepted but no comments posted
  - Check `artifacts/webhook/webhook.log`
  - Verify `GITHUB_TOKEN` permissions and Ollama availability.
