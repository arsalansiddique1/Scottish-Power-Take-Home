from review_agent.analyzers.llm_reviewer import LLMReviewer
from review_agent.models import ChangedFile, Finding


class FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls = 0

    def chat(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        timeout_seconds: float,
    ) -> str:
        _ = (model, prompt, temperature, timeout_seconds)
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


def _changed_file() -> ChangedFile:
    return ChangedFile(
        file_path="src/example.py",
        status="modified",
        content="eval(user_input)\n",
    )


def _baseline() -> list[Finding]:
    return [
        Finding(
            rule_id="SECURITY_UNSAFE_EXEC",
            category="security",
            severity="high",
            confidence=0.9,
            file_path="src/example.py",
            line=1,
            title="Unsafe exec",
            description="exec/eval detected",
            suggestion="Avoid eval",
            evidence="eval(user_input)",
            source="static",
        )
    ]


def test_llm_reviewer_parses_valid_json() -> None:
    response = (
        '[{"rule_id":"LLM_STYLE","category":"style","severity":"low",'
        '"line":1,"title":"Naming","description":"Variable naming issue",'
        '"suggestion":"Rename variable","evidence":"badName","confidence":0.8}]'
    )
    reviewer = LLMReviewer(
        client=FakeLLMClient([response]),
        model_profiles_path="config/model_profiles.yaml",
        profile="fast",
    )

    findings = reviewer.review_files([_changed_file()], static_findings=_baseline())
    assert len(findings) == 2
    assert any(f.source == "llm" for f in findings)


def test_llm_reviewer_retries_once_on_malformed_response() -> None:
    bad = "not-json"
    good = (
        '{"findings":[{"category":"security","severity":"high","line":1,'
        '"title":"Risk","description":"Issue","suggestion":"Fix",'
        '"evidence":"eval","confidence":0.9}]}'
    )
    client = FakeLLMClient([bad, good])
    reviewer = LLMReviewer(
        client=client,
        model_profiles_path="config/model_profiles.yaml",
        profile="fast",
    )

    findings = reviewer.review_files([_changed_file()], static_findings=[])
    assert len(findings) == 1
    assert findings[0].source == "llm"
    assert client.calls == 2


def test_llm_reviewer_falls_back_to_static_only_after_invalid_responses() -> None:
    client = FakeLLMClient(["bad-json", "still-bad"])
    reviewer = LLMReviewer(
        client=client,
        model_profiles_path="config/model_profiles.yaml",
        profile="fast",
    )

    baseline = _baseline()
    findings = reviewer.review_files([_changed_file()], static_findings=baseline)

    assert findings == baseline
    assert client.calls == 2
