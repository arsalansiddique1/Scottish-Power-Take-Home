# Phased Execution Plan (Step-by-Step)

This document converts `IMPLEMENTATION_PLAN.md` into an actionable implementation sequence.

## 1. How to Use This Plan
- Execute phases in order.
- Do not start a later stage until exit criteria for the current stage are met.
- Commit at each stage boundary.
- Keep all behavior deterministic and test-backed.

## 2. Phase Overview
1. Phase 0: Project foundation and tooling
2. Phase 1: GitHub ingestion and diff context
3. Phase 2: Static analysis and rule engine
4. Phase 3: LLM semantic review (Ollama)
5. Phase 4: Comment publishing and artifacts
6. Phase 5: End-to-end baseline validation (required)
7. Phase 6: Multi-agent delegation and refactor (stretch)

---

## 3. Phase 0: Project Foundation and Tooling

### Goal
Create a Poetry-managed Python project with runnable CLI, config loading, and test/lint setup.

### Steps
1. Initialize Poetry project and dependency groups (`main`, `dev`).
2. Create baseline folder structure (`src/`, `config/`, `tests/`, `examples/`, `artifacts/`, `docs/`).
3. Add core config + settings module.
4. Add quality tooling (`ruff`, `black`, `mypy`, `pytest`).
5. Add CI workflow for lint + tests.

### Deliverables
- `pyproject.toml`
- `poetry.lock`
- `src/main.py` (CLI entry)
- `src/settings.py`
- `.github/workflows/ci.yml`

### Exit Criteria
- `poetry install` succeeds.
- `poetry run pytest` runs.
- `poetry run ruff check .` runs.

---

## 4. Phase 1: GitHub Ingestion and Diff Context

### Goal
Ingest PR event data and produce normalized changed-file/diff context.

### Steps
1. Build webhook payload model (`repo`, `pr_number`, `head_sha`, event type).
2. Implement GitHub adapter for:
- fetching PR metadata
- listing changed files
- retrieving patch content and file content
3. Implement retry and rate-limit handling.
4. Add diff parser for hunk/line mapping.
5. Build fixtures for sample payload and sample patch.

### Deliverables
- `src/github_adapter.py`
- `src/diff_parser.py`
- `examples/sample_pr_payload.json`
- `examples/sample_diff.patch`
- Integration tests for ingestion and parsing

### Exit Criteria
- Sample payload produces normalized `ChangedFile[]` + mapped changed lines.
- Parser handles multi-hunk file fixture.

---

## 5. Phase 2: Static Analysis and Rule Engine

### Goal
Implement deterministic, config-driven static rule checks.

### Steps
1. Define rule schema and create `config/coding_standards.yaml`.
2. Implement finding model contract.
3. Implement static analyzers:
- regex rules
- AST rules (Python)
4. Implement severity/confidence normalization.
5. Add finding deduplication and stable sorting.
6. Add unit tests per rule category.

### Deliverables
- `src/rules_engine.py`
- `src/analyzers/static_analyzer.py`
- `config/coding_standards.yaml`
- `tests/unit/test_rules_engine.py`

### Exit Criteria
- At least 7 baseline rules implemented.
- Same input yields identical ordered findings.

---

## 6. Phase 3: LLM Semantic Review (Ollama)

### Goal
Add semantic review using local Ollama models with strict schema output.

### Steps
1. Implement model profile config (`config/model_profiles.yaml`).
2. Implement Ollama client wrapper with timeout/retry.
3. Define prompt template with constrained JSON output.
4. Implement schema validation and fallback strategy:
- retry once on malformed output
- fallback to static-only if still invalid
5. Add model switch support (`quality` vs `fast`).
6. Add tests for parser/validation/fallback behavior.

### Deliverables
- `src/analyzers/llm_client.py`
- `src/analyzers/llm_reviewer.py`
- `config/model_profiles.yaml`
- tests for schema guardrails

### Exit Criteria
- Semantic findings generated with valid schema on sample patch.
- Invalid JSON responses do not crash pipeline.

---

## 7. Phase 4: Comment Publishing and Artifacts

### Goal
Produce high-quality PR comments and machine-readable outputs.

### Steps
1. Implement comment builder templates (line-level and summary).
2. Map findings to GitHub review comment format.
3. Implement idempotency logic (`run_id`, duplicate suppression).
4. Implement artifact writer for:
- `artifacts/findings.jsonl`
- `artifacts/summary.json`
- `artifacts/metrics.csv`
5. Add run metadata fields (SHA, model, config version, prompt version).

### Deliverables
- `src/comment_builder.py`
- `src/artifact_writer.py`
- publishing methods in `src/github_adapter.py`

### Exit Criteria
- Sample run creates all artifact files.
- Comments are renderable and actionable.

---

## 8. Phase 5: End-to-End Baseline Validation (Required)

### Goal
Demonstrate the full baseline pipeline from sample PR input to outputs.

### Steps
1. Implement `review_orchestrator.py` for single-agent baseline flow.
2. Implement CLI command: run review from fixture payload.
3. Add deterministic e2e test asserting:
- findings created
- summary created
- artifacts persisted
4. Add demo documentation in `README.md` with under-5-minute setup.
5. Capture sample output under `examples/expected_review_output.json`.

### Deliverables
- `src/review_orchestrator.py`
- `tests/e2e/test_end_to_end_sample_pr.py`
- updated `README.md`
- `examples/expected_review_output.json`

### Exit Criteria
- One-command local demo works.
- e2e test passes in CI.

---

## 9. Phase 6: Multi-Agent Delegation and Refactor (Stretch)

### Goal
Add LangGraph-based handoff to a bounded refactoring agent.

### Steps
1. Define shared graph state model.
2. Implement LangGraph baseline nodes:
- ingest
- static review
- llm review
- merge findings
- delegation decision
- publish
3. Add conditional route to refactoring node based on thresholds.
4. Implement bounded refactor actions (safe subset only).
5. Add verification node (lint/tests) before finalizing refactor output.
6. Publish delegation/refactor outcome in summary comment.

### Deliverables
- `src/agents/graph.py`
- `src/agents/delegation_manager.py`
- `src/agents/refactoring_agent.py`
- `src/agents/verification_agent.py`

### Exit Criteria
- Delegation is deterministic and threshold-driven.
- Refactor path produces auditable output and does not bypass verification.

---

## 10. Recommended Build Order (Strict)
1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 5 (baseline e2e lock-in)
5. Phase 3
6. Phase 4
7. Re-run Phase 5 validations
8. Phase 6 (if time)

Reason: lock deterministic baseline early, then layer LLM and advanced flow.

---

## 11. Tracking Template (Per Stage)
Use this checklist for each stage:

- Scope implemented
- Tests added
- CI passing
- Artifacts/sample output updated
- README updated
- Risks/limitations logged

---

## 12. Risk Controls by Stage
1. Early API complexity risk
- Mitigation: fixture-first development and mocked integration tests.

2. LLM reliability risk
- Mitigation: strict schema parser + fallback mode.

3. Comment noise risk
- Mitigation: confidence threshold + dedupe + severity gating.

4. Time risk
- Mitigation: treat Phase 6 as optional; never block baseline delivery.

---

## 13. Definition of Success
- Baseline required scope is fully working and demonstrable.
- Submission artifacts are complete and reproducible.
- Multi-agent enhancement is included only if baseline is stable.
