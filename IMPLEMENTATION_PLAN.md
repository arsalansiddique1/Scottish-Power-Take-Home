# Automated Code Review System Implementation Plan (Detailed)

## 1. Objective
Design and implement an end-to-end automated code review system integrated with GitHub pull requests that:
- Triggers automatically on PR events (`opened`, `synchronize`, `reopened`, `ready_for_review`)
- Analyzes code changes with deterministic rule checks + LLM semantic review
- Publishes high-quality, line-level review comments and a summary comment
- Optionally delegates to a refactoring agent for safe automated improvements
- Produces reproducible machine-readable outputs and traceable logs
- Includes clear setup docs and at least one executable example/test case

## 2. Delivery Constraints and Priorities
- Timebox target from brief: ~4 focused hours
- Delivery strategy:
  - Phase 1 (must-have baseline): fully working single-agent reviewer with deterministic outputs
  - Phase 2 (stretch): multi-agent delegation + automated refactoring + verification gate
- Quality bar:
  - Deterministic runs for same input/config
  - Minimal false-positive noise
  - Actionable suggestions with evidence and confidence

## 3. Detailed Tech Stack

### 3.1 Core Runtime and Tooling
- Language: Python 3.11+
- Package manager: `poetry` (required)
- Web framework (webhook mode): `FastAPI` + `uvicorn`
- CLI interface: `typer`
- Data models/config: `pydantic`, `pydantic-settings`, `pyyaml`
- Logging: `structlog` or Python `logging` (JSON formatter)

### 3.2 GitHub Integration
- Authentication:
  - Preferred: GitHub App (least privilege + org-friendly)
  - Fallback: PAT in local/dev
- SDK/API:
  - `PyGithub` for convenience
  - Direct REST API calls for review-comment edge cases
- Triggering:
  - Option A: GitHub webhooks to local/server webhook endpoint
  - Option B: GitHub Actions workflow (recommended for easy demo)

### 3.3 Analysis Layer
- Diff parsing: `unidiff` (or custom parser if needed)
- AST/static checks:
  - Python AST (`ast`) for syntax-aware rules
  - Regex/pattern checks for generic policies
- Optional advanced static security: `semgrep`, `bandit`

### 3.4 Agent and Workflow Orchestration
- `langgraph` for graph/state-machine orchestration (recommended for multi-agent)
- `langchain` core wrappers for model/tool abstractions
- Typed shared state with `pydantic` models

### 3.5 LLM Providers and Model Strategy
- Primary local provider for development/testing: `Ollama`
- Local open-source models for semantic review:
  - `qwen2.5-coder:14b` (default quality model)
  - `qwen2.5-coder:7b` or `llama3.1:8b` (faster/cheaper smoke runs)
- Optional cloud comparison/fallback:
  - OpenAI model through provider adapter (only if needed for quality benchmarking)

Why Ollama is recommended in this assignment context:
1. No per-call API cost for local testing.
2. Privacy/control (code stays local during development).
3. Fast iteration and reproducible experiments with pinned local model tags.
4. Easy demo in take-home submission without requiring paid API keys.

### 3.6 Testing and Quality
- Unit/integration tests: `pytest`, `pytest-mock`
- Lint/format/type: `ruff`, `black`, `mypy`
- HTTP mocking for GitHub API calls: `responses` or `respx`
- CI: GitHub Actions (`lint`, `test`, optional end-to-end sample run)

### 3.7 Output Storage / Artifacts
- Line-oriented findings: JSONL
- Summary metrics: JSON + CSV
- Optional run index/state: SQLite (`sqlite3`)

## 4. Architecture Overview

### 4.1 High-Level Components
1. `webhook_listener`
- Receives PR webhook events
- Verifies webhook signature
- Enqueues/starts review run

2. `github_adapter`
- Fetches PR metadata, changed files, patch hunks, file contents
- Publishes line-level comments and summary
- Handles retries, pagination, and rate limits

3. `review_orchestrator` (LangGraph entry)
- Builds run context
- Executes review graph
- Controls idempotency

4. `diff_parser`
- Converts patch to normalized hunks
- Maps review findings to valid GitHub line references

5. `rules_engine`
- Loads YAML/JSON standards
- Runs static checks by category
- Emits structured findings

6. `llm_reviewer`
- Performs semantic analysis on changed code + context
- Returns schema-validated findings only

7. `finding_merger`
- Deduplicates static + LLM findings
- Applies confidence threshold and severity gating

8. `delegation_manager` (Phase 2)
- Decides if refactor handoff is warranted

9. `refactoring_agent` (Phase 2)
- Applies safe transforms
- Commits to PR branch with explanation

10. `verification_agent` (Phase 2 optional)
- Runs tests/lint on refactoring result
- Allows/blocks publish and supports rollback

11. `artifact_writer`
- Writes deterministic run artifacts and logs

## 5. LangGraph Workflow Design

### 5.1 Graph State (typed)
```python
class ReviewState(BaseModel):
    run_id: str
    repo: str
    pr_number: int
    head_sha: str
    event_type: str
    changed_files: list[ChangedFile]
    static_findings: list[Finding]
    llm_findings: list[Finding]
    merged_findings: list[Finding]
    delegation_decision: DelegationDecision | None
    refactor_actions: list[RefactorAction]
    verification_result: VerificationResult | None
    publish_result: PublishResult | None
    metrics: RunMetrics
```

### 5.2 Nodes
1. `ingest_pr_context`
2. `parse_diff_and_context`
3. `run_static_rules`
4. `run_llm_semantic_review`
5. `merge_and_rank_findings`
6. `decide_delegation`
7. `run_refactor_agent` (conditional)
8. `run_verification` (conditional)
9. `publish_pr_comments`
10. `write_artifacts`

### 5.3 Conditional Routing Rules
- Route to `run_refactor_agent` when any of:
  - complexity score > configured threshold
  - >= N high-severity findings in same file
  - repeated pattern violations across files
- Route to `run_verification` after refactoring
- If verification fails:
  - skip auto-commit merge path
  - publish warning summary and refactor details
- Else publish normal comments + optional refactor commit reference

### 5.4 Determinism Controls
- Temperature = 0
- Strict response schema validation
- Rule config version pinning
- Stable file ordering and finding sort order
- Include model ID + prompt version in artifacts

## 6. Rule System Design

### 6.1 Rule Schema
```yaml
- id: SECURITY_HARDCODED_SECRET
  enabled: true
  category: security
  severity: high
  language: [python, javascript, typescript]
  detector: regex
  pattern: '(?i)(api[_-]?key|secret|token)\s*=\s*["\'][^"\']+["\']'
  description: Potential hardcoded secret found.
  recommendation: Move secret to environment variables or secret manager.
  docs_ref: OWASP-Top10-A02
```

### 6.2 Initial Baseline Rule Set (minimum 7)
- Style:
  - `STYLE_LINE_LENGTH`
  - `STYLE_NAMING_CONVENTION`
- Quality:
  - `QUALITY_DUPLICATED_BRANCH_LOGIC`
  - `QUALITY_COMPLEX_CONDITIONAL`
- Security:
  - `SECURITY_HARDCODED_SECRET`
  - `SECURITY_UNSAFE_EXEC`
- Best practice:
  - `BP_MISSING_ERROR_HANDLING`

### 6.3 Finding Contract
Each finding must include:
- `rule_id`, `category`, `severity`, `confidence`
- `file_path`, `line`, `end_line` (if relevant)
- `title`, `description`, `suggestion`
- `evidence` (short snippet/pattern)
- `source` (`static` or `llm`)

## 7. LLM Plan and Test Strategy (Clarified)

### 7.1 LLMs to Use in This Project
1. Primary local model: `qwen2.5-coder:14b` via Ollama
- Use for semantic code-review quality during demos.

2. Fast test model: `qwen2.5-coder:7b` or `llama3.1:8b`
- Use in CI/local smoke tests for speed.

3. Optional benchmark model (provider-agnostic adapter)
- Run a small comparison set to validate whether local quality is sufficient.

### 7.2 Why this approach fits the brief
- The brief recommends Ollama and emphasizes practical implementation.
- Ollama enables free local runs and avoids API key dependency during evaluation.
- A dual-model strategy balances quality and runtime in a take-home setting.

### 7.3 Prompting Contract
- Input:
  - changed hunks
  - surrounding context lines
  - coding standards subset
- Output:
  - strict JSON list of findings (no prose)
- Guardrails:
  - reject malformed output
  - retry once with repair prompt
  - fallback to static-only findings if still invalid

### 7.4 LLM Evaluation Harness
- Use `examples/` fixture PR patches (3-5 curated scenarios)
- Track per run:
  - number of findings
  - precision proxy (manual label file)
  - schema validity rate
  - runtime per model
- Store comparison in `artifacts/model_eval.csv`

## 8. GitHub PR Comment Strategy

### 8.1 Line-Level Comment Template
- Header: `[Severity][Category] RuleID`
- What: concise issue description
- Why: impact/risk
- Fix: specific recommended change
- Reference: docs/rule link

### 8.2 Summary Comment Template
- Run metadata: commit SHA, config version, model name
- Counts by severity/category
- Top 3 critical findings
- Delegation/refactor status (if any)
- Link/path to artifacts

### 8.3 Idempotency
- Tag each run with `run_id`
- Skip duplicate comments for same file/line/rule/head SHA
- Update summary comment instead of adding infinite duplicates

## 9. Repository Structure (Detailed)
```text
.
├─ src/
│  ├─ main.py
│  ├─ settings.py
│  ├─ models.py
│  ├─ github_adapter.py
│  ├─ webhook_listener.py
│  ├─ review_orchestrator.py
│  ├─ diff_parser.py
│  ├─ rules_engine.py
│  ├─ finding_merger.py
│  ├─ comment_builder.py
│  ├─ artifact_writer.py
│  ├─ analyzers/
│  │  ├─ static_analyzer.py
│  │  ├─ llm_client.py
│  │  └─ llm_reviewer.py
│  └─ agents/
│     ├─ graph.py
│     ├─ delegation_manager.py
│     ├─ refactoring_agent.py
│     └─ verification_agent.py
├─ config/
│  ├─ coding_standards.yaml
│  ├─ thresholds.yaml
│  └─ model_profiles.yaml
├─ examples/
│  ├─ sample_pr_payload.json
│  ├─ sample_diff.patch
│  ├─ labeled_findings.json
│  └─ expected_review_output.json
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ e2e/
├─ artifacts/
├─ docs/
│  ├─ architecture.md
│  ├─ operations.md
│  └─ presentation_outline.md
├─ .github/workflows/
│  ├─ pr-review.yml
│  └─ ci.yml
├─ README.md
├─ pyproject.toml
└─ poetry.lock
```

## 10. Detailed Execution Backlog

### Phase 1: Baseline (Required)
1. Bootstrapping
- Create project scaffold, settings, and model contracts
- Add lint/test CI workflow

2. GitHub integration
- Webhook signature verification
- PR/file/diff retrieval
- Review comment publishing

3. Diff parser + line mapping
- Parse hunks reliably
- Map finding -> GitHub review line
- Cover edge cases with fixtures

4. Static rules engine
- Load config, execute checks, output normalized findings

5. LLM semantic review
- Build prompt + schema parser
- Integrate Ollama model client
- Add fallback behavior

6. Merge findings + publish
- Dedupe findings
- Build actionable comments
- Post summary comment

7. Reproducible artifacts
- JSONL findings, JSON summary, CSV metrics
- Include run metadata and versions

8. Example/test case
- One complete fixture-based e2e test
- Example output files committed under `examples/`

### Phase 2: Multi-Agent (Stretch)
1. Add delegation logic node
2. Implement bounded refactoring actions
3. Add verification gate (lint/test)
4. Add rollback/abort path + PR annotation
5. Add artifacts for delegation events

## 11. Security and Operational Controls
- Secrets via env vars only (`GITHUB_APP_PRIVATE_KEY`, `GITHUB_TOKEN`, `LLM_BASE_URL`, `LLM_API_KEY`)
- Never log secrets or full sensitive snippets
- Rate-limit aware retries with exponential backoff
- Timeout and circuit-breaker around LLM calls
- Fail-safe mode: static-only review if LLM/provider unavailable

## 12. Testing Plan

### 12.1 Unit Tests
- Diff parsing correctness
- Rule evaluation correctness
- Comment formatting and deduping
- Decision routing in delegation manager

### 12.2 Integration Tests
- Webhook payload -> fetched PR artifacts -> findings
- Mocked GitHub comment post assertions
- LLM schema validation + fallback behavior

### 12.3 End-to-End Test (Required)
- Input: sample PR payload + patch
- Output assertions:
  - line-level comments generated
  - summary generated
  - artifacts persisted
  - deterministic ordering of findings

## 13. Definition of Done
1. System runs from PR trigger to posted comments without manual intervention.
2. Baseline rule checks and LLM semantic checks both active.
3. Findings include file/line, severity, confidence, and actionable fix suggestion.
4. Artifacts generated in JSONL/JSON/CSV and reproducible for same inputs.
5. README enables setup/run in under 5 minutes.
6. At least one e2e sample test passes.
7. (Stretch) Delegation/refactoring path works with safety checks.

## 14. 4-Hour Delivery Cut Plan
1. Hour 1
- Scaffold project + webhook/action trigger + GitHub fetch.

2. Hour 2
- Diff parser + static rules + unit tests.

3. Hour 3
- Ollama LLM integration + schema validation + comment publishing.

4. Hour 4
- Artifacts + e2e fixture test + README + architecture notes.

If time remains:
- Add delegation node and one safe refactor action (e.g., rename variable or simplify conditional).

## 15. Submission Checklist Mapping
1. Source code
- Modular `src/` with clear separation of concerns.

2. README.md
- Setup, architecture, usage, limitations, and extension points.

3. Configuration (YAML/JSON)
- Coding standards, thresholds, model profiles.

4. Examples directory
- Sample payload/diff, expected outputs, sample logs.

5. Presentation (PDF/PPTX)
- Problem framing, architecture, baseline demo, optional multi-agent demo, results.

6. Logs/Outputs (JSON/JSONL)
- Persisted under `artifacts/` with run metadata.

---
This plan prioritizes a robust baseline reviewer first, then extends into LangGraph-based multi-agent behavior. Ollama is the default testing path to keep the solution free, local, and reproducible.

