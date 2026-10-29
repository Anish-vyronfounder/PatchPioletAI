from src.patch_utils import generate_unified_diff, infer_patch, validate_patch


def test_generate_unified_diff_contains_markers():
    before = "print('hi')\n"
    after = "print('hello')\n"
    diff = generate_unified_diff(before, after)
    assert "--- before.py" in diff
    assert "+++ after.py" in diff
    assert "-print('hi')" in diff or "+print('hello')" in diff


def test_infer_patch_handles_zero_division():
    source = "def divide(a, b):\n    return a / b\n"
    traceback = "ZeroDivisionError: division by zero"
    fixed = infer_patch(source, traceback)
    assert "if b != 0" in fixed or "0 else 0" in fixed


def test_validate_patch_rejects_no_change():
    assert validate_patch("same", "same") is False
    assert validate_patch("before", "after") is True
