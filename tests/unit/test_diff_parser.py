from pathlib import Path

from review_agent.diff_parser import extract_reviewable_added_lines


def test_extract_reviewable_added_lines_multi_hunk() -> None:
    patch = Path("examples/sample_diff.patch").read_text(encoding="utf-8")
    lines = extract_reviewable_added_lines(patch)

    assert lines == [2, 4, 5, 6, 23, 24, 25, 26]


def test_extract_reviewable_added_lines_empty_patch() -> None:
    assert extract_reviewable_added_lines("") == []
