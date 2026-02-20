from review_agent.agents.refactoring_agent import RefactoringAgent
from review_agent.models import ChangedFile


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
