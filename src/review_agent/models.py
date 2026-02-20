from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]
Category = Literal["style", "quality", "security", "best_practice"]


class PRContext(BaseModel):
    repo_full_name: str
    pr_number: int
    head_sha: str
    action: str


class ChangedFile(BaseModel):
    file_path: str
    status: str
    patch: str = ""
    content: str = ""
    sha: str | None = None
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    reviewable_lines: list[int] = Field(default_factory=list)


class PullRequestSnapshot(BaseModel):
    context: PRContext
    changed_files: list[ChangedFile]


class RuleDefinition(BaseModel):
    id: str
    enabled: bool = True
    category: Category
    severity: Severity
    detector: Literal["regex", "line_length", "ast", "heuristic"]
    description: str
    recommendation: str
    docs_ref: str
    languages: list[str] = Field(default_factory=lambda: ["python"])
    pattern: str | None = None
    max_length: int | None = None
    confidence: float = 0.8


class Finding(BaseModel):
    rule_id: str
    category: Category
    severity: Severity
    confidence: float
    file_path: str
    line: int
    end_line: int | None = None
    title: str
    description: str
    suggestion: str
    evidence: str
    docs_ref: str | None = None
    reasoning: str | None = None
    problematic_code: str | None = None
    replacement_code: str | None = None
    suggested_diff: str | None = None
    source: Literal["static", "llm"] = "static"


class PRLineComment(BaseModel):
    path: str
    start_line: int | None = None
    line: int
    body: str
    start_side: Literal["RIGHT"] | None = None
    side: Literal["RIGHT"] = "RIGHT"


class CommitInfo(BaseModel):
    sha: str
    author: str = ""
    message: str = ""
    date: str = ""


class RefactorAction(BaseModel):
    file_path: str
    action_type: str
    description: str
    applied: bool


class DelegationDecision(BaseModel):
    should_delegate: bool
    reasons: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    passed: bool
    details: list[str] = Field(default_factory=list)


class RulesConfig(BaseModel):
    rules: list[RuleDefinition]


def parse_pr_webhook_payload(payload: dict[str, Any]) -> PRContext:
    action = str(payload.get("action", ""))
    repo_full_name = str(payload.get("repository", {}).get("full_name", ""))
    pr_number = int(payload.get("pull_request", {}).get("number", 0))
    head_sha = str(payload.get("pull_request", {}).get("head", {}).get("sha", ""))

    if not repo_full_name or not pr_number or not head_sha or not action:
        raise ValueError("Invalid pull request webhook payload")

    return PRContext(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        head_sha=head_sha,
        action=action,
    )
