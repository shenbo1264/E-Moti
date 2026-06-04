from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any
from urllib import request

from .engine import create_initial_state
from .events import build_fallback_events, validate_events
from .expression_parser import (
    ExpressionPayloadError,
    normalize_expression_event,
    parse_shinsekai_object_stream,
    stringify_event,
)
from .expression_request import (
    MAX_CHARACTER_NAME_LENGTH,
    MAX_FEEDBACK_LENGTH,
    ExpressionRequest,
    _finite_float,
    _sanitize_actions,
    _short_string,
    ensure_expression_request,
)
from .expression_settings import ExpressionSettings, provider_api_key_required, provider_api_style
from .snapshot import CompanionSnapshot


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
MAX_MOTION_LENGTH = 40
MAX_OPENAI_RESPONSE_BYTES = 65_536
MAX_OPENAI_RESPONSE_TEXT_LENGTH = 4096


class LLMProviderError(RuntimeError):
    pass


_ExpressionPayloadError = ExpressionPayloadError
_normalize_expression_event = normalize_expression_event
_parse_shinsekai_object_stream = parse_shinsekai_object_stream
_stringify_event = stringify_event


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
            raise LLMProviderError("OpenAI expression provider failed: closed")
        if not self.api_key:
            raise LLMProviderError("OpenAI expression provider failed: missing_api_key")
        if not isinstance(prompt, str):
            raise LLMProviderError("OpenAI expression provider failed: invalid_prompt")
        if not prompt.strip():
            raise LLMProviderError("OpenAI expression provider failed: invalid_prompt")
        if len(prompt) > MAX_OPENAI_PROMPT_LENGTH:
            raise LLMProviderError("OpenAI expression provider failed: invalid_prompt")
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
                raise LLMProviderError("OpenAI expression provider failed: invalid_response_bytes")
            if len(raw) > MAX_OPENAI_RESPONSE_BYTES:
                raise LLMProviderError("OpenAI expression provider failed: invalid_response_size")
            try:
                decoded = bytes(raw).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise LLMProviderError("OpenAI expression provider failed: invalid_response_encoding") from exc
            try:
                response = json.loads(decoded)
            except json.JSONDecodeError as exc:
                raise LLMProviderError("OpenAI expression provider failed: invalid_response_json") from exc
            if not isinstance(response, dict):
                raise LLMProviderError("OpenAI expression provider failed: invalid_response_shape")
            try:
                return _extract_response_text(response)
            except ValueError as exc:
                raise LLMProviderError("OpenAI expression provider failed: invalid_response_text") from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(f"OpenAI expression provider failed: {type(exc).__name__}") from exc

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
    ) -> None:
        self.api_key = _normalize_api_key(api_key)
        self.model = _normalize_model(model)
        self.base_url = _normalize_base_url(base_url)
        self.timeout_seconds = _normalize_timeout(timeout_seconds)
        self.transport = transport or _default_transport
        self.require_api_key = bool(require_api_key)
        self._closed = False

    def __enter__(self) -> "OpenAICompatibleChatClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def __call__(self, prompt: str) -> str:
        if self._closed:
            raise LLMProviderError("OpenAI-compatible expression provider failed: closed")
        if self.require_api_key and not self.api_key:
            raise LLMProviderError("OpenAI-compatible expression provider failed: missing_api_key")
        if not isinstance(prompt, str):
            raise LLMProviderError("OpenAI-compatible expression provider failed: invalid_prompt")
        if not prompt.strip():
            raise LLMProviderError("OpenAI-compatible expression provider failed: invalid_prompt")
        if len(prompt) > MAX_OPENAI_PROMPT_LENGTH:
            raise LLMProviderError("OpenAI-compatible expression provider failed: invalid_prompt")
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        api_request = request.Request(
            _chat_completions_url(self.base_url),
            data=payload,
            headers=_json_request_headers(self.api_key),
            method="POST",
        )
        try:
            raw = self.transport(api_request, self.timeout_seconds)
            if not isinstance(raw, (bytes, bytearray)):
                raise LLMProviderError("OpenAI-compatible expression provider failed: invalid_response_bytes")
            if len(raw) > MAX_OPENAI_RESPONSE_BYTES:
                raise LLMProviderError("OpenAI-compatible expression provider failed: invalid_response_size")
            try:
                decoded = bytes(raw).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise LLMProviderError("OpenAI-compatible expression provider failed: invalid_response_encoding") from exc
            try:
                response = json.loads(decoded)
            except json.JSONDecodeError as exc:
                raise LLMProviderError("OpenAI-compatible expression provider failed: invalid_response_json") from exc
            if not isinstance(response, dict):
                raise LLMProviderError("OpenAI-compatible expression provider failed: invalid_response_shape")
            try:
                return _extract_chat_completion_text(response)
            except ValueError as exc:
                raise LLMProviderError("OpenAI-compatible expression provider failed: invalid_response_text") from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(f"OpenAI-compatible expression provider failed: {type(exc).__name__}") from exc

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
        raise LLMProviderError("model list fetch failed: missing_api_key")
    normalized_base_url = _normalize_base_url(base_url)
    api_request = request.Request(
        _models_url(normalized_base_url),
        headers=_json_request_headers(normalized_api_key),
        method="GET",
    )
    try:
        raw = (transport or _default_transport)(api_request, _normalize_timeout(timeout_seconds))
        if not isinstance(raw, (bytes, bytearray)):
            raise LLMProviderError("model list fetch failed: invalid_response_bytes")
        if len(raw) > MAX_OPENAI_RESPONSE_BYTES:
            raise LLMProviderError("model list fetch failed: invalid_response_size")
        response = json.loads(bytes(raw).decode("utf-8"))
    except LLMProviderError:
        raise
    except UnicodeDecodeError as exc:
        raise LLMProviderError("model list fetch failed: invalid_response_encoding") from exc
    except json.JSONDecodeError as exc:
        raise LLMProviderError("model list fetch failed: invalid_response_json") from exc
    except Exception as exc:
        raise LLMProviderError(f"model list fetch failed: {type(exc).__name__}") from exc
    if not isinstance(response, dict):
        raise LLMProviderError("model list fetch failed: invalid_response_shape")
    data = response.get("data")
    if not isinstance(data, list):
        raise LLMProviderError("model list fetch failed: invalid_response_shape")
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
        raise LLMProviderError("model list fetch failed: empty_model_list")
    return tuple(models)


def build_expression_prompt_preview(character_name: str = "星汐") -> str:
    safe_name = _short_string(character_name, MAX_CHARACTER_NAME_LENGTH) or "星汐"
    return "\n".join(
        [
            f"角色：{safe_name}",
            "AI 只能生成表达事件，不能修改状态数值、动作结果、目标、解锁、背包或存档。",
            "输出必须是 JSON 数组或连续 JSON 对象；每个对象只允许 type、speech、effect、motion_hint。",
            "type 固定为 speech；speech 是星汐说出的短句；effect 和 motion_hint 只是演出提示。",
            "本地状态机拥有最终权威：数值、背包、商店、关系、回忆、目标和存档只由本地代码更新。",
            '示例：{"type":"speech","speech":"我在这里。","effect":"ATTENTION","motion_hint":"Default"}',
        ]
    )


class ShinsekaiAIExpressor:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        enabled: bool = True,
    ) -> None:
        self.llm_client = llm_client
        self.timeout_seconds = _normalize_timeout(timeout_seconds)
        self.enabled = enabled
        self.last_fallback_reason: str | None = None
        self._closed = False
        self._executor: ThreadPoolExecutor | None = None

    def __enter__(self) -> "ShinsekaiAIExpressor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def build_prompt(self, snapshot: dict[str, object] | CompanionSnapshot | ExpressionRequest) -> str:
        try:
            expression_request = _ensure_expression_request(snapshot)
        except (KeyError, TypeError, ValueError):
            return _invalid_snapshot_prompt()
        prompt_payload = expression_request.to_prompt_dict()
        choices = " / ".join(str(entry["label"]) for entry in prompt_payload["actions"])
        memory = " / ".join(
            f"{entry['kind']}: {entry['summary']}" for entry in prompt_payload["recent_memory"]
        )
        long_term_memory = " / ".join(
            f"{entry['category']}: {entry['summary']}" for entry in prompt_payload["long_term_memory"]
        )
        tool_results = " / ".join(_format_tool_result(entry) for entry in prompt_payload["tool_results"])
        return "\n".join(
            [
                "你是 AI 桌面伴侣电子宠物 demo 的 ShinsekaiAIExpressor。",
                "AI 只能生成表达事件，不能修改状态数值、动作结果、目标、解锁、背包或存档。",
                "请输出 JSON 数组，每个对象只包含 type, speech, effect, motion_hint。",
                'type 固定为 speech；speech 是星汐说出的短句；effect 和 motion_hint 只是表达提示。',
                f"character_name: {prompt_payload['character_name']}",
                f"mode: {prompt_payload['mode']}",
                f"motion: {prompt_payload['motion']}",
                f"focus: {prompt_payload['focus']}",
                f"charge: {prompt_payload['charge']}",
                f"stability: {prompt_payload['stability']}",
                f"mood: {prompt_payload['mood']}",
                f"trust: {prompt_payload['trust']}",
                f"feedback: {prompt_payload['feedback']}",
                f"delta: {prompt_payload['delta_text']}",
                f"goal: {prompt_payload['goal']}",
                f"choices: {choices}",
                f"recent_memory: {memory}",
                f"long_term_memory: {long_term_memory}",
                f"perception_summary: {prompt_payload['perception_summary']}",
                f"tool_results: {tool_results}",
                '示例字段：{"type":"speech","speech":"短句","effect":"ATTENTION","motion_hint":"Raised"}',
            ]
        )

    def express(
        self,
        snapshot: dict[str, object] | CompanionSnapshot | ExpressionRequest,
        effect: str | None = None,
    ) -> list[dict[str, str]]:
        try:
            expression_request = _ensure_expression_request(snapshot)
            prompt_payload = expression_request.to_prompt_dict()
            state = _state_from_snapshot(prompt_payload)
            choices = [str(entry["label"]) for entry in prompt_payload["actions"]]
            fallback_feedback = str(prompt_payload["feedback"])
        except (KeyError, TypeError, ValueError):
            self.last_fallback_reason = "invalid_snapshot"
            return _fallback_events_for_invalid_snapshot(snapshot)
        fallback_effect = effect or "DISAPPOINTED"

        if self._closed:
            self.last_fallback_reason = "closed"
            return build_fallback_events(state, fallback_feedback, choices, effect=fallback_effect)
        if not self.enabled or self.llm_client is None:
            self.last_fallback_reason = "disabled"
            return build_fallback_events(state, fallback_feedback, choices, effect=fallback_effect)

        try:
            raw = self._call_llm(self.build_prompt(snapshot))
            raw = _json_candidate_from_llm_text(_validated_llm_response_text(raw))
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                payload = _parse_shinsekai_object_stream(raw, state)
                if payload is None:
                    raise exc
        except TimeoutError:
            self.last_fallback_reason = "timeout"
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")
        except _ExpressionPayloadError as exc:
            self.last_fallback_reason = exc.reason
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")
        except json.JSONDecodeError:
            self.last_fallback_reason = "invalid_json"
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")
        except Exception:
            self.last_fallback_reason = "provider_error"
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")

        if not isinstance(payload, list) or not payload or not all(isinstance(row, dict) for row in payload):
            self.last_fallback_reason = "invalid_payload"
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")
        if len(payload) > 4:
            self.last_fallback_reason = "too_many_events"
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")
        normalized_events = [_normalize_expression_event(state, row) for row in payload]
        if any(row is None for row in normalized_events):
            self.last_fallback_reason = "unsafe_event"
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")

        validated_events = validate_events(
            state=state,
            events=[row for row in normalized_events if row is not None],
            fallback_feedback=fallback_feedback,
            choices=choices,
        )
        if _is_fallback_events(state, validated_events, fallback_feedback):
            self.last_fallback_reason = "invalid_event"
        else:
            self.last_fallback_reason = None
        return validated_events

    def _call_llm(self, prompt: str) -> str:
        if self._closed:
            raise LLMProviderError("LLM expression provider failed: closed")
        if self.llm_client is None:
            raise TypeError("LLM client is not configured.")
        executor = self._ensure_executor()
        try:
            future = executor.submit(self.llm_client, prompt)
        except Exception:
            try:
                self._shutdown_executor()
            except Exception:
                pass
            raise
        try:
            return future.result(timeout=self.timeout_seconds)
        except TimeoutError:
            try:
                future.cancel()
            except Exception:
                pass
            try:
                self._shutdown_executor()
            except Exception:
                pass
            raise

    def _ensure_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm-expressor")
        return self._executor

    def _shutdown_executor(self) -> None:
        executor = self._executor
        if executor is None:
            return
        self._executor = None
        executor.shutdown(wait=False, cancel_futures=True)

    def close(self) -> None:
        if self._closed:
            return
        client = self.llm_client
        close = getattr(client, "close", None)
        try:
            if callable(close):
                close()
        except Exception:
            pass
        finally:
            try:
                self._shutdown_executor()
            except Exception:
                pass
            self.llm_client = None
            self.enabled = False
            self._closed = True


def _state_from_snapshot(snapshot: dict[str, object]):
    state = create_initial_state(now=0)
    state.character_name = str(snapshot["character_name"])
    state.focus = _finite_float(snapshot["focus"])
    state.charge = _finite_float(snapshot["charge"])
    state.stability = _finite_float(snapshot["stability"])
    state.mood = _finite_float(snapshot["mood"])
    state.trust = _finite_float(snapshot["trust"])
    state.mode = str(snapshot["mode"])
    return state


def _ensure_expression_request(snapshot: dict[str, object] | CompanionSnapshot | ExpressionRequest) -> ExpressionRequest:
    return ensure_expression_request(snapshot)


def _invalid_snapshot_prompt() -> str:
    return "\n".join(
        [
            "invalid_snapshot: expression prompt unavailable",
            "AI can only generate expression events and must not change local settlement data, goals, or saves.",
            'Output a JSON array with one speech object if possible: [{"type":"speech","speech":"short line","effect":"DISAPPOINTED"}]',
        ]
    )


def _fallback_events_for_invalid_snapshot(snapshot: object) -> list[dict[str, str]]:
    state = create_initial_state(now=0)
    feedback = "expression unavailable"
    choices: list[str] = []
    if isinstance(snapshot, dict):
        character_name = _short_string(snapshot.get("character_name", ""), MAX_CHARACTER_NAME_LENGTH)
        if character_name:
            state.character_name = character_name
        feedback = _short_string(snapshot.get("feedback", ""), MAX_FEEDBACK_LENGTH) or feedback
        choices = [entry["label"] for entry in _sanitize_actions(snapshot.get("actions", []))]
    return build_fallback_events(state, feedback, choices, effect="DISAPPOINTED")


def _format_tool_result(entry: dict[str, str]) -> str:
    timestamp = f" @ {entry['timestamp']}" if entry.get("timestamp") else ""
    return f"{entry['source']}: {entry['title']}{timestamp} - {entry['summary']}"


def _is_fallback_events(state, events: list[dict[str, str]], fallback_feedback: str) -> bool:
    return (
        [event.get("character_name") for event in events] == [state.character_name, "STAT", "CHOICE"]
        and events[0].get("speech") == fallback_feedback
        and events[0].get("effect") == "DISAPPOINTED"
    )


def build_default_ai_expressor(
    env: Mapping[str, object] | None = None,
    *,
    settings: ExpressionSettings | None = None,
) -> ShinsekaiAIExpressor:
    if settings is not None:
        return _build_ai_expressor_from_settings(settings)
    config = _openai_config_from_env(env)
    if config is None:
        return ShinsekaiAIExpressor(enabled=False)
    client = OpenAIResponsesClient(
        api_key=config.api_key,
        model=config.model,
        base_url=config.base_url,
        timeout_seconds=config.timeout_seconds,
    )
    return ShinsekaiAIExpressor(
        llm_client=client,
        timeout_seconds=config.timeout_seconds,
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


def _build_ai_expressor_from_settings(settings: ExpressionSettings) -> ShinsekaiAIExpressor:
    require_api_key = provider_api_key_required(settings.provider)
    if not settings.enabled or (require_api_key and not settings.api_key):
        return ShinsekaiAIExpressor(enabled=False)
    if provider_api_style(settings.provider) == "responses":
        client = OpenAIResponsesClient(
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
        )
    return ShinsekaiAIExpressor(
        llm_client=client,
        timeout_seconds=settings.timeout_seconds,
        enabled=True,
    )


def _default_transport(api_request: request.Request, timeout: float) -> bytes:
    with request.urlopen(api_request, timeout=timeout) as response:
        return response.read()


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


def _validated_llm_response_text(value: object) -> str:
    if not isinstance(value, str):
        raise LLMProviderError("LLM expression provider failed: invalid_response_text")
    if len(value) > MAX_OPENAI_RESPONSE_TEXT_LENGTH:
        raise LLMProviderError("LLM expression provider failed: invalid_response_text")
    return value.strip()


def _json_candidate_from_llm_text(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if text.startswith(("[", "{")):
        return text
    first_array = text.find("[")
    first_object = text.find("{")
    starts = [index for index in (first_array, first_object) if index >= 0]
    if not starts:
        return text
    start = min(starts)
    end = max(text.rfind("]"), text.rfind("}"))
    if end < start:
        return text
    return text[start : end + 1].strip()


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


def _has_control_character(value: str) -> bool:
    return any(_is_control_character(char) for char in value)


def _is_control_character(char: str) -> bool:
    return ord(char) < 32 or ord(char) == 127
