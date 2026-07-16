"""OpenAI-compatible LLM client for the feedback efficiency harness."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import EXPERIMENT_ROOT, HEURIGYM_PIPELINE_ROOT, ORTHOUGHT_ROOT, REPO_ROOT
from .cost_logging import append_cost_usage_row, build_cost_usage_row


LOGGER = logging.getLogger(__name__)


PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "openai": {
        "base_url": None,
        "env_vars": ("OPENAI_API_KEY",),
    },
    "moonshot": {
        "base_url": "https://api.moonshot.ai/v1",
        "env_vars": ("MOONSHOT_API_KEY", "KIMI_API_KEY"),
    },
}


class LLMError(RuntimeError):
    """Raised when an LLM request cannot be completed."""


@dataclass(frozen=True, slots=True)
class LLMClient:
    provider: str
    model: str
    request_timeout_seconds: int = 45
    max_retries: int = 0
    temperature: float | None = None
    max_tokens: int = 512
    thinking: str = "default"
    reasoning_effort: str | None = None

    def __post_init__(self) -> None:
        provider = self.provider.lower()
        if provider not in PROVIDER_CONFIG:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
        thinking = self.thinking.lower()
        if thinking not in {"default", "disabled", "enabled"}:
            raise ValueError("thinking must be one of: default, disabled, enabled")
        if self.reasoning_effort is not None:
            reasoning_effort = self.reasoning_effort.lower()
            if reasoning_effort not in {"minimal", "low", "medium", "high"}:
                raise ValueError("reasoning_effort must be one of: minimal, low, medium, high")
            object.__setattr__(self, "reasoning_effort", reasoning_effort)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "thinking", thinking)

    def chat(self, messages: list[dict]) -> str:
        return str(self.chat_with_metadata(messages)["text"])

    def chat_with_metadata(self, messages: list[dict]) -> dict[str, Any]:
        load_env_files()
        api_key = resolve_api_key(self.provider)
        if not api_key:
            names = ", ".join(PROVIDER_CONFIG[self.provider]["env_vars"])
            raise LLMError(f"Missing API key for provider={self.provider}. Expected env var: {names}.")

        model = normalize_model_name(self.model, self.provider)
        prompt_char_count = _message_char_count(messages)
        max_token_parameter = _max_token_parameter(self.provider, model)
        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            max_token_parameter: self.max_tokens,
        }
        sends_temperature = self.temperature is not None
        if sends_temperature:
            request_kwargs["temperature"] = self.temperature
        if self.reasoning_effort is not None and self.provider == "openai" and _supports_reasoning_effort(model):
            request_kwargs["reasoning_effort"] = self.reasoning_effort

        extra_body = self._extra_body_for(model)
        if extra_body is not None:
            request_kwargs["extra_body"] = extra_body

        LOGGER.info(
            (
                "LLM request provider=%s model=%s max_tokens=%s timeout=%ss "
                "max_retries=%s sends_temperature=%s thinking=%s reasoning_effort=%s prompt_chars=%s"
            ),
            self.provider,
            model,
            self.max_tokens,
            self.request_timeout_seconds,
            self.max_retries,
            sends_temperature,
            self.thinking,
            self.reasoning_effort,
            prompt_char_count,
        )

        started = time.monotonic()
        try:
            from openai import OpenAI

            client_kwargs: dict[str, Any] = {
                "api_key": api_key,
                "timeout": self.request_timeout_seconds,
                "max_retries": self.max_retries,
            }
            base_url = PROVIDER_CONFIG[self.provider]["base_url"]
            if base_url is not None:
                client_kwargs["base_url"] = base_url

            client = OpenAI(**client_kwargs)
            response = _create_chat_completion_with_fallback(client, request_kwargs)
            text, response_debug = _extract_response_text_and_debug(response)
            _log_cost_usage(
                provider=self.provider,
                model=model,
                usage=getattr(response, "usage", None),
                success=True,
                response_id=str(getattr(response, "id", "") or ""),
            )
        except Exception as exc:
            _log_cost_usage(
                provider=self.provider,
                model=model,
                usage=None,
                success=False,
                error_type=exc.__class__.__name__,
                notes="LLM request failed",
            )
            raise LLMError(
                f"LLM request failed provider={self.provider} model={model} "
                f"error={exc.__class__.__name__}: {exc}"
            ) from exc

        elapsed = time.monotonic() - started
        LOGGER.info(
            "LLM response provider=%s model=%s response_chars=%s elapsed_seconds=%.3f",
            self.provider,
            model,
            len(text),
            elapsed,
        )
        return {
            "text": text,
            "provider": self.provider,
            "model": model,
            "prompt_char_count": prompt_char_count,
            "max_tokens": self.max_tokens,
            "max_token_parameter": max_token_parameter,
            "reasoning_effort": self.reasoning_effort,
            "elapsed_seconds": elapsed,
            **response_debug,
        }

    def complete(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])

    def _extra_body_for(self, model: str) -> dict[str, Any] | None:
        if self.provider != "moonshot":
            return None
        lowered = model.lower()
        if not (lowered.startswith("kimi-k2.5") or lowered.startswith("kimi-k2.6")):
            return None
        if self.thinking == "disabled":
            return {"thinking": {"type": "disabled"}}
        if self.thinking == "enabled":
            return {"thinking": {"type": "enabled"}}
        return None


OpenAICompatibleClient = LLMClient


def normalize_model_name(model: str, provider: str) -> str:
    provider = provider.lower()
    lowered = model.lower()
    prefixes = {
        "openai": ("openai/",),
        "moonshot": ("moonshot/", "kimi/"),
    }.get(provider, ())
    for prefix in prefixes:
        if lowered.startswith(prefix):
            return model.split("/", 1)[1]
    return model


def _max_token_parameter(provider: str, model: str) -> str:
    lowered = model.lower()
    if provider == "openai" and (lowered.startswith("gpt-5") or lowered.startswith("o")):
        return "max_completion_tokens"
    return "max_tokens"


def _supports_reasoning_effort(model: str) -> bool:
    lowered = model.lower()
    return lowered.startswith("gpt-5") or lowered.startswith("o")


def _create_chat_completion_with_fallback(client: Any, request_kwargs: dict[str, Any]) -> Any:
    try:
        return client.chat.completions.create(**request_kwargs)
    except Exception as exc:
        message = str(exc).lower()
        fallback_kwargs = dict(request_kwargs)
        changed = False
        if "max_tokens" in message and "max_tokens" in fallback_kwargs:
            fallback_kwargs["max_completion_tokens"] = fallback_kwargs.pop("max_tokens")
            changed = True
        if "temperature" in message and "temperature" in fallback_kwargs:
            fallback_kwargs.pop("temperature", None)
            changed = True
        if "reasoning_effort" in message and "reasoning_effort" in fallback_kwargs:
            fallback_kwargs.pop("reasoning_effort", None)
            changed = True
        if not changed:
            raise
        return client.chat.completions.create(**fallback_kwargs)


def _extract_response_text_and_debug(response: Any) -> tuple[str, dict[str, Any]]:
    choice = response.choices[0] if getattr(response, "choices", None) else None
    message = getattr(choice, "message", None) if choice is not None else None
    text = str(getattr(message, "content", "") or "")
    message_dump = _safe_model_dump(message)
    response_dump = _safe_model_dump(response)
    usage_debug = _usage_debug(getattr(response, "usage", None))
    content_candidates = _content_candidates(message_dump)
    response_content_candidates = _content_candidates(response_dump)
    nonstandard_content_fields = [
        key for key, value in content_candidates.items() if key != "content" and bool(value)
    ]
    response_nonstandard_content_fields = [
        key for key, value in response_content_candidates.items() if bool(value)
    ]
    debug = {
        "response_id": str(getattr(response, "id", "") or ""),
        "finish_reason": getattr(choice, "finish_reason", None) if choice is not None else None,
        "raw_response_repr": _truncate_repr(response),
        "message_content_chars": len(text),
        "message_has_content": bool(text),
        "nonstandard_content_fields": nonstandard_content_fields,
        "nonstandard_content_present": bool(nonstandard_content_fields),
        "response_nonstandard_content_fields": response_nonstandard_content_fields,
        "response_nonstandard_content_present": bool(response_nonstandard_content_fields),
        **usage_debug,
    }
    if not text:
        for key in nonstandard_content_fields:
            candidate = content_candidates.get(key)
            if isinstance(candidate, str):
                text = candidate
                debug["text_extraction_path"] = key
                break
        else:
            for key in response_nonstandard_content_fields:
                candidate = response_content_candidates.get(key)
                if isinstance(candidate, str):
                    text = candidate
                    debug["text_extraction_path"] = f"response.{key}"
                    break
            else:
                debug["text_extraction_path"] = "message.content"
    else:
        debug["text_extraction_path"] = "message.content"
    return text, debug


def _safe_model_dump(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        try:
            payload = value.model_dump()
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}
    if isinstance(value, dict):
        return dict(value)
    return {}


def _content_candidates(message_dump: dict[str, Any]) -> dict[str, Any]:
    candidates: dict[str, Any] = {}
    for key in ("content", "refusal", "reasoning", "reasoning_content", "output_text", "text"):
        if key in message_dump:
            candidates[key] = message_dump.get(key)
    return candidates


def _usage_debug(usage: Any) -> dict[str, Any]:
    payload = _safe_model_dump(usage)
    completion_details = payload.get("completion_tokens_details")
    if not isinstance(completion_details, dict):
        completion_details = {}
    prompt_details = payload.get("prompt_tokens_details")
    if not isinstance(prompt_details, dict):
        prompt_details = {}
    return {
        "prompt_tokens": payload.get("prompt_tokens"),
        "completion_tokens": payload.get("completion_tokens"),
        "total_tokens": payload.get("total_tokens"),
        "reasoning_tokens": completion_details.get("reasoning_tokens"),
        "cached_tokens": prompt_details.get("cached_tokens"),
    }


def _truncate_repr(value: Any, limit: int = 4000) -> str:
    text = repr(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def resolve_api_key(provider: str) -> str:
    provider = provider.lower()
    if provider not in PROVIDER_CONFIG:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    load_env_files()
    for name in PROVIDER_CONFIG[provider]["env_vars"]:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def load_env_files() -> None:
    for env_path in env_paths():
        if env_path.is_file():
            _load_one_env_file(env_path)


def env_paths() -> tuple[Path, ...]:
    return (
        EXPERIMENT_ROOT / ".env",
        REPO_ROOT / ".env",
        ORTHOUGHT_ROOT / ".env",
        HEURIGYM_PIPELINE_ROOT / ".env",
    )


def _load_one_env_file(path: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        _simple_load_dotenv(path)
        return
    load_dotenv(path, override=False)


def _simple_load_dotenv(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip("\"'")


def _message_char_count(messages: list[dict]) -> int:
    total = 0
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str):
            total += len(content)
        else:
            total += len(str(content))
    return total


def _log_cost_usage(
    *,
    provider: str,
    model: str,
    usage: Any,
    success: bool,
    response_id: str | None = None,
    error_type: str | None = None,
    notes: str | None = None,
) -> None:
    csv_path = os.environ.get("COST_USAGE_CSV", "").strip()
    if not csv_path:
        return
    try:
        row = build_cost_usage_row(
            provider=provider,
            model=model,
            usage=usage,
            success=success,
            response_id=response_id,
            error_type=error_type,
            notes=notes,
        )
        append_cost_usage_row(csv_path, row)
    except Exception:
        LOGGER.exception("Failed to append cost usage row")
