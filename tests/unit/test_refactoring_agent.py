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
