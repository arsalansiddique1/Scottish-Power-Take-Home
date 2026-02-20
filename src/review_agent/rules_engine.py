from pathlib import Path

import yaml

from review_agent.analyzers.static_analyzer import apply_rule
from review_agent.models import ChangedFile, Finding, RuleDefinition, RulesConfig


class RulesEngine:
    def __init__(self, rules: list[RuleDefinition]) -> None:
        self._rules = [rule for rule in rules if rule.enabled]

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> 'RulesEngine':
        loaded = yaml.safe_load(Path(config_path).read_text(encoding='utf-8'))
        config = RulesConfig.model_validate(loaded)
        return cls(config.rules)

    def analyze_files(self, changed_files: list[ChangedFile]) -> list[Finding]:
        findings: list[Finding] = []
        for changed_file in sorted(changed_files, key=lambda c: c.file_path):
            for rule in self._rules:
                findings.extend(apply_rule(rule, changed_file))
        return self._dedupe_and_sort(findings)

    def active_rules(self) -> list[RuleDefinition]:
        return list(self._rules)

    def _dedupe_and_sort(self, findings: list[Finding]) -> list[Finding]:
        unique: dict[tuple[str, str, int, str], Finding] = {}
        for finding in findings:
            key = (finding.rule_id, finding.file_path, finding.line, finding.evidence)
            if key not in unique:
                unique[key] = finding

        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        return sorted(
            unique.values(),
            key=lambda f: (
                f.file_path,
                severity_order[f.severity],
                f.line,
                f.rule_id,
                f.evidence,
            ),
        )
