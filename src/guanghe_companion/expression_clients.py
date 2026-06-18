from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from .expression_settings import ExpressionSettings, provider_api_key_required, provider_api_style

LLMClient = Callable[[str], str]
HTTPTransport = Callable[[request.Request, float], bytes]
DEFAULT_TIMEOUT_SECONDS = 2.0
MAX_TIMEOUT_SECONDS = 60.0
DEFAULT_OPENAI_MODEL = "gpt-5.5"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_OPENAI_API_KEY_LENGTH = 512
MAX_OPENAI_MODEL_LENGTH = 80
MAX_OPENAI_BASE_URL_LENGTH = 240
MAX_OPENAI_PROMPT_LENGTH = 8192
MAX_OPENAI_RESPONSE_BYTES = 65_536
MAX_OPENAI_RESPONSE_TEXT_LENGTH = 4096
DEFAULT_CHAT_COMPLETION_MAX_TOKENS = 512
JSON_RESPONSE_PROVIDERS = frozenset({"deepseek"})


class LLMProviderError(RuntimeError):
    def __init__(self, message: str, *, public_reason: str | None = None) -> None:
        super().__init__(message)
        self.public_reason = public_reason or _public_reason_from_message(message)


@dataclass(frozen=True, slots=True)
class ExpressionClientConfig:
    client: LLMClient | None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    enabled: bool = False


@dataclass(frozen=True, slots=True)
class _OpenAIProviderConfig:
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float


class OpenAIResponsesClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        base_url: str = OPENAI_RESPONSES_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: HTTPTransport | None = None,
    ) -> None:
        self.api_key = _normalize_api_key(api_key)
        self.model = _normalize_model(model)
        self.base_url = _normalize_base_url(base_url)
        self.timeout_seconds = _normalize_timeout(timeout_seconds)
        self.transport = transport or _default_transport
        self._closed = False

    def __enter__(self) -> "OpenAIResponsesClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def __call__(self, prompt: str) -> str:
        if self._closed:
            raise _provider_error("OpenAI expression provider failed", "closed")
        if not self.api_key:
            raise _provider_error("OpenAI expression provider failed", "missing_api_key")
        if not isinstance(prompt, str):
            raise _provider_error("OpenAI expression provider failed", "invalid_prompt")
        if not prompt.strip():
            raise _provider_error("OpenAI expression provider failed", "invalid_prompt")
        if len(prompt) > MAX_OPENAI_PROMPT_LENGTH:
            raise _provider_error("OpenAI expression provider failed", "invalid_prompt")
        payload = json.dumps(
            {
                "model": self.model,
                "input": prompt,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        api_request = request.Request(
            self.base_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            raw = self.transport(api_request, self.timeout_seconds)
            if not isinstance(raw, (bytes, bytearray)):
                raise _provider_error("OpenAI expression provider failed", "invalid_response_bytes")
            if len(raw) > MAX_OPENAI_RESPONSE_BYTES:
                raise _provider_error("OpenAI expression provider failed", "invalid_response_size")
            try:
                decoded = bytes(raw).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise _provider_error("OpenAI expression provider failed", "invalid_response_encoding") from exc
            try:
                response = json.loads(decoded)
            except json.JSONDecodeError as exc:
                raise _provider_error("OpenAI expression provider failed", "invalid_response_json") from exc
            if not isinstance(response, dict):
                raise _provider_error("OpenAI expression provider failed", "invalid_response_shape")
            try:
                return _extract_response_text(response)
            except ValueError as exc:
                raise _provider_error("OpenAI expression provider failed", "invalid_response_text") from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            raise _provider_error_from_exception("OpenAI expression provider failed", exc) from exc

    def close(self) -> None:
        self._closed = True


class OpenAICompatibleChatClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: HTTPTransport | None = None,
        require_api_key: bool = True,
        json_response: bool = False,
        max_tokens: int | None = None,
    ) -> None:
        self.api_key = _normalize_api_key(api_key)
        self.model = _normalize_model(model)
        self.base_url = _normalize_base_url(base_url)
        self.timeout_seconds = _normalize_timeout(timeout_seconds)
        self.transport = transport or _default_transport
        self.require_api_key = bool(require_api_key)
        self.json_response = bool(json_response)
        self.max_tokens = _normalize_max_tokens(max_tokens)
        self._closed = False

    def __enter__(self) -> "OpenAICompatibleChatClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def __call__(self, prompt: str) -> str:
        if self._closed:
            raise _provider_error("OpenAI-compatible expression provider failed", "closed")
        if self.require_api_key and not self.api_key:
            raise _provider_error("OpenAI-compatible expression provider failed", "missing_api_key")
        if not isinstance(prompt, str):
            raise _provider_error("OpenAI-compatible expression provider failed", "invalid_prompt")
        if not prompt.strip():
            raise _provider_error("OpenAI-compatible expression provider failed", "invalid_prompt")
        if len(prompt) > MAX_OPENAI_PROMPT_LENGTH:
            raise _provider_error("OpenAI-compatible expression provider failed", "invalid_prompt")
        payload_dict: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.json_response:
            payload_dict["response_format"] = {"type": "json_object"}
        if self.max_tokens is not None:
            payload_dict["max_tokens"] = self.max_tokens
        payload = json.dumps(payload_dict, ensure_ascii=False).encode("utf-8")
        api_request = request.Request(
            _chat_completions_url(self.base_url),
            data=payload,
            headers=_json_request_headers(self.api_key),
            method="POST",
        )
        try:
            raw = self.transport(api_request, self.timeout_seconds)
            if not isinstance(raw, (bytes, bytearray)):
                raise _provider_error("OpenAI-compatible expression provider failed", "invalid_response_bytes")
            if len(raw) > MAX_OPENAI_RESPONSE_BYTES:
                raise _provider_error("OpenAI-compatible expression provider failed", "invalid_response_size")
            try:
                decoded = bytes(raw).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise _provider_error("OpenAI-compatible expression provider failed", "invalid_response_encoding") from exc
            try:
                response = json.loads(decoded)
            except json.JSONDecodeError as exc:
                raise _provider_error("OpenAI-compatible expression provider failed", "invalid_response_json") from exc
            if not isinstance(response, dict):
                raise _provider_error("OpenAI-compatible expression provider failed", "invalid_response_shape")
            try:
                return _extract_chat_completion_text(response)
            except ValueError as exc:
                raise _provider_error("OpenAI-compatible expression provider failed", "invalid_response_text") from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            raise _provider_error_from_exception("OpenAI-compatible expression provider failed", exc) from exc

    def close(self) -> None:
        self._closed = True


def fetch_provider_model_ids(
    *,
    provider: str,
    base_url: str,
    api_key: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    transport: HTTPTransport | None = None,
) -> tuple[str, ...]:
    normalized_api_key = _normalize_api_key(api_key)
    if provider_api_key_required(provider) and not normalized_api_key:
        raise _provider_error("model list fetch failed", "missing_api_key")
    normalized_base_url = _normalize_base_url(base_url)
    api_request = request.Request(
        _models_url(normalized_base_url),
        headers=_json_request_headers(normalized_api_key),
        method="GET",
    )
    try:
        raw = (transport or _default_transport)(api_request, _normalize_timeout(timeout_seconds))
        if not isinstance(raw, (bytes, bytearray)):
            raise _provider_error("model list fetch failed", "invalid_response_bytes")
        if len(raw) > MAX_OPENAI_RESPONSE_BYTES:
            raise _provider_error("model list fetch failed", "invalid_response_size")
        response = json.loads(bytes(raw).decode("utf-8"))
    except LLMProviderError:
        raise
    except UnicodeDecodeError as exc:
        raise _provider_error("model list fetch failed", "invalid_response_encoding") from exc
    except json.JSONDecodeError as exc:
        raise _provider_error("model list fetch failed", "invalid_response_json") from exc
    except Exception as exc:
        raise _provider_error_from_exception("model list fetch failed", exc) from exc
    if not isinstance(response, dict):
        raise _provider_error("model list fetch failed", "invalid_response_shape")
    data = response.get("data")
    if not isinstance(data, list):
        raise _provider_error("model list fetch failed", "invalid_response_shape")
    models: list[str] = []
    seen: set[str] = set()
    for entry in data:
        if not isinstance(entry, dict):
            continue
        model_id = _short_string(entry.get("id", ""), 160)
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        models.append(model_id)
        if len(models) >= 200:
            break
    if not models:
        raise _provider_error("model list fetch failed", "empty_model_list")
    return tuple(models)


def client_config_from_env(env: Mapping[str, object] | None = None) -> ExpressionClientConfig:
    config = _openai_config_from_env(env)
    if config is None:
        return ExpressionClientConfig(client=None)
    return ExpressionClientConfig(
        client=OpenAIResponsesClient(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
        ),
        timeout_seconds=config.timeout_seconds,
        enabled=True,
    )


def client_config_from_settings(settings: ExpressionSettings) -> ExpressionClientConfig:
    require_api_key = provider_api_key_required(settings.provider)
    if not settings.enabled or (require_api_key and not settings.api_key):
        return ExpressionClientConfig(client=None)
    if provider_api_style(settings.provider) == "responses":
        client: LLMClient = OpenAIResponsesClient(
            api_key=settings.api_key,
            model=settings.model,
            base_url=settings.base_url,
            timeout_seconds=settings.timeout_seconds,
        )
    else:
        client = OpenAICompatibleChatClient(
            api_key=settings.api_key,
            model=settings.model,
            base_url=settings.base_url,
            timeout_seconds=settings.timeout_seconds,
            require_api_key=require_api_key,
            json_response=_provider_uses_json_response(settings.provider),
            max_tokens=DEFAULT_CHAT_COMPLETION_MAX_TOKENS if _provider_uses_json_response(settings.provider) else None,
        )
    return ExpressionClientConfig(
        client=client,
        timeout_seconds=settings.timeout_seconds,
        enabled=True,
    )


def _openai_config_from_env(env: Mapping[str, object] | None = None) -> _OpenAIProviderConfig | None:
    if env is not None and not isinstance(env, Mapping):
        return None
    source = os.environ if env is None else env
    enabled_flag = source.get("GUANGHE_LLM_ENABLED")
    if not isinstance(enabled_flag, str) or _has_control_character(enabled_flag) or enabled_flag.strip() != "1":
        return None
    api_key = _normalize_api_key(source.get("OPENAI_API_KEY"))
    if not api_key:
        return None
    return _OpenAIProviderConfig(
        api_key=api_key,
        model=_normalize_model(source.get("GUANGHE_LLM_MODEL")),
        base_url=_normalize_base_url(source.get("GUANGHE_LLM_BASE_URL")),
        timeout_seconds=_parse_timeout(source.get("GUANGHE_LLM_TIMEOUT_SECONDS")),
    )


def _default_transport(api_request: request.Request, timeout: float) -> bytes:
    with request.urlopen(api_request, timeout=timeout) as response:
        return response.read()


def _provider_error(prefix: str, public_reason: str) -> LLMProviderError:
    return LLMProviderError(f"{prefix}: {public_reason}", public_reason=public_reason)


def _provider_error_from_exception(prefix: str, exc: Exception) -> LLMProviderError:
    return _provider_error(prefix, _public_reason_from_exception(exc))


def _public_reason_from_exception(exc: Exception) -> str:
    if isinstance(exc, error.HTTPError):
        return f"http_{exc.code}"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError):
            return "timeout"
        return "network_error"
    return "provider_error"


def _public_reason_from_message(message: str) -> str:
    if ":" not in message:
        return "provider_error"
    reason = message.rsplit(":", 1)[-1].strip()
    return reason if reason else "provider_error"


def _json_request_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _extract_response_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return _validated_response_text(output_text)
    output = response.get("output")
    if not isinstance(output, list):
        raise ValueError("OpenAI response does not include output.")
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "output_text" and isinstance(part.get("text"), str) and str(part["text"]).strip():
                return _validated_response_text(str(part["text"]))
    raise ValueError("OpenAI response does not include output text.")


def _extract_chat_completion_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list):
        raise ValueError("Chat completion response does not include choices.")
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return _validated_response_text(content)
    raise ValueError("Chat completion response does not include message content.")


def _chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/responses"):
        return base[: -len("/responses")] + "/chat/completions"
    return f"{base}/chat/completions"


def _models_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    for suffix in ("/chat/completions", "/responses"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return f"{base}/models"


def _validated_response_text(value: str) -> str:
    text = value.strip()
    if len(text) > MAX_OPENAI_RESPONSE_TEXT_LENGTH:
        raise ValueError("OpenAI response text is too long.")
    return text


def _parse_timeout(value: str | None) -> float:
    if value is None:
        return DEFAULT_TIMEOUT_SECONDS
    if isinstance(value, str) and _has_control_character(value):
        return DEFAULT_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS
    return _normalize_timeout(parsed)


def _normalize_timeout(value: object) -> float:
    if isinstance(value, str) and _has_control_character(value):
        return DEFAULT_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS
    return parsed if math.isfinite(parsed) and 0 < parsed <= MAX_TIMEOUT_SECONDS else DEFAULT_TIMEOUT_SECONDS


def _normalize_max_tokens(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if 1 <= parsed <= 4096 else None


def _provider_uses_json_response(provider: str) -> bool:
    return provider in JSON_RESPONSE_PROVIDERS


def _normalize_model(value: object) -> str:
    if not isinstance(value, str):
        return DEFAULT_OPENAI_MODEL
    model = value.strip()
    if not model or len(model) > MAX_OPENAI_MODEL_LENGTH or _has_control_character(model):
        return DEFAULT_OPENAI_MODEL
    return model


def _normalize_base_url(value: object) -> str:
    if not isinstance(value, str):
        return OPENAI_RESPONSES_URL
    base_url = value.strip()
    if (
        not base_url
        or len(base_url) > MAX_OPENAI_BASE_URL_LENGTH
        or _has_control_character(base_url)
        or not base_url.startswith(("https://", "http://"))
    ):
        return OPENAI_RESPONSES_URL
    return base_url


def _normalize_api_key(value: object) -> str:
    if not isinstance(value, str):
        return ""
    api_key = value.strip()
    if not api_key or len(api_key) > MAX_OPENAI_API_KEY_LENGTH or _has_control_character(api_key):
        return ""
    return api_key


def _short_string(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return _replace_control_characters(value.strip())[:max_length]


def _replace_control_characters(value: str) -> str:
    return "".join(" " if _is_control_character(char) else char for char in value)


def _has_control_character(value: str) -> bool:
    return any(_is_control_character(char) for char in value)


def _is_control_character(char: str) -> bool:
    return ord(char) < 32 or ord(char) == 127
