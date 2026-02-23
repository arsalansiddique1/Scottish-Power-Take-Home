# Presentation Outline (Submission Deck Script)

Use this as the exact speaking script + slide content for PDF/PPTX.

## Slide 1: Title and Goal
- Title: Automated GitHub PR Reviewer with Multi-Agent Delegation
- Goal: Reduce manual review effort while improving consistency, auditability, and fix velocity.
- Deliverables: baseline reviewer + advanced delegation/refactor/verification + reproducible outputs.

## Slide 2: Problem Statement
- Manual PR review is slow and reviewer-dependent.
- Security/quality issues can be missed in large diffs.
- Feedback quality varies and often lacks actionable fixes.
- Need: automated, deterministic, explainable PR feedback directly in GitHub.

## Slide 3: Requirements Coverage Map
- GitHub/Webhook integration: implemented.
- Diff/context ingestion + 5–7 rules: implemented (7 rules).
- Static + LLM review comments with line references and fix guidance: implemented.
- Reproducible machine-readable outputs + summary stats: implemented.
- Multi-agent delegation + optional auto-commit with safety gates: implemented.

## Slide 4: Architecture Overview
- Trigger layer: GitHub webhook -> FastAPI listener.
- Ingestion layer: PyGithub fetches PR metadata, changed files, patches, file contents, commit history.
- Analysis layer: static rules + rule-aware LLM reviewer.
- Output layer: PR line comments + summary comment + artifacts.
- Advanced layer: LangGraph decision -> refactor -> verification workflow.

## Slide 5: Tech Stack
- Language/runtime: Python 3.11/3.12
- Packaging: Poetry
- API/service: FastAPI + uvicorn
- GitHub integration: PyGithub
- LLM stack: LangChain + langchain-ollama (`ChatOllama`)
- Model profile: `gpt-oss:20b-cloud` (via Ollama)
- Agent orchestration: LangGraph
- Observability/testing: LangSmith (optional), pytest, ruff

## Slide 6: Baseline Pipeline Walkthrough
- PR opened/updated -> webhook accepted immediately.
- Parse patch hunks to compute reviewable diff lines.
- Load standards from `config/coding_standards.yaml`.
- Run static detectors: regex, AST, heuristic, line-length.
- Run LLM semantic review with:
- rule catalog
- diff-hunk context
- file metadata + reviewable lines
- Publish anchored line comments + summary to GitHub.

## Slide 7: Coding Standards and Rule Coverage
- Config file: `config/coding_standards.yaml`
- 7 baseline rules across:
- Style/Formatting (`STYLE_LINE_LENGTH`, `STYLE_NAMING_CONVENTION`)
- Code Quality (`QUALITY_DUPLICATED_BRANCH_LOGIC`, `QUALITY_COMPLEX_CONDITIONAL`)
- Security (`SECURITY_HARDCODED_SECRET`, `SECURITY_UNSAFE_EXEC`)
- Best Practices (`BP_MISSING_ERROR_HANDLING`)
- Rules are versionable and environment-independent via YAML.

## Slide 8: Comment Quality and Diff Accuracy
- Comments include severity/category/rule/confidence/docs/ref reasoning.
- `Problematic code` and `Suggested fix` blocks rendered in GitHub format.
- Supports single-line and multi-line suggestion anchors.
- Robust anchor fallback:
- range -> single-line retry -> skip unresolved comment (no full-run failure).
- Dedupe + per-file/global caps reduce noise.

## Slide 9: Multi-Agent Delegation Workflow
- LangGraph state machine:
- `decide_delegation`
- `run_refactor`
- `run_verification`
- Delegation criteria in `config/thresholds.yaml`:
- findings volume/severity concentration
- complexity signal
- quality/security count
- low test-coverage signal heuristic
- Handoff log persisted for auditability.

## Slide 10: Safety, Auto-Commit, and Loop Prevention
- Refactor safety:
- reject invalid LLM output per file
- final syntax validation
- rollback to original file content on invalid transformed output
- Optional auto-commit of verified refactors to PR branch.
- Loop guards:
- skip rerun when latest commit is `chore(refactor-agent):...`
- cap automated refactor commits per PR history.

## Slide 11: Reproducibility and Observability
- Artifacts per run:
- `findings.jsonl`
- `summary.json`
- `metrics.csv`
- Webhook tracking:
- `artifacts/webhook/webhook.log`
- `error_<delivery_id>.log` on failures
- Optional LangSmith traces:
- static stage
- llm review
- delegation graph
- publish + artifact stages

## Slide 12: Demo Results and Example Evidence
- Show one real run folder, e.g.:
- `artifacts/webhook/run-<id>/summary.json`
- `artifacts/webhook/run-<id>/findings.jsonl`
- `artifacts/webhook/run-<id>/metrics.csv`
- Show GitHub PR screenshot:
- line comments with suggestion blocks
- summary comment with counts/status
- Show webhook log progression:
- accepted -> start -> result -> success.

## Slide 13: Limitations and Next Steps
- Verification currently emphasizes syntax/static validity; full test execution is not yet built-in.
- Multi-line fix generation can still improve for complex structural refactors.
- Planned enhancements:
- integrated test execution stage in verification
- richer rollback semantics after commit
- language-specific refactor policies
- precision/recall evaluation dashboard for comment quality.
