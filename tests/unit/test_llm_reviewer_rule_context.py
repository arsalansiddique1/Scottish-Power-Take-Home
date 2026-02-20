import json

from review_agent.analyzers.llm_reviewer import LLMReviewer
from review_agent.models import ChangedFile, RuleDefinition


class FakeClient:
    def __init__(self, response_payload: dict[str, object]) -> None:
        self._response_payload = response_payload
        self.last_prompt = ""

    def chat(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        timeout_seconds: float,
    ) -> str:
        _ = (model, temperature, timeout_seconds)
        self.last_prompt = prompt
        return json.dumps(self._response_payload)


def test_llm_reviewer_prompt_includes_rules_and_diff_context() -> None:
    fake = FakeClient(
        response_payload={
            "findings": [
                {
                    "rule_id": "SECURITY_HARDCODED_SECRET",
                    "category": "security",
                    "severity": "high",
                    "line": 3,
                    "title": "Potential hardcoded secret detected.",
                    "description": "Potential hardcoded secret detected.",
                    "suggestion": "Move secrets to env vars.",
                    "evidence": "api_key = 'abc'",
                    "confidence": 0.9,
                    "docs_ref": "OWASP-A02",
                    "reasoning": "Rule matched secret assignment pattern.",
                }
            ]
        }
    )
    rules = [
        RuleDefinition(
            id="SECURITY_HARDCODED_SECRET",
            enabled=True,
            category="security",
            severity="high",
            detector="regex",
            description="Potential hardcoded secret detected.",
            recommendation="Move secrets to environment variables.",
            docs_ref="OWASP-A02",
            languages=["python"],
            pattern="secret",
            confidence=0.9,
        )
    ]
    reviewer = LLMReviewer(
        client=fake,
        model_profiles_path="config/model_profiles.yaml",
        profile="fast",
        rules=rules,
    )
    changed = ChangedFile(
        file_path="src/a.py",
        status="modified",
        patch="@@ -1,1 +1,2 @@\n-api_key='x'\n+api_key='abc'\n+print('ok')\n",
        content="api_key = 'abc'\nprint('ok')\n",
    )

    findings = reviewer.review_files([changed], static_findings=[])

    assert findings
    assert findings[0].docs_ref == "OWASP-A02"
    assert findings[0].reasoning == "Rule matched secret assignment pattern."
    assert "Rules context:" in fake.last_prompt
    assert "SECURITY_HARDCODED_SECRET" in fake.last_prompt
    assert "Diff chunk context:" in fake.last_prompt
    assert "added_lines" in fake.last_prompt


def test_llm_reviewer_normalizes_unknown_rule_id() -> None:
    fake = FakeClient(
        response_payload={
            "findings": [
                {
                    "rule_id": "UNKNOWN_RULE_X",
                    "category": "quality",
                    "severity": "medium",
                    "line": 1,
                    "title": "Unknown",
                    "description": "Unknown",
                    "suggestion": "Unknown",
                    "evidence": "x",
                    "confidence": 0.8,
                }
            ]
        }
    )
    reviewer = LLMReviewer(
        client=fake,
        model_profiles_path="config/model_profiles.yaml",
        profile="fast",
        rules=[],
    )
    changed = ChangedFile(file_path="src/a.py", status="modified", content="x = 1\n")

    findings = reviewer.review_files([changed], static_findings=[])

    assert findings
    assert findings[0].rule_id == "LLM_SEMANTIC_REVIEW"
