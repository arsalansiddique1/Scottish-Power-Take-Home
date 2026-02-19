import json
from pathlib import Path

import pytest

from review_agent.github_adapter import GithubAdapter
from review_agent.models import parse_pr_webhook_payload


class FakeFile:
    def __init__(self, filename: str, patch: str) -> None:
        self.filename = filename
        self.status = "modified"
        self.patch = patch
        self.sha = "file_sha"
        self.additions = 2
        self.deletions = 1
        self.changes = 3


class FakePullRequest:
    def __init__(self, files: list[FakeFile]) -> None:
        self._files = files

    def get_files(self) -> list[FakeFile]:
        return self._files


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


def test_parse_pr_webhook_payload(sample_payload: dict[str, object]) -> None:
    context = parse_pr_webhook_payload(sample_payload)

    assert context.action == "synchronize"
    assert context.repo_full_name == "acme/demo-repo"
    assert context.pr_number == 42
    assert context.head_sha == "abc123def456"


def test_github_adapter_normalizes_changed_files(sample_payload: dict[str, object]) -> None:
    context = parse_pr_webhook_payload(sample_payload)
    fake_files = [
        FakeFile(
            "src/app.py",
            "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-print('x')\n+print('y')\n",
        )
    ]
    adapter = GithubAdapter(token="", client=FakeClient(FakeRepo(FakePullRequest(fake_files))))

    changed_files = adapter.get_changed_files(context)
    assert len(changed_files) == 1
    assert changed_files[0].file_path == "src/app.py"
    assert changed_files[0].status == "modified"
    assert "+print('y')" in changed_files[0].patch
    assert changed_files[0].reviewable_lines == [1]
