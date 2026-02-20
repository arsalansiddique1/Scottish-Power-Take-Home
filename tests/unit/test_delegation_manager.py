from review_agent.agents.delegation_manager import DelegationManager
from review_agent.models import ChangedFile, Finding


def _finding(
    *,
    rule_id: str,
    category: str,
    severity: str,
    file_path: str = "src/a.py",
    line: int = 1,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        category=category,
        severity=severity,
        confidence=0.8,
        file_path=file_path,
        line=line,
        title="t",
        description="d",
        suggestion="s",
        evidence="e",
        source="static",
    )


def test_delegation_manager_triggers_on_thresholds() -> None:
    manager = DelegationManager.from_yaml("config/thresholds.yaml")
    findings = [
        _finding(rule_id="SECURITY_A", category="security", severity="high", line=1),
        _finding(rule_id="SECURITY_B", category="security", severity="high", line=2),
    ]
    decision = manager.decide(findings)

    assert decision.should_delegate is True
    assert decision.reasons


def test_delegation_manager_skips_when_findings_low() -> None:
    manager = DelegationManager.from_yaml("config/thresholds.yaml")
    findings = [_finding(rule_id="STYLE_X", category="style", severity="low")]
    decision = manager.decide(findings)

    assert decision.should_delegate is False
    assert decision.reasons == []


def test_delegation_manager_can_trigger_on_low_test_coverage_signal() -> None:
    manager = DelegationManager.from_yaml("config/thresholds.yaml")
    findings = [
        _finding(rule_id="QUALITY_A", category="quality", severity="medium"),
        _finding(rule_id="QUALITY_B", category="quality", severity="medium"),
    ]
    changed_files = [ChangedFile(file_path="src/service.py", status="modified", content="x = 1\n")]

    decision = manager.decide(findings, changed_files=changed_files)

    assert decision.should_delegate is True
    assert "low_test_coverage_signal" in decision.reasons
