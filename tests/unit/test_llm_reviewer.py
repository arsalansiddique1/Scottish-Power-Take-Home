from review_agent.analyzers.llm_client import OllamaLLMClient
from review_agent.analyzers.llm_reviewer import LLMReviewer
from review_agent.models import ChangedFile, Finding
from conftest import require_live_ollama


def _changed_file() -> ChangedFile:
    return ChangedFile(
        file_path="src/example.py",
        status="modified",
        content='''
secret = "abcd1234"
exec(user_input)
''',
    )


def _baseline() -> list[Finding]:
    return [
        Finding(
            rule_id="SECURITY_UNSAFE_EXEC",
            category="security",
            severity="high",
            confidence=0.9,
            file_path="src/example.py",
            line=2,
            title="Unsafe exec",
            description="exec/eval detected",
            suggestion="Avoid eval",
            evidence="exec(user_input)",
            source="static",
        )
    ]


def test_llm_reviewer_live_ollama_returns_structured_findings() -> None:
    base_url, _ = require_live_ollama()

    reviewer = LLMReviewer(
        client=OllamaLLMClient(base_url=base_url),
        model_profiles_path="config/model_profiles.yaml",
        profile="fast",
        temperature=0.0,
    )

    findings = reviewer.review_files([_changed_file()], static_findings=_baseline())

    assert findings
    assert any(f.source == "llm" for f in findings) or any(f.source == "static" for f in findings)
    assert all(0.0 <= f.confidence <= 1.0 for f in findings)
