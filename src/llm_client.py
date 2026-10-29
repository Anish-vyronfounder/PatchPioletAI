from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import NEBIUS_API_KEY, NEBIUS_BASE_URL, NEBIUS_MODEL, USE_MOCK_PROVIDER


class MockLLMClient:
    """A local provider that never claims to be a real model response."""

    def generate(self, *, source_code: str, traceback_text: str, user_prompt: str) -> dict[str, Any]:
        lowered_traceback = traceback_text.lower()
        if "zerodivisionerror" in lowered_traceback:
            diagnosis = "The supplied traceback reports division by zero."
        elif "indexerror" in lowered_traceback or "list index out of range" in lowered_traceback:
            diagnosis = "The supplied traceback reports an invalid sequence index."
        else:
            diagnosis = "Mock mode does not perform model-based code analysis."
        return {
            "provider": "mock",
            "status": "mock_mode",
            "diagnosis": diagnosis,
            "repair_plan": "A local rule-based proposal may be shown for supported traceback patterns; review it and run tests yourself.",
            "fixed_code": source_code,
            "confidence": None,
            "notes": "This is a local mock response for interface testing. It is not a real Nebius inference result.",
        }


class NebiusLLMClient:
    """OpenAI-compatible client for a verified Nebius endpoint if configured."""

    def __init__(self) -> None:
        self.api_key = NEBIUS_API_KEY or ""
        self.model = NEBIUS_MODEL
        self.base_url = NEBIUS_BASE_URL
        self._client: OpenAI | None = None

        if self.api_key:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=30.0,
                max_retries=1,
            )

    def generate(self, *, source_code: str, traceback_text: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key or self._client is None:
            raise RuntimeError("NEBIUS_API_KEY is not configured")

        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are PatchPilot AI, a careful Python debugging assistant. Return only a valid JSON object with string fields diagnosis, repair_plan, and fixed_code. Do not claim that a proposed patch was tested."},
                {"role": "user", "content": f"Source code:\n{source_code}\n\nTraceback:\n{traceback_text}\n\nUser prompt:\n{user_prompt}\n\nReturn only JSON."},
            ],
            temperature=0.2,
        )

        if not response.choices:
            raise ValueError("The model returned no response choices.")
        message = response.choices[0].message.content
        if not isinstance(message, str) or not message.strip():
            raise ValueError("The model returned an empty response.")
        try:
            parsed = json.loads(message)
        except json.JSONDecodeError:
            raise ValueError("The model returned malformed JSON.")

        if not isinstance(parsed, dict):
            raise ValueError("The model response was not a JSON object.")
        for field in ("diagnosis", "repair_plan", "fixed_code"):
            if not isinstance(parsed.get(field), str):
                raise ValueError(f"The model response is missing a valid '{field}' string.")

        return {
            "provider": "nebius",
            "status": "success",
            "diagnosis": parsed["diagnosis"],
            "repair_plan": parsed["repair_plan"],
            "fixed_code": parsed["fixed_code"],
            "confidence": None,
            "notes": "",
        }

    def test_connection(self) -> None:
        if not self.api_key or self._client is None:
            raise RuntimeError("NEBIUS_API_KEY is not configured")
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": "Reply with OK."}],
            max_tokens=8,
            temperature=0,
        )
        if not response.choices or not response.choices[0].message.content:
            raise ValueError("The model connection returned an empty response.")


def get_llm_client() -> MockLLMClient | NebiusLLMClient:
    if USE_MOCK_PROVIDER:
        return MockLLMClient()
    if not NEBIUS_API_KEY:
        raise RuntimeError(
            "Live inference is selected but NEBIUS_API_KEY is not configured. "
            "Set a key or enable USE_MOCK_PROVIDER."
        )
    return NebiusLLMClient()
