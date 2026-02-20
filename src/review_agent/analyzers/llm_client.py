from typing import Any
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage


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
        client = ChatOllama(
            model=model,
            base_url=self._base_url,
            temperature=temperature,
            timeout=timeout_seconds,
            format="json",
        )
        response = client.invoke([HumanMessage(content=prompt)])
        content = response.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(_extract_content_piece(piece) for piece in content)
        return str(content)


def _extract_content_piece(piece: Any) -> str:
    if isinstance(piece, str):
        return piece
    if isinstance(piece, dict):
        return str(piece.get("text", ""))
    return str(piece)
