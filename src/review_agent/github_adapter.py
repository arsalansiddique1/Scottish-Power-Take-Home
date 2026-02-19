import time
from collections.abc import Callable
from typing import Any

from github import Auth
from github import Github
from github.GithubException import GithubException, RateLimitExceededException

from review_agent.diff_parser import extract_reviewable_added_lines
from review_agent.models import ChangedFile, CommitInfo, PRContext, PRLineComment

RETRYABLE_STATUS_CODES = {403, 429, 500, 502, 503, 504}


class GithubAdapter:
    def __init__(
        self,
        token: str,
        client: Any | None = None,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        elif token:
            self._client = Github(auth=Auth.Token(token))
        else:
            self._client = None
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep_fn or time.sleep

    def get_pr_context(self, repo_full_name: str, pr_number: int, action: str) -> PRContext:
        def operation() -> PRContext:
            repo = self._require_client().get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            return PRContext(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                head_sha=str(pr.head.sha),
                action=action,
            )

        return self._run_with_retries(operation)

    def get_changed_files(self, context: PRContext) -> list[ChangedFile]:
        def operation() -> list[ChangedFile]:
            repo = self._require_client().get_repo(context.repo_full_name)
            pr = repo.get_pull(context.pr_number)
            normalized: list[ChangedFile] = []
            for file in pr.get_files():
                raw_patch = str(getattr(file, "patch", "") or "")
                try:
                    reviewable_lines = extract_reviewable_added_lines(raw_patch)
                except Exception:
                    # Never fail the full webhook run because one file patch is malformed.
                    reviewable_lines = []

                normalized.append(
                    ChangedFile(
                        file_path=str(getattr(file, "filename", "")),
                        status=str(getattr(file, "status", "")),
                        patch=raw_patch,
                        sha=getattr(file, "sha", None),
                        additions=int(getattr(file, "additions", 0) or 0),
                        deletions=int(getattr(file, "deletions", 0) or 0),
                        changes=int(getattr(file, "changes", 0) or 0),
                        reviewable_lines=reviewable_lines,
                    )
                )
            return normalized

        return self._run_with_retries(operation)

    def hydrate_file_contents(self, context: PRContext, changed_files: list[ChangedFile]) -> list[ChangedFile]:
        def operation() -> list[ChangedFile]:
            repo = self._require_client().get_repo(context.repo_full_name)
            hydrated: list[ChangedFile] = []
            for changed_file in changed_files:
                content = ""
                try:
                    item = repo.get_contents(changed_file.file_path, ref=context.head_sha)
                    if not isinstance(item, list):
                        content = item.decoded_content.decode("utf-8")
                except Exception:
                    content = ""
                hydrated.append(changed_file.model_copy(update={"content": content}))
            return hydrated

        return self._run_with_retries(operation)

    def get_commit_history(self, context: PRContext, limit: int = 20) -> list[CommitInfo]:
        def operation() -> list[CommitInfo]:
            repo = self._require_client().get_repo(context.repo_full_name)
            pr = repo.get_pull(context.pr_number)
            commits: list[CommitInfo] = []
            for commit in pr.get_commits()[:limit]:
                author_name = ""
                commit_date = ""
                if getattr(commit, "commit", None):
                    commit_obj = commit.commit
                    if getattr(commit_obj, "author", None):
                        author_name = str(getattr(commit_obj.author, "name", "") or "")
                        commit_date = str(getattr(commit_obj.author, "date", "") or "")
                commits.append(
                    CommitInfo(
                        sha=str(getattr(commit, "sha", "")),
                        author=author_name,
                        message=str(getattr(getattr(commit, "commit", None), "message", "") or ""),
                        date=commit_date,
                    )
                )
            return commits

        return self._run_with_retries(operation)

    def publish_line_comments(
        self,
        context: PRContext,
        comments: list[PRLineComment],
        commit_id: str,
    ) -> None:
        if not comments:
            return

        def operation() -> None:
            repo = self._require_client().get_repo(context.repo_full_name)
            pr = repo.get_pull(context.pr_number)
            for comment in comments:
                pr.create_review_comment(
                    body=comment.body,
                    commit=commit_id,
                    path=comment.path,
                    line=comment.line,
                    side=comment.side,
                )

        self._run_with_retries(operation)

    def publish_summary_comment(self, context: PRContext, body: str) -> None:
        def operation() -> None:
            repo = self._require_client().get_repo(context.repo_full_name)
            pr = repo.get_pull(context.pr_number)
            pr.create_issue_comment(body)

        self._run_with_retries(operation)

    def commit_refactor_changes(
        self,
        context: PRContext,
        changed_files: list[ChangedFile],
        commit_message: str,
    ) -> str | None:
        def operation() -> str | None:
            repo = self._require_client().get_repo(context.repo_full_name)
            pr = repo.get_pull(context.pr_number)
            branch = str(pr.head.ref)
            updated_any = False

            for changed_file in changed_files:
                if not changed_file.content.strip():
                    continue
                remote_item = repo.get_contents(changed_file.file_path, ref=branch)
                if isinstance(remote_item, list):
                    continue
                remote_content = remote_item.decoded_content.decode("utf-8")
                if remote_content == changed_file.content:
                    continue
                repo.update_file(
                    path=changed_file.file_path,
                    message=commit_message,
                    content=changed_file.content,
                    sha=remote_item.sha,
                    branch=branch,
                )
                updated_any = True

            if not updated_any:
                return None

            refreshed = repo.get_pull(context.pr_number)
            return str(refreshed.head.sha)

        return self._run_with_retries(operation)

    def _require_client(self) -> Any:
        if self._client is None:
            raise ValueError("GitHub client not configured. Set GITHUB_TOKEN for live PR operations.")
        return self._client

    def _run_with_retries(self, operation: Callable[[], Any]) -> Any:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return operation()
            except RateLimitExceededException as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                self._sleep(self._backoff_seconds * (2**attempt))
            except GithubException as exc:
                last_error = exc
                status = int(getattr(exc, "status", 0) or 0)
                if status not in RETRYABLE_STATUS_CODES or attempt >= self._max_retries:
                    break
                self._sleep(self._backoff_seconds * (2**attempt))
        assert last_error is not None
        raise last_error
