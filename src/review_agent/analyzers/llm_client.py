from collections.abc import Mapping
from typing import Any

import ollama


class OllamaLLMClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    def chat(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        timeout_seconds: float,
    ) -> str:
        # Build a client with per-call timeout so stalled model calls fail cleanly.
        client = ollama.Client(host=self._base_url, timeout=timeout_seconds)
        response: Mapping[str, Any] = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperature},
            format="json",
        )
        message = response.get("message", {})
        content = message.get("content", "")
        return str(content)
