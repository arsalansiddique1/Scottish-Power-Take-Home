import json
from pathlib import Path

import pytest

from review_agent.github_adapter import GithubAdapter
from review_agent.models import PRLineComment, parse_pr_webhook_payload


class FakePullRequest:
    def __init__(self) -> None:
        self.review_comments: list[dict[str, object]] = []
        self.issue_comments: list[str] = []

    def get_files(self) -> list[object]:
        return []

    def create_review_comment(self, **kwargs: object) -> None:
        self.review_comments.append(kwargs)

    def create_issue_comment(self, body: str) -> None:
        self.issue_comments.append(body)


class FakeRepo:
    def __init__(self, pr: FakePullRequest) -> None:
        self._pr = pr

    def get_pull(self, pr_number: int) -> FakePullRequest:
        assert pr_number == 42
        return self._pr


class FakeClient:
    def __init__(self, repo: FakeRepo) -> None:
        self._repo = repo

    def get_repo(self, full_name: str) -> FakeRepo:
        assert full_name == "acme/demo-repo"
        return self._repo


@pytest.fixture
def sample_payload() -> dict[str, object]:
    payload_path = Path("examples/sample_pr_payload.json")
    return json.loads(payload_path.read_text(encoding="utf-8"))


def test_publish_line_and_summary_comments(sample_payload: dict[str, object]) -> None:
    context = parse_pr_webhook_payload(sample_payload)
    fake_pr = FakePullRequest()
    adapter = GithubAdapter(token="", client=FakeClient(FakeRepo(fake_pr)))

    adapter.publish_line_comments(
        context,
        comments=[PRLineComment(path="src/a.py", line=3, body="msg")],
        commit_id="abc123",
    )
    adapter.publish_summary_comment(context, body="summary")

    assert len(fake_pr.review_comments) == 1
    assert fake_pr.review_comments[0]["path"] == "src/a.py"
    assert fake_pr.review_comments[0]["line"] == 3
    assert fake_pr.issue_comments == ["summary"]
