# Presentation Outline (Required Submission Deck)

## Slide 1: Problem and Objective
- Problem: Manual PR reviews are slow/inconsistent.
- Objective: Build an intelligent automated PR review pipeline with optional multi-agent refactoring.
- Scope: Baseline + advanced delegation path.

## Slide 2: Requirements Mapping
- GitHub integration and PR triggers.
- Diff/context analysis.
- Rule-based + LLM semantic feedback.
- Reproducible outputs (JSONL/JSON/CSV).
- Example/test case.

## Slide 3: Architecture
- Ingestion: Webhook/GitHub Action trigger.
- Analysis: static engine + LLM reviewer.
- Output: line comments + summary + artifacts.
- Optional phase: delegation manager -> refactor agent -> verification agent.

## Slide 4: Technology Stack
- Python + Poetry
- PyGithub + GitHub REST
- LangGraph/LangChain
- Ollama (qwen2.5-coder:14b/7b)
- FastAPI, pytest, ruff

## Slide 5: Baseline Pipeline Walkthrough
- Trigger on PR event.
- Fetch diff + file context.
- Run 7 static rules.
- Run LLM semantic checks.
- Merge findings and publish comments.

## Slide 6: Multi-Agent Delegation
- Delegation thresholds from `config/thresholds.yaml`.
- Refactoring agent performs bounded safe transforms.
- Verification agent enforces syntax gate.
- Optional commit back to PR branch.

## Slide 7: Determinism and Observability
- Stable sorting/deduplication.
- Temperature 0 and schema validation.
- Artifacts: `findings.jsonl`, `summary.json`, `metrics.csv`.

## Slide 8: Demo and Example Results
- Fixture demo command.
- Live PR command.
- Example output screenshot/snippets from artifacts.

## Slide 9: Testing Strategy
- Unit tests: parser/rules/LLM fallback/delegation.
- Integration tests: publish path + live orchestration with mocks.
- E2E tests: fixture pipeline deterministic behavior.

## Slide 10: Tradeoffs, Limitations, Next Steps
- Current refactoring actions intentionally bounded.
- Live LLM dependency optional in CI.
- Next: stronger language support, improved false-positive filtering, full rollback automation.
