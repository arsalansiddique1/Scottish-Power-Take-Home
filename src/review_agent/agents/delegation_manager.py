from pathlib import Path

import yaml

from review_agent.models import DelegationDecision, Finding


class DelegationManager:
    def __init__(self, thresholds: dict[str, object]) -> None:
        self._total_findings_threshold = int(thresholds.get("total_findings_threshold", 3))
        self._high_severity_in_file_threshold = int(
            thresholds.get("high_severity_in_file_threshold", 2)
        )
        self._quality_or_security_findings_threshold = int(
            thresholds.get("quality_or_security_findings_threshold", 2)
        )
        self._complex_trigger_rule = str(
            thresholds.get("complex_conditional_trigger_rule", "QUALITY_COMPLEX_CONDITIONAL")
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DelegationManager":
        loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(dict(loaded.get("thresholds", {})))

    def decide(self, findings: list[Finding]) -> DelegationDecision:
        reasons: list[str] = []

        if len(findings) >= self._total_findings_threshold:
            reasons.append(f"total_findings>={self._total_findings_threshold}")

        high_by_file: dict[str, int] = {}
        qs_count = 0
        for finding in findings:
            if finding.severity in {"high", "critical"}:
                high_by_file[finding.file_path] = high_by_file.get(finding.file_path, 0) + 1
            if finding.category in {"quality", "security"}:
                qs_count += 1
            if finding.rule_id == self._complex_trigger_rule:
                reasons.append("complexity_trigger_rule_detected")

        if any(v >= self._high_severity_in_file_threshold for v in high_by_file.values()):
            reasons.append(
                f"high_severity_in_file>={self._high_severity_in_file_threshold}"
            )

        if qs_count >= self._quality_or_security_findings_threshold:
            reasons.append(
                f"quality_or_security_findings>={self._quality_or_security_findings_threshold}"
            )

        deduped_reasons = sorted(set(reasons))
        return DelegationDecision(should_delegate=bool(deduped_reasons), reasons=deduped_reasons)
