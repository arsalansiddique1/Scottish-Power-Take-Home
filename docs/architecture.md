# Architecture

## High-Level Flow

```mermaid
flowchart TD
    A[GitHub PR Event] --> B[Trigger Layer]
    B --> B1[GitHub Actions pr-review.yml]
    B --> B2[FastAPI Webhook Listener]
    B1 --> C[Review Orchestrator]
    B2 --> C

    C --> D[GitHub Adapter]
    D --> D1[PR Metadata]
    D --> D2[Changed Files and Diffs]
    D --> D3[Full File Contents]
    D --> D4[Commit History]

    C --> E[Rules Engine]
    C --> F[LLM Reviewer]
    E --> G[Merged Findings]
    F --> G

    G --> H[Comment Builder]
    H --> I[Line-level Comments]
    H --> J[Summary Comment]

    G --> K[Delegation Manager]
    K -->|delegate| L[Refactoring Agent]
    K -->|skip| N[Publish]
    L --> M[Verification Agent]
    M --> N

    N --> O[GitHub PR Comments]
    M --> P[Optional Refactor Commit]

    C --> Q[Artifact Writer]
    Q --> Q1[findings.jsonl]
    Q --> Q2[summary.json]
    Q --> Q3[metrics.csv]
```

## Multi-Agent Graph (LangGraph)

```mermaid
flowchart LR
    S[Start] --> D[decide_delegation]
    D -->|delegate| R[run_refactor]
    D -->|skip| E[End]
    R --> V[run_verification]
    V --> E
```

## Key Design Guarantees
- Deterministic ordering and deduplication of findings.
- Structured outputs with run metadata and commit-history count.
- Safe bounded refactoring actions plus verification gate.
- Optional commit-back path to PR branch with explanatory summary comment.
