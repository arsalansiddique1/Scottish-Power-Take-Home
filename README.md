# Automated PR Reviewer

Automated code review pipeline for GitHub pull requests using:
- static rule-based analysis
- LLM semantic analysis (Ollama)
- actionable review-comment generation
- reproducible artifacts (JSONL/JSON/CSV)
- optional multi-agent delegation/refactor/verification

## Quick Start (Under 5 Minutes)

### 1. Install dependencies
```bash
poetry install
```

### 2. Verify setup
```bash
poetry run review-agent healthcheck
```

### 3. Run baseline review with fixture input (live Ollama)
```bash
poetry run review-agent run-fixture-review --run-id sample-run --output-dir artifacts/sample
```

### 3b. Run with Phase 6 multi-agent delegation enabled
```bash
poetry run review-agent run-fixture-review --run-id sample-delegate --output-dir artifacts/sample-delegate --enable-delegation
```

### 4. Run tests and lint
```bash
poetry run pytest -q
poetry run ruff check .
```

## Live GitHub PR Review

Set required environment variables:
```bash
$env:GITHUB_TOKEN="your_token"         # PowerShell
$env:LLM_BASE_URL="http://localhost:11434"
$env:LLM_MODEL="qwen2.5-coder:14b"
$env:LLM_TIMEOUT_SECONDS="180"
```

Run review against a live PR:
```bash
poetry run review-agent run-pr-review --repo owner/repo --pr-number 123 --action synchronize --enable-delegation
```

To allow safe automated refactor commit back to the PR branch:
```bash
poetry run review-agent run-pr-review --repo owner/repo --pr-number 123 --action synchronize --enable-delegation --auto-commit-refactors
```

## Webhook Mode

Start webhook service:
```bash
poetry run uvicorn review_agent.webhook_listener:app --host 0.0.0.0 --port 8000
```

Endpoint:
- `POST /webhook/github`
- Verifies `X-Hub-Signature-256` using `WEBHOOK_SECRET`
- Handles PR actions: `opened`, `synchronize`, `reopened`, `ready_for_review`
- Returns immediately with `run_id` and processes the review in a background task

Run tracking endpoints:
- `GET /webhook/status/{run_id}`: returns `accepted|running|success|failed`
- `GET /webhook/artifacts/{run_id}`: downloads a zip containing `summary.json`, `findings.jsonl`, `metrics.csv` when status is `success`

## GitHub Actions Bridge (Webhook-Only Execution)

Workflow file: `.github/workflows/pr-webhook-bridge.yml`

Required repository secrets:
- `WEBHOOK_URL` (for example `https://<your-ngrok-domain>`)
- `WEBHOOK_SECRET` (must match local `.env` `WEBHOOK_SECRET`)

How it works:
1. On PR events, Actions posts a signed request to `POST /webhook/github`.
2. Workflow receives `run_id` from the webhook response.
3. Workflow polls `GET /webhook/status/{run_id}` until completion.
4. On success, workflow downloads `GET /webhook/artifacts/{run_id}`.
5. Workflow uploads those files to the Actions run via `actions/upload-artifact`.

## Optional: Run with live Ollama

1. Start Ollama locally (`http://localhost:11434`).
2. Pull a model (example):
```bash
ollama pull qwen2.5-coder:7b
```
3. Run review:
```bash
poetry run review-agent run-fixture-review --run-id live-run
```

## Project Layout
- `src/review_agent/`: core implementation
- `config/coding_standards.yaml`: static review rules
- `config/model_profiles.yaml`: LLM model profiles
- `config/thresholds.yaml`: delegation thresholds
- `examples/`: fixture payload/diff + expected output
- `tests/`: unit, integration, and e2e tests
- `artifacts/`: generated machine-readable outputs
- `docs/architecture.md`: architecture diagrams
- `docs/presentation_outline.md`: required presentation content

## Baseline Output Files
Each review run generates:
- `findings.jsonl`
- `summary.json`
- `metrics.csv`

## Notes
- Live Ollama mode is supported for semantic analysis with local open-source models.
- Delegation mode adds threshold-based handoff to refactoring and verification agents.
- GitHub Actions bridge workflow is available in `.github/workflows/pr-webhook-bridge.yml`.
- Live PR flow retrieves commit history and includes commit metadata in summary/artifacts.
