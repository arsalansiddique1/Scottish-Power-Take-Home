import json

import typer

from review_agent.review_orchestrator import ReviewOrchestrator
from review_agent.settings import get_settings

app = typer.Typer(help="Automated PR review system CLI")


@app.command()
def healthcheck() -> None:
    """Simple command to verify local setup."""
    settings = get_settings()
    typer.echo(
        f"ok | llm_base_url={settings.llm_base_url} | llm_model={settings.llm_model}"
    )


@app.command("run-fixture-review")
def run_fixture_review(
    payload_path: str = "examples/sample_pr_payload.json",
    patch_path: str = "examples/sample_diff.patch",
    output_dir: str = "artifacts",
    run_id: str | None = None,
    live_llm: bool = False,
    enable_delegation: bool = False,
) -> None:
    """Run full baseline review from local fixture files."""
    orchestrator = ReviewOrchestrator(settings=get_settings())
    result = orchestrator.run_fixture_review(
        payload_path=payload_path,
        patch_path=patch_path,
        output_dir=output_dir,
        run_id=run_id,
        use_live_llm=live_llm,
        enable_delegation=enable_delegation,
    )
    typer.echo(json.dumps(result, indent=2))


@app.command("run-pr-review")
def run_pr_review(
    repo_full_name: str = typer.Option(..., "--repo"),
    pr_number: int = typer.Option(..., "--pr-number"),
    action: str = typer.Option("synchronize", "--action"),
    output_dir: str = "artifacts",
    run_id: str | None = None,
    live_llm: bool = False,
    enable_delegation: bool = True,
    auto_commit_refactors: bool = False,
) -> None:
    """Run review pipeline against a live GitHub PR."""
    settings = get_settings()
    if not settings.github_token:
        raise typer.BadParameter("GITHUB_TOKEN must be set for run-pr-review")

    orchestrator = ReviewOrchestrator(settings=settings)
    result = orchestrator.run_pr_review(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        action=action,
        output_dir=output_dir,
        run_id=run_id,
        use_live_llm=live_llm,
        enable_delegation=enable_delegation,
        auto_commit_refactors=auto_commit_refactors,
    )
    typer.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()
