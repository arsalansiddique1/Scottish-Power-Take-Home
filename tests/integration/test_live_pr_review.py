from review_agent.models import ChangedFile, CommitInfo, PRContext
from review_agent.review_orchestrator import ReviewOrchestrator
from review_agent.settings import Settings


class FakeGithubAdapter:
    def __init__(self) -> None:
        self.line_comments_published = 0
        self.summary_comments_published = 0
        self.commit_called = False

    def get_pr_context(self, repo_full_name: str, pr_number: int, action: str) -> PRContext:
        return PRContext(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            head_sha="headsha123",
            action=action,
        )

    def get_changed_files(self, context: PRContext) -> list[ChangedFile]:
        _ = context
        return [
            ChangedFile(
                file_path="src/live.py",
                status="modified",
                content='''
token = "abc"
exec(user_input)
camelCaseVar = 1
''',
            )
        ]

    def hydrate_file_contents(self, context: PRContext, changed_files: list[ChangedFile]) -> list[ChangedFile]:
        _ = context
        return changed_files

    def get_commit_history(self, context: PRContext, limit: int = 20) -> list[CommitInfo]:
        _ = (context, limit)
        return [CommitInfo(sha="c1", author="dev", message="feat: change", date="2026-02-19")]

    def publish_line_comments(self, context: PRContext, comments: list[object], commit_id: str) -> None:
        _ = (context, commit_id)
        self.line_comments_published += len(comments)

    def publish_summary_comment(self, context: PRContext, body: str) -> None:
        _ = (context, body)
        self.summary_comments_published += 1

    def commit_refactor_changes(
        self,
        context: PRContext,
        changed_files: list[ChangedFile],
        commit_message: str,
    ) -> str | None:
        _ = (context, changed_files, commit_message)
        self.commit_called = True
        return "newsha999"


def test_run_pr_review_live_flow_with_publish_and_refactor_commit(tmp_path) -> None:
    adapter = FakeGithubAdapter()
    orchestrator = ReviewOrchestrator(
        settings=Settings(github_token="dummy-token"),
        github_adapter=adapter,
    )

    result = orchestrator.run_pr_review(
        repo_full_name="acme/live-repo",
        pr_number=12,
        action="synchronize",
        output_dir=tmp_path,
        use_live_llm=False,
        enable_delegation=True,
        auto_commit_refactors=True,
        run_id="live-test-run",
    )

    assert result["run_id"] == "live-test-run"
    assert result["line_comments"] >= 1
    assert adapter.line_comments_published >= 1
    assert adapter.summary_comments_published >= 1
    assert adapter.commit_called is True
    assert result["refactor_commit_sha"] == "newsha999"
    assert result["commit_history_count"] == 1
