from __future__ import annotations

import difflib
import re
from typing import Iterable


def generate_unified_diff(before: str, after: str, fromfile: str = "before.py", tofile: str = "after.py") -> str:
    """Generate a unified diff for a before/after code sample."""
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=fromfile,
        tofile=tofile,
        lineterm="",
    )
    return "\n".join(diff)


def _replace_zero_division(code: str) -> str:
    if "/" not in code:
        return code

    return_pattern = r"return\s+([^\n]*?)\s*/\s*([^\n]+)"
    if re.search(return_pattern, code):
        return re.sub(
            return_pattern,
            r"return \1 / \2 if \2 != 0 else 0",
            code,
        )

    assign_pattern = r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\n]*?)\s*/\s*([^\n]+)"
    if re.search(assign_pattern, code):
        return re.sub(
            assign_pattern,
            r"\1 = \2 / \3 if \3 != 0 else 0",
            code,
        )

    return code


def _replace_index_issue(code: str) -> str:
    if "IndexError" not in code and "list index" not in code:
        return code

    for match in re.finditer(r"(\w+)\[(\w+)\]", code):
        var_name = match.group(1)
        index_name = match.group(2)
        before = match.group(0)
        after = f"{var_name}[{index_name}] if 0 <= {index_name} < len({var_name}) else None"
        code = code.replace(before, after)
    return code


def infer_patch(source_code: str, traceback_text: str) -> str:
    """Apply a narrow, rule-based fix for common beginner defects."""
    updated = source_code
    lower_trace = traceback_text.lower()
    if "zerodivisionerror" in lower_trace:
        updated = _replace_zero_division(updated)
    if "indexerror" in lower_trace or "list index out of range" in lower_trace:
        updated = _replace_index_issue(updated)
    if "typeerror" in lower_trace and "int" in lower_trace and "str" in lower_trace:
        updated = updated.replace("input(", "int(input(")
    return updated


def validate_patch(before: str, after: str) -> bool:
    return bool(after.strip()) and after != before


def normalize_code(raw: str) -> str:
    return raw.strip() + ("\n" if raw.strip() else "")
