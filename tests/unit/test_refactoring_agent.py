from review_agent.agents.refactoring_agent import RefactoringAgent
from review_agent.models import ChangedFile, Finding


def test_refactoring_agent_applies_bounded_actions() -> None:
    changed_files = [
        ChangedFile(
            file_path="src/x.py",
            status="modified",
            content="""
def f(flag):
    camelCaseVar = 1
    if flag:
        return camelCaseVar
    else:
        return camelCaseVar
""",
        )
    ]

    updated_files, actions = RefactoringAgent().apply(changed_files)

    assert actions
    assert any(a.action_type == "rename_variable" for a in actions)
    assert any(a.action_type == "simplify_conditional" for a in actions)
    assert "camel_case_var" in updated_files[0].content


def test_refactoring_agent_gracefully_falls_back_when_llm_not_available() -> None:
    changed_files = [
        ChangedFile(
            file_path="src/y.py",
            status="modified",
            content="camelCaseVar = 1\n",
        )
    ]

    agent = RefactoringAgent(client=None)
    updated_files, actions = agent.apply(changed_files, findings=[])

    assert actions
    assert "camel_case_var" in updated_files[0].content


class _InvalidSyntaxLLMClient:
    def chat(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        timeout_seconds: float,
    ) -> str:
        _ = (model, prompt, temperature, timeout_seconds)
        return (
            '{"apply": true, "transformed_code": "def broken(:\\n    pass", '
            '"actions": [{"action_type": "llm_refactor", "description": "bad"}]}'
        )


def test_refactoring_agent_rejects_invalid_llm_refactor_and_keeps_safe_output() -> None:
    changed_files = [
        ChangedFile(
            file_path="src/z.py",
            status="modified",
            content="camelCaseVar = 1\n",
        )
    ]
    agent = RefactoringAgent(
        client=_InvalidSyntaxLLMClient(),
        model_profiles_path="config/model_profiles.yaml",
        profile="fast",
    )

    findings = [
        Finding(
            rule_id="QUALITY_COMPLEX_CONDITIONAL",
            category="quality",
            severity="medium",
            confidence=0.8,
            file_path="src/z.py",
            line=1,
            title="complexity",
            description="complexity",
            suggestion="simplify",
            evidence="camelCaseVar = 1",
            source="llm",
        )
    ]
    updated_files, actions = agent.apply(changed_files, findings=findings)

    assert "camel_case_var = 1" in updated_files[0].content
    assert any(a.action_type == "reject_invalid_llm_refactor" for a in actions)
