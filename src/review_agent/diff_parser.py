from unidiff import PatchSet


def extract_reviewable_added_lines(patch: str) -> list[int]:
    if not patch.strip():
        return []

    patch_set = PatchSet(patch)
    added_lines: list[int] = []
    for patched_file in patch_set:
        for hunk in patched_file:
            for line in hunk:
                if line.is_added and line.target_line_no is not None:
                    added_lines.append(int(line.target_line_no))
    return sorted(set(added_lines))
