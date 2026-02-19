import ast
import re
from typing import NamedTuple

from review_agent.models import ChangedFile, Finding, RuleDefinition


class LineMatch(NamedTuple):
    line_number: int
    evidence: str


def infer_language(file_path: str) -> str:
    if file_path.endswith('.py'):
        return 'python'
    if file_path.endswith('.js'):
        return 'javascript'
    if file_path.endswith('.ts'):
        return 'typescript'
    return 'text'


def build_analysis_text(changed_file: ChangedFile) -> str:
    if changed_file.content.strip():
        return changed_file.content

    lines: list[str] = []
    for raw in changed_file.patch.splitlines():
        if raw.startswith('+++') or raw.startswith('---') or raw.startswith('@@'):
            continue
        if raw.startswith('+'):
            lines.append(raw[1:])
        elif not raw.startswith('-'):
            lines.append(raw.lstrip(' '))
    return '\n'.join(lines)


def apply_rule(rule: RuleDefinition, changed_file: ChangedFile) -> list[Finding]:
    language = infer_language(changed_file.file_path)
    if language not in rule.languages:
        return []

    text = build_analysis_text(changed_file)
    if not text.strip():
        return []

    matches: list[LineMatch] = []
    if rule.detector == 'line_length':
        matches = _line_length_matches(text, rule.max_length or 100)
    elif rule.detector == 'regex' and rule.pattern:
        matches = _regex_matches(text, rule.pattern)
    elif rule.detector == 'ast':
        matches = _ast_matches(text, rule.id)
    elif rule.detector == 'heuristic':
        matches = _heuristic_matches(text, rule.id)

    findings: list[Finding] = []
    for line_number, evidence in matches:
        findings.append(
            Finding(
                rule_id=rule.id,
                category=rule.category,
                severity=rule.severity,
                confidence=max(0.0, min(1.0, rule.confidence)),
                file_path=changed_file.file_path,
                line=line_number,
                title=rule.description,
                description=rule.description,
                suggestion=rule.recommendation,
                evidence=evidence[:180],
                docs_ref=rule.docs_ref,
                reasoning=_reasoning_text(rule.detector, evidence),
                source='static',
            )
        )
    return findings


def _reasoning_text(detector: str, evidence: str) -> str:
    if detector == "regex":
        return f"Regex detector matched line snippet: {evidence[:80]}"
    if detector == "line_length":
        return f"Line-length detector exceeded configured maximum. Snippet: {evidence[:80]}"
    if detector == "ast":
        return f"AST detector matched semantic pattern: {evidence[:80]}"
    if detector == "heuristic":
        return f"Heuristic detector matched rule-specific pattern: {evidence[:80]}"
    return f"Rule detector triggered on snippet: {evidence[:80]}"


def _line_length_matches(text: str, limit: int) -> list[LineMatch]:
    matches: list[LineMatch] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if len(line) > limit:
            matches.append(LineMatch(index, line))
    return matches


def _regex_matches(text: str, pattern: str) -> list[LineMatch]:
    compiled = re.compile(pattern)
    matches: list[LineMatch] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if compiled.search(line):
            matches.append(LineMatch(index, line))
    return matches


def _ast_matches(text: str, rule_id: str) -> list[LineMatch]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    matches: list[LineMatch] = []
    if rule_id == 'QUALITY_COMPLEX_CONDITIONAL':
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                complexity = _bool_complexity(node.test)
                if complexity >= 3:
                    line = int(getattr(node, 'lineno', 1))
                    matches.append(LineMatch(line, f'complexity={complexity}'))
    elif rule_id == 'BP_MISSING_ERROR_HANDLING':
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = _callee_name(node.func)
                if callee in {'open', 'requests.get', 'requests.post'} and not _inside_try(tree, node):
                    line = int(getattr(node, 'lineno', 1))
                    matches.append(LineMatch(line, callee))
    return matches


def _heuristic_matches(text: str, rule_id: str) -> list[LineMatch]:
    lines = text.splitlines()
    matches: list[LineMatch] = []
    if rule_id == 'STYLE_NAMING_CONVENTION':
        pattern = re.compile(r'^\s*([a-z]+[A-Z][A-Za-z0-9]*)\s*=')
        for index, line in enumerate(lines, start=1):
            if pattern.search(line):
                matches.append(LineMatch(index, line))
    elif rule_id == 'QUALITY_DUPLICATED_BRANCH_LOGIC':
        for index in range(len(lines) - 3):
            if lines[index].strip().startswith('if ') and lines[index + 1].strip().startswith('return '):
                if lines[index + 2].strip().startswith('else:') and lines[index + 3].strip().startswith('return '):
                    if lines[index + 1].strip() == lines[index + 3].strip():
                        matches.append(LineMatch(index + 1, lines[index + 1].strip()))
    return matches


def _bool_complexity(node: ast.AST) -> int:
    if isinstance(node, ast.BoolOp):
        base = len(node.values)
        extra = sum(_bool_complexity(v) for v in node.values)
        return base + extra
    return 1


def _callee_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _callee_name(node.value)
        return f'{base}.{node.attr}' if base else node.attr
    return ''


def _inside_try(tree: ast.AST, target: ast.Call) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for inner in ast.walk(node):
                if inner is target:
                    return True
    return False
