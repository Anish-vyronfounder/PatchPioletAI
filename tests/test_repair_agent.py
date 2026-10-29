from src.repair_agent import analyze_failure


def test_analyze_failure_returns_expected_fields(monkeypatch):
    import src.llm_client as llm_client

    monkeypatch.setattr(llm_client, "USE_MOCK_PROVIDER", True)
    source = "def divide(a, b):\n    return a / b\n"
    traceback = "Traceback (most recent call last):\nZeroDivisionError: division by zero"

    result = analyze_failure(source, traceback, "Fix this bug.")
    assert set(result.keys()) >= {"provider", "status", "diagnosis", "repair_plan", "fixed_code", "diff", "confidence"}
    assert isinstance(result["diagnosis"], str)
    assert isinstance(result["repair_plan"], str)
    assert isinstance(result["diff"], str)
    assert result["provider"] == "mock"
    assert result["confidence"] is None
    assert result["fixed_code"] != source


def test_analyze_failure_does_not_hide_provider_errors(monkeypatch):
    import pytest
    import src.repair_agent as repair_agent

    class BrokenClient:
        def generate(self, **_kwargs):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(repair_agent, "get_llm_client", lambda: BrokenClient())
    with pytest.raises(RuntimeError, match="provider unavailable"):
        analyze_failure("print('hello')\n", "", "")
