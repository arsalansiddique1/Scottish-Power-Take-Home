import re

from unidiff import PatchSet
from unidiff.errors import UnidiffParseError


def extract_reviewable_added_lines(patch: str) -> list[int]:
    if not patch.strip():
        return []

    try:
        patch_set = PatchSet(patch)
        added_lines: list[int] = []
        for patched_file in patch_set:
            for hunk in patched_file:
                for line in hunk:
                    if line.is_added and line.target_line_no is not None:
                        added_lines.append(int(line.target_line_no))
        return sorted(set(added_lines))
    except UnidiffParseError:
        # GitHub can return hunk-only patches (for example, some deleted files).
        # Fall back to a lightweight parser and return only reviewable added lines.
        return _extract_added_lines_from_hunk_only_patch(patch)


def _extract_added_lines_from_hunk_only_patch(patch: str) -> list[int]:
    header_re = re.compile(r"^@@\s*-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s*@@")
    current_target: int | None = None
    added_lines: list[int] = []

    for raw_line in patch.splitlines():
        header_match = header_re.match(raw_line)
        if header_match:
            current_target = int(header_match.group(1))
            continue

        if current_target is None:
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            added_lines.append(current_target)
            current_target += 1
            continue

        if raw_line.startswith("-") and not raw_line.startswith("---"):
            continue

        if raw_line.startswith("\\ No newline"):
            continue

        current_target += 1

    return sorted(set(added_lines))
