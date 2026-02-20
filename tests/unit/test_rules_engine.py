from review_agent.models import ChangedFile
from review_agent.rules_engine import RulesEngine


def _build_engine() -> RulesEngine:
    return RulesEngine.from_yaml('config/coding_standards.yaml')


def test_rules_engine_covers_all_baseline_categories() -> None:
    changed_files = [
        ChangedFile(
            file_path='src/security.py',
            status='modified',
            content='''
api_key = "abc123"
exec(user_input)
''',
        ),
        ChangedFile(
            file_path='src/quality.py',
            status='modified',
            content='''
def choose(flag):
    if flag and cond_a and cond_b and cond_c:
        return 1
    else:
        return 1
''',
        ),
        ChangedFile(
            file_path='src/style.py',
            status='modified',
            content='''
camelCaseVar = 1
very_long_line = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
''',
        ),
        ChangedFile(
            file_path='src/best.py',
            status='modified',
            content='''
def load_file(path):
    data = open(path).read()
    return data
''',
        ),
    ]

    findings = _build_engine().analyze_files(changed_files)
    rule_ids = {f.rule_id for f in findings}

    assert 'STYLE_LINE_LENGTH' in rule_ids
    assert 'STYLE_NAMING_CONVENTION' in rule_ids
    assert 'QUALITY_DUPLICATED_BRANCH_LOGIC' in rule_ids
    assert 'QUALITY_COMPLEX_CONDITIONAL' in rule_ids
    assert 'SECURITY_HARDCODED_SECRET' in rule_ids
    assert 'SECURITY_UNSAFE_EXEC' in rule_ids
    assert 'BP_MISSING_ERROR_HANDLING' in rule_ids


def test_rules_engine_is_deterministic_and_deduplicated() -> None:
    changed_files = [
        ChangedFile(
            file_path='src/repeat.py',
            status='modified',
            content='''
token = "x"
token = "x"
''',
        )
    ]

    engine = _build_engine()
    first = engine.analyze_files(changed_files)
    second = engine.analyze_files(changed_files)

    assert [f.model_dump() for f in first] == [f.model_dump() for f in second]
    security_findings = [f for f in first if f.rule_id == 'SECURITY_HARDCODED_SECRET']
    assert len(security_findings) == 2


def test_findings_have_normalized_confidence_range() -> None:
    changed_files = [
        ChangedFile(
            file_path='src/security.py',
            status='modified',
            content='api_key = "abc123"\n',
        )
    ]

    findings = _build_engine().analyze_files(changed_files)
    assert findings
    for finding in findings:
        assert 0.0 <= finding.confidence <= 1.0


def test_static_findings_include_docs_ref_and_reasoning() -> None:
    changed_files = [
        ChangedFile(
            file_path="src/security.py",
            status="modified",
            content='api_key = "abc123"\n',
        )
    ]

    findings = _build_engine().analyze_files(changed_files)
    target = next(f for f in findings if f.rule_id == "SECURITY_HARDCODED_SECRET")
    assert target.docs_ref == "OWASP-A02"
    assert target.reasoning is not None
    assert "Regex detector matched" in target.reasoning
