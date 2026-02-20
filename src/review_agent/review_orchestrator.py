import json
import logging
from pathlib import Path
from uuid import uuid4

from review_agent.agents.delegation_manager import DelegationManager
from review_agent.agents.graph import DelegationGraphRunner
from review_agent.agents.refactoring_agent import RefactoringAgent
from review_agent.analyzers.llm_client import OllamaLLMClient
from review_agent.analyzers.llm_reviewer import LLMReviewer
from review_agent.artifact_writer import ArtifactWriter
from review_agent.comment_builder import build_line_comments, build_summary_comment
from review_agent.github_adapter import GithubAdapter
from review_agent.models import ChangedFile, CommitInfo, PRContext, parse_pr_webhook_payload
from review_agent.rules_engine import RulesEngine
from review_agent.settings import Settings
from review_agent.tracing import configure_langsmith, langgraph_run_config, traced_span

logger = logging.getLogger(__name__)


class ReviewOrchestrator:
    def __init__(
        self,
        settings: Settings,
        rules_config_path: str | Path = "config/coding_standards.yaml",
        model_profiles_path: str | Path = "config/model_profiles.yaml",
        thresholds_config_path: str | Path = "config/thresholds.yaml",
        github_adapter: GithubAdapter | None = None,
    ) -> None:
        self._settings = settings
        configure_langsmith(settings)
        self._rules_engine = RulesEngine.from_yaml(rules_config_path)
        self._model_profiles_path = model_profiles_path
        self._thresholds_config_path = thresholds_config_path
        self._github_adapter = github_adapter or GithubAdapter(token=settings.github_token)

    def run_fixture_review(
        self,
        *,
        payload_path: str | Path,
        patch_path: str | Path,
        output_dir: str | Path = "artifacts",
        run_id: str | None = None,
        enable_delegation: bool = False,
    ) -> dict[str, object]:
        payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
        context = parse_pr_webhook_payload(payload)
        patch = Path(patch_path).read_text(encoding="utf-8")

        changed_files = [
            ChangedFile(
                file_path="src/calculator.py",
                status="modified",
                patch=patch,
            )
        ]

        return self._run_pipeline(
            context=context,
            changed_files=changed_files,
            output_dir=output_dir,
            run_id=run_id,
            enable_delegation=enable_delegation,
            publish_to_github=False,
            auto_commit_refactors=False,
            commit_history=[],
        )

    def run_pr_review(
        self,
        *,
        repo_full_name: str,
        pr_number: int,
        action: str,
        output_dir: str | Path = "artifacts",
        run_id: str | None = None,
        enable_delegation: bool = True,
        auto_commit_refactors: bool = False,
    ) -> dict[str, object]:
        logger.info("stage=get_pr_context repo=%s pr=%s action=%s", repo_full_name, pr_number, action)
        context = self._github_adapter.get_pr_context(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            action=action,
        )
        logger.info("stage=get_changed_files repo=%s pr=%s", repo_full_name, pr_number)
        changed_files = self._github_adapter.get_changed_files(context)
        logger.info("stage=hydrate_file_contents files=%s", len(changed_files))
        changed_files = self._github_adapter.hydrate_file_contents(context, changed_files)
        logger.info("stage=get_commit_history")
        commit_history = self._github_adapter.get_commit_history(context)

        return self._run_pipeline(
            context=context,
            changed_files=changed_files,
            output_dir=output_dir,
            run_id=run_id,
            enable_delegation=enable_delegation,
            publish_to_github=True,
            auto_commit_refactors=auto_commit_refactors,
            commit_history=commit_history,
        )

    def _run_pipeline(
        self,
        *,
        context: PRContext,
        changed_files: list[ChangedFile],
        output_dir: str | Path,
        run_id: str | None,
        enable_delegation: bool,
        publish_to_github: bool,
        auto_commit_refactors: bool,
        commit_history: list[CommitInfo] | None = None,
    ) -> dict[str, object]:
        resolved_run_id = run_id or uuid4().hex[:12]
        trace_metadata = {
            "run_id": resolved_run_id,
            "repo": context.repo_full_name,
            "pr_number": context.pr_number,
            "head_sha": context.head_sha,
            "llm_model": self._settings.llm_model,
            "llm_profile": self._settings.llm_profile,
            "delegation_enabled": enable_delegation,
        }

        logger.info("stage=static_analysis files=%s", len(changed_files))
        with traced_span(
            enabled=self._settings.langsmith_tracing,
            name="static_analysis",
            inputs={"changed_files": len(changed_files)},
            metadata=trace_metadata,
        ):
            static_findings = self._rules_engine.analyze_files(changed_files)
        logger.info("stage=static_analysis_done findings=%s", len(static_findings))
        llm_client = OllamaLLMClient(base_url=self._settings.llm_base_url)
        llm_profile = self._settings.llm_profile

        llm_reviewer = LLMReviewer(
            client=llm_client,
            model_profiles_path=self._model_profiles_path,
            profile=llm_profile,
            temperature=0.0,
            timeout_seconds=self._settings.llm_timeout_seconds,
        )

        logger.info("stage=llm_review profile=%s model=%s", llm_profile, self._settings.llm_model)
        with traced_span(
            enabled=self._settings.langsmith_tracing,
            name="llm_review",
            inputs={"changed_files": len(changed_files)},
            metadata=trace_metadata,
        ):
            findings = llm_reviewer.review_files(changed_files, static_findings=static_findings)
        logger.info("stage=llm_review_done findings=%s", len(findings))

        delegation_status = "not-run"
        delegation_reasons: list[str] = []
        refactor_actions: list[dict[str, object]] = []
        verification_details: list[str] = []
        handoff_log: list[str] = []
        refactor_commit_sha: str | None = None

        delegated_files = changed_files
        if enable_delegation:
            logger.info("stage=delegation_start")
            refactoring_agent = RefactoringAgent(
                client=llm_client,
                model_profiles_path=self._model_profiles_path,
                profile=llm_profile,
                temperature=0.0,
                timeout_seconds=self._settings.llm_timeout_seconds,
            )
            graph_runner = DelegationGraphRunner(
                delegation_manager=DelegationManager.from_yaml(self._thresholds_config_path),
                refactoring_agent=refactoring_agent,
            )
            graph_result = graph_runner.run(
                changed_files=changed_files,
                findings=findings,
                graph_config=langgraph_run_config(
                    run_name="delegation_graph",
                    tags=["delegation", "pr-review"],
                    metadata=trace_metadata,
                ),
            )
            decision = graph_result["delegation_decision"]
            verification = graph_result["verification_result"]
            actions = graph_result["refactor_actions"]
            delegated_files = graph_result["changed_files"]

            delegation_reasons = decision.reasons
            refactor_actions = [action.model_dump() for action in actions]
            verification_details = verification.details
            handoff_log = list(graph_result.get("handoff_log", []))

            if not decision.should_delegate:
                delegation_status = "skipped"
            elif verification.passed:
                delegation_status = "delegated_verified"
            else:
                delegation_status = "delegated_failed_verification"
            logger.info(
                "stage=delegation_done status=%s actions=%s",
                delegation_status,
                len(refactor_actions),
            )

        line_comments = build_line_comments(
            findings,
            run_id=resolved_run_id,
            changed_files=changed_files,
        )
        summary = build_summary_comment(
            findings,
            run_id=resolved_run_id,
            head_sha=context.head_sha,
            model_name=self._settings.llm_model,
            config_version="v1",
            prompt_version="p1",
            delegation_status=delegation_status,
        )
        if commit_history:
            summary = (
                f"{summary}\n\n### Commit History Snapshot\n"
                f"- commits_analyzed: `{len(commit_history)}`\n"
                f"- latest_commit: `{commit_history[0].sha}`"
            )

        if publish_to_github:
            logger.info("stage=publish_line_comments count=%s", len(line_comments))
            with traced_span(
                enabled=self._settings.langsmith_tracing,
                name="publish_line_comments",
                inputs={"line_comments": len(line_comments)},
                metadata=trace_metadata,
            ):
                self._github_adapter.publish_line_comments(
                    context=context,
                    comments=line_comments,
                    commit_id=context.head_sha,
                )
            logger.info("stage=publish_summary_comment")
            with traced_span(
                enabled=self._settings.langsmith_tracing,
                name="publish_summary_comment",
                inputs={"summary_length": len(summary)},
                metadata=trace_metadata,
            ):
                self._github_adapter.publish_summary_comment(context=context, body=summary)

            if auto_commit_refactors and delegation_status == "delegated_verified":
                logger.info("stage=commit_refactors_start")
                with traced_span(
                    enabled=self._settings.langsmith_tracing,
                    name="commit_refactors",
                    inputs={"files": len(delegated_files)},
                    metadata=trace_metadata,
                ):
                    refactor_commit_sha = self._github_adapter.commit_refactor_changes(
                        context=context,
                        changed_files=delegated_files,
                        commit_message="chore(refactor-agent): apply safe automated refactors",
                    )
                if refactor_commit_sha:
                    action_lines = "\n".join(
                        f"- `{a.get('file_path', '')}` `{a.get('action_type', '')}`: {a.get('description', '')}"
                        for a in refactor_actions[:10]
                    )
                    self._github_adapter.publish_summary_comment(
                        context=context,
                        body=(
                            "Refactoring agent committed safe updates to the PR branch.\n"
                            f"- commit: `{refactor_commit_sha}`\n"
                            f"- actions: `{len(refactor_actions)}`\n"
                            f"{action_lines}"
                        ),
                    )
                logger.info("stage=commit_refactors_done sha=%s", refactor_commit_sha or "")

        logger.info("stage=write_artifacts")
        with traced_span(
            enabled=self._settings.langsmith_tracing,
            name="write_artifacts",
            inputs={"output_dir": str(output_dir)},
            metadata=trace_metadata,
        ):
            artifacts = ArtifactWriter(output_dir=output_dir).write(
                findings=findings,
                summary_comment=summary,
                run_metadata={
                    "run_id": resolved_run_id,
                    "head_sha": context.head_sha,
                    "model_name": self._settings.llm_model,
                    "config_version": "v1",
                    "prompt_version": "p1",
                    "delegation_status": delegation_status,
                "commit_count": str(len(commit_history or [])),
                "handoff_log": " | ".join(handoff_log) if enable_delegation else "",
            },
        )
        logger.info("stage=complete run_id=%s findings=%s", resolved_run_id, len(findings))

        return {
            "run_id": resolved_run_id,
            "repo": context.repo_full_name,
            "pr_number": context.pr_number,
            "head_sha": context.head_sha,
            "total_findings": len(findings),
            "line_comments": len(line_comments),
            "summary_comment": summary,
            "artifacts": artifacts,
            "delegation_status": delegation_status,
            "delegation_reasons": delegation_reasons,
            "refactor_actions": refactor_actions,
            "verification_details": verification_details,
            "handoff_log": handoff_log if enable_delegation else [],
            "refactor_commit_sha": refactor_commit_sha,
            "commit_history_count": len(commit_history or []),
        }
