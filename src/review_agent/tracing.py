import os
from contextlib import contextmanager
from typing import Any

from review_agent.settings import Settings

try:
    from langsmith.run_helpers import trace as langsmith_trace
except Exception:  # pragma: no cover - optional dependency/runtime
    langsmith_trace = None


def configure_langsmith(settings: Settings) -> None:
    if not settings.langsmith_tracing:
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key


def langgraph_run_config(
    *,
    run_name: str,
    tags: list[str],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "run_name": run_name,
        "tags": tags,
        "metadata": metadata,
    }


@contextmanager
def traced_span(
    *,
    enabled: bool,
    name: str,
    inputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
):
    if not enabled or langsmith_trace is None:
        yield
        return

    with langsmith_trace(
        name=name,
        run_type="chain",
        inputs=inputs or {},
        metadata=metadata or {},
    ):
        yield
