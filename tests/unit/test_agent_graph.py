from review_agent.agents.delegation_manager import DelegationManager
from review_agent.agents.graph import DelegationGraphRunner
from review_agent.models import ChangedFile, Finding


def _finding(rule_id: str, category: str, severity: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        category=category,
        severity=severity,
        confidence=0.8,
        file_path="src/x.py",
        line=1,
        title="t",
        description="d",
        suggestion="s",
        evidence="e",
        source="static",
    )


def test_graph_routes_to_refactor_when_delegation_true() -> None:
    manager = DelegationManager.from_yaml("config/thresholds.yaml")
    runner = DelegationGraphRunner(delegation_manager=manager)

    files = [ChangedFile(file_path="src/x.py", status="modified", content="camelCaseVar = 1\n")]
    findings = [
        _finding("SECURITY_A", "security", "high"),
        _finding("SECURITY_B", "security", "high"),
    ]

    result = runner.run(files, findings)
    assert result["delegation_decision"].should_delegate is True
    assert result["refactor_actions"]
    assert result["handoff_log"]
    assert "review_agent->refactoring_agent" in result["handoff_log"][0]


def test_graph_skips_refactor_when_delegation_false() -> None:
    manager = DelegationManager.from_yaml("config/thresholds.yaml")
    runner = DelegationGraphRunner(delegation_manager=manager)

    files = [ChangedFile(file_path="src/x.py", status="modified", content="x = 1\n")]
    findings = [_finding("STYLE_LINE_LENGTH", "style", "low")]

    result = runner.run(files, findings)
    assert result["delegation_decision"].should_delegate is False
    assert result["refactor_actions"] == []
    assert result["handoff_log"]
