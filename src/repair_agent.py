from __future__ import annotations

from typing import Any

from .llm_client import get_llm_client
from .patch_utils import generate_unified_diff, infer_patch, validate_patch


def analyze_failure(source_code: str, traceback_text: str, user_prompt: str = "") -> dict[str, Any]:
    """Diagnose the failure and produce a minimal code patch proposal."""
    source_code = source_code or ""
    traceback_text = traceback_text or "No traceback provided."
    user_prompt = user_prompt or "Diagnose and repair the bug with a minimal patch."

    client = get_llm_client()
    result = client.generate(
        source_code=source_code,
        traceback_text=traceback_text,
        user_prompt=user_prompt,
    )

    fixed_code = result["fixed_code"]
    if result.get("provider") == "mock" and fixed_code == source_code:
        fixed_code = infer_patch(source_code, traceback_text)
    diagnosis = result.get("diagnosis") or "A likely defect was found in the code path that raised the error."
    repair_plan = result.get("repair_plan") or "Add safety checks around the failing operation and retest."

    if not isinstance(fixed_code, str):
        raise ValueError("The generated patch is not text.")
    if fixed_code != source_code and not validate_patch(source_code, fixed_code):
        raise ValueError("The generated patch is empty or invalid.")

    diff = generate_unified_diff(source_code, fixed_code)

    return {
        "provider": result.get("provider", "local"),
        "status": result.get("status", "local"),
        "diagnosis": diagnosis,
        "repair_plan": repair_plan,
        "fixed_code": fixed_code,
        "diff": diff,
        "confidence": None,
        "notes": result.get("notes", ""),
    }
