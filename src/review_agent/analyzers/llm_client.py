from collections.abc import Mapping
from typing import Any, Protocol

import ollama


class LLMClientProtocol(Protocol):
    def chat(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        timeout_seconds: float,
    ) -> str: ...


class OllamaLLMClient:
    def __init__(self, base_url: str) -> None:
        self._client = ollama.Client(host=base_url)

    def chat(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        timeout_seconds: float,
    ) -> str:
        response: Mapping[str, Any] = self._client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperature},
            format="json",
        )
        message = response.get("message", {})
        content = message.get("content", "")
        return str(content)
