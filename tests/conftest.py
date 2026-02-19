import os

import pytest

from review_agent.analyzers.llm_client import OllamaLLMClient


def require_live_ollama() -> tuple[str, str]:
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_TEST_MODEL", "qwen2.5-coder:7b")

    client = OllamaLLMClient(base_url=base_url)
    try:
        client.chat(
            model=model,
            prompt='Return JSON: {"findings": []}',
            temperature=0.0,
            timeout_seconds=10.0,
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Live Ollama not available for tests ({base_url}, {model}): {exc}")

    return base_url, model
