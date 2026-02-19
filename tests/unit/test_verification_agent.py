from review_agent.agents.verification_agent import VerificationAgent
from review_agent.models import ChangedFile


def test_verification_agent_fails_on_invalid_python() -> None:
    changed_files = [
        ChangedFile(
            file_path="src/bad.py",
            status="modified",
            content="def broken(:\n    pass\n",
        )
    ]
    result = VerificationAgent().verify(changed_files)

    assert result.passed is False
    assert result.details
