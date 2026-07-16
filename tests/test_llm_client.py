from __future__ import annotations

import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

import src.llm_client as llm_client
from src.llm_client import (
    LLMClient,
    _create_chat_completion_with_fallback,
    _max_token_parameter,
    _supports_reasoning_effort,
    normalize_model_name,
    resolve_api_key,
)


def test_llm_client_construction_does_not_expose_keys(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "load_env_files", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "secret-openai")

    client = LLMClient(provider="openai", model="gpt-4o-mini")

    assert "secret-openai" not in repr(client)
    assert client.provider == "openai"
    assert normalize_model_name("openai/gpt-4o-mini", "openai") == "gpt-4o-mini"


def test_provider_selection_for_openai_and_moonshot(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "load_env_files", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("MOONSHOT_API_KEY", "moonshot-key")

    assert resolve_api_key("openai") == "openai-key"
    assert resolve_api_key("moonshot") == "moonshot-key"
    assert normalize_model_name("moonshot/moonshot-v1-8k", "moonshot") == "moonshot-v1-8k"


def test_moonshot_key_fallback_prefers_moonshot_then_kimi(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "load_env_files", lambda: None)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.setenv("KIMI_API_KEY", "kimi-key")

    assert resolve_api_key("moonshot") == "kimi-key"

    monkeypatch.setenv("MOONSHOT_API_KEY", "moonshot-key")

    assert resolve_api_key("moonshot") == "moonshot-key"


def test_openai_gpt5_uses_max_completion_tokens() -> None:
    assert _max_token_parameter("openai", "gpt-5-mini") == "max_completion_tokens"
    assert _max_token_parameter("openai", "gpt-4o-mini") == "max_tokens"


def test_reasoning_effort_support_is_limited_to_reasoning_models() -> None:
    assert _supports_reasoning_effort("gpt-5-mini") is True
    assert _supports_reasoning_effort("o3-mini") is True
    assert _supports_reasoning_effort("gpt-4o-mini") is False


def test_reasoning_effort_fallback_removes_unsupported_parameter() -> None:
    class FakeCompletions:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if "reasoning_effort" in kwargs:
                raise TypeError("unexpected keyword argument 'reasoning_effort'")
            return {"ok": True}

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self) -> None:
            self.chat = FakeChat()

    client = FakeClient()
    result = _create_chat_completion_with_fallback(
        client,
        {
            "model": "gpt-5-mini",
            "messages": [],
            "max_completion_tokens": 16,
            "reasoning_effort": "low",
        },
    )

    assert result == {"ok": True}
    assert "reasoning_effort" in client.chat.completions.calls[0]
    assert "reasoning_effort" not in client.chat.completions.calls[1]
