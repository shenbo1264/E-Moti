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
from .events import ALLOWED_EFFECTS, build_fallback_events, validate_events


LLMClient = Callable[[str], str]
HTTPTransport = Callable[[request.Request, float], bytes]
DEFAULT_TIMEOUT_SECONDS = 2.0
MAX_TIMEOUT_SECONDS = 5.0
DEFAULT_OPENAI_MODEL = "gpt-5.5"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_PERCEPTION_SUMMARY_LENGTH = 240
MAX_TOOL_RESULTS = 3
MAX_ACTION_LABEL_LENGTH = 40
MAX_RECENT_MEMORY = 3
MAX_CHARACTER_NAME_LENGTH = 40
MAX_MODE_LENGTH = 40
MAX_MOTION_LENGTH = 40
MAX_SPEECH_LENGTH = 80
MAX_MOTION_HINT_LENGTH = 40
MAX_EFFECT_LENGTH = 20
MAX_FEEDBACK_LENGTH = 160
MAX_DELTA_TEXT_LENGTH = 80
MAX_GOAL_LENGTH = 160
MAX_MEMORY_KIND_LENGTH = 40
MAX_MEMORY_SUMMARY_LENGTH = 160
MAX_MEMORY_MOTION_LENGTH = 40
MAX_TOOL_TIMESTAMP_LENGTH = 40


class LLMProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _OpenAIProviderConfig:
    api_key: str
    model: str
    timeout_seconds: float


@dataclass(frozen=True, slots=True)
class ExpressionRequest:
    character_name: str
    mode: str
    motion: str
    focus: float
    charge: float
    stability: float
    mood: float
    trust: float
    feedback: str
    delta_text: str
    goal: str
    actions: tuple[dict[str, str], ...]
    recent_memory: tuple[dict[str, str], ...]
    perception_summary: str = ""
    tool_results: tuple[dict[str, str], ...] = ()

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, object]) -> "ExpressionRequest":
        actions = _sanitize_actions(snapshot.get("actions", []))
        recent_memory = _sanitize_recent_memory(snapshot.get("memory_log", []))
        return cls(
            character_name=_short_string(snapshot.get("character_name", ""), MAX_CHARACTER_NAME_LENGTH),
            mode=_short_string(snapshot.get("mode", ""), MAX_MODE_LENGTH),
            motion=_short_string(snapshot.get("motion", snapshot.get("current_motion", "")), MAX_MOTION_LENGTH),
            focus=_finite_float(snapshot["focus"]),
            charge=_finite_float(snapshot["charge"]),
            stability=_finite_float(snapshot["stability"]),
            mood=_finite_float(snapshot["mood"]),
            trust=_finite_float(snapshot["trust"]),
            feedback=_short_string(snapshot.get("feedback", ""), MAX_FEEDBACK_LENGTH),
            delta_text=_short_string(snapshot.get("delta_text", ""), MAX_DELTA_TEXT_LENGTH),
            goal=_short_string(snapshot.get("goal", ""), MAX_GOAL_LENGTH),
            actions=actions,
            recent_memory=recent_memory,
            perception_summary=_short_string(snapshot.get("perception_summary", ""), MAX_PERCEPTION_SUMMARY_LENGTH),
            tool_results=_sanitize_tool_results(snapshot.get("tool_results", [])),
        )

    def to_prompt_dict(self) -> dict[str, object]:
        return {
            "character_name": self.character_name,
            "mode": self.mode,
            "motion": self.motion,
            "focus": self.focus,
            "charge": self.charge,
            "stability": self.stability,
            "mood": self.mood,
            "trust": self.trust,
            "feedback": self.feedback,
            "delta_text": self.delta_text,
            "goal": self.goal,
            "actions": [dict(action) for action in self.actions],
            "recent_memory": [dict(entry) for entry in self.recent_memory],
            "perception_summary": self.perception_summary,
            "tool_results": [dict(entry) for entry in self.tool_results],
        }


class OpenAIResponsesClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: HTTPTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip() if isinstance(api_key, str) else ""
        self.model = model.strip() if isinstance(model, str) else ""
        self.model = self.model or DEFAULT_OPENAI_MODEL
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
        payload = json.dumps(
            {
                "model": self.model,
                "input": prompt,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        api_request = request.Request(
            OPENAI_RESPONSES_URL,
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
            return _extract_response_text(response)
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(f"OpenAI expression provider failed: {type(exc).__name__}") from exc

    def close(self) -> None:
        self._closed = True


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

    def build_prompt(self, snapshot: dict[str, object] | ExpressionRequest) -> str:
        try:
            expression_request = _ensure_expression_request(snapshot)
        except (KeyError, TypeError, ValueError):
            return _invalid_snapshot_prompt()
        prompt_payload = expression_request.to_prompt_dict()
        choices = " / ".join(str(entry["label"]) for entry in prompt_payload["actions"])
        memory = " / ".join(
            f"{entry['kind']}: {entry['summary']}" for entry in prompt_payload["recent_memory"]
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
                f"perception_summary: {prompt_payload['perception_summary']}",
                f"tool_results: {tool_results}",
                '示例字段：{"type":"speech","speech":"短句","effect":"ATTENTION","motion_hint":"Raised"}',
            ]
        )

    def express(self, snapshot: dict[str, object] | ExpressionRequest, effect: str | None = None) -> list[dict[str, str]]:
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
            payload = json.loads(raw)
        except TimeoutError:
            self.last_fallback_reason = "timeout"
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


def _stringify_event(event: dict[Any, Any]) -> dict[str, str]:
    return {str(key): str(value).strip() for key, value in event.items()}


def _ensure_expression_request(snapshot: dict[str, object] | ExpressionRequest) -> ExpressionRequest:
    if isinstance(snapshot, ExpressionRequest):
        return snapshot
    return ExpressionRequest.from_snapshot(snapshot)


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


def _as_dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _sanitize_tool_results(value: object) -> tuple[dict[str, str], ...]:
    results: list[dict[str, str]] = []
    for entry in _as_dict_list(value):
        source = _short_string(entry.get("source", ""), 60)
        title = _short_string(entry.get("title", ""), 80)
        summary = _short_string(entry.get("summary", ""), 180)
        if not source or not title or not summary:
            continue
        result = {"source": source, "title": title, "summary": summary}
        timestamp = _short_string(entry.get("timestamp", ""), MAX_TOOL_TIMESTAMP_LENGTH)
        if timestamp:
            result["timestamp"] = timestamp
        results.append(result)
        if len(results) >= MAX_TOOL_RESULTS:
            break
    return tuple(results)


def _format_tool_result(entry: dict[str, str]) -> str:
    timestamp = f" @ {entry['timestamp']}" if entry.get("timestamp") else ""
    return f"{entry['source']}: {entry['title']}{timestamp} - {entry['summary']}"


def _sanitize_actions(value: object) -> tuple[dict[str, str], ...]:
    actions: list[dict[str, str]] = []
    for action in _as_dict_list(value):
        label = _short_string(action.get("label", ""), MAX_ACTION_LABEL_LENGTH)
        if label:
            actions.append({"label": label})
    return tuple(actions)


def _sanitize_recent_memory(value: object) -> tuple[dict[str, str], ...]:
    memory: list[dict[str, str]] = []
    for entry in _as_dict_list(value):
        kind = _short_string(entry.get("kind", ""), MAX_MEMORY_KIND_LENGTH)
        summary = _short_string(entry.get("summary", ""), MAX_MEMORY_SUMMARY_LENGTH)
        motion = _short_string(entry.get("motion", ""), MAX_MEMORY_MOTION_LENGTH)
        if not kind or not summary or not motion:
            continue
        memory.append({"kind": kind, "summary": summary, "motion": motion})
        if len(memory) >= MAX_RECENT_MEMORY:
            break
    return tuple(memory)


def _short_string(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def _finite_float(value: object) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite expression stat")
    return parsed


def _normalize_expression_event(state, event: dict[Any, Any]) -> dict[str, str] | None:
    if _is_allowed_legacy_expression_event(state, event):
        return _stringify_event(event)
    return _normalize_speech_schema_event(state, event)


def _is_allowed_legacy_expression_event(state, event: dict[Any, Any]) -> bool:
    if {str(key) for key in event.keys()} != {"character_name", "speech", "sprite", "effect"}:
        return False
    if not all(isinstance(event.get(key), str) for key in ("character_name", "speech", "sprite", "effect")):
        return False
    normalized = _stringify_event(event)
    if not normalized["speech"]:
        return False
    if len(normalized["speech"]) > MAX_SPEECH_LENGTH:
        return False
    if not _is_safe_legacy_sprite(normalized["sprite"]):
        return False
    if normalized["effect"] not in ALLOWED_EFFECTS:
        return False
    return normalized["character_name"] == state.character_name


def _is_safe_legacy_sprite(sprite: str) -> bool:
    return sprite == "1"


def _normalize_speech_schema_event(state, event: dict[Any, Any]) -> dict[str, str] | None:
    allowed_keys = {"type", "speech", "effect", "motion_hint"}
    if not set(event.keys()).issubset(allowed_keys):
        return None
    if event.get("type") != "speech":
        return None

    speech = event.get("speech")
    effect = event.get("effect", "")
    motion_hint = event.get("motion_hint", "")
    if not isinstance(speech, str) or not speech.strip():
        return None
    normalized_speech = speech.strip()
    if len(normalized_speech) > MAX_SPEECH_LENGTH:
        return None
    if not isinstance(effect, str):
        return None
    normalized_effect = effect.strip()
    if len(normalized_effect) > MAX_EFFECT_LENGTH:
        return None
    if normalized_effect not in ALLOWED_EFFECTS:
        return None
    if motion_hint != "" and not isinstance(motion_hint, str):
        return None
    if isinstance(motion_hint, str) and len(motion_hint.strip()) > MAX_MOTION_HINT_LENGTH:
        return None

    return {
        "character_name": state.character_name,
        "speech": normalized_speech,
        "sprite": "1",
        "effect": normalized_effect,
    }


def _is_fallback_events(state, events: list[dict[str, str]], fallback_feedback: str) -> bool:
    return (
        [event.get("character_name") for event in events] == [state.character_name, "STAT", "CHOICE"]
        and events[0].get("speech") == fallback_feedback
        and events[0].get("effect") == "DISAPPOINTED"
    )


def build_default_ai_expressor(env: Mapping[str, object] | None = None) -> ShinsekaiAIExpressor:
    config = _openai_config_from_env(env)
    if config is None:
        return ShinsekaiAIExpressor(enabled=False)
    client = OpenAIResponsesClient(
        api_key=config.api_key,
        model=config.model,
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
    if not isinstance(enabled_flag, str) or enabled_flag.strip() != "1":
        return None
    raw_api_key = source.get("OPENAI_API_KEY")
    api_key = raw_api_key.strip() if isinstance(raw_api_key, str) else ""
    if not api_key:
        return None
    raw_model = source.get("GUANGHE_LLM_MODEL")
    model = raw_model.strip() if isinstance(raw_model, str) else ""
    return _OpenAIProviderConfig(
        api_key=api_key,
        model=model or DEFAULT_OPENAI_MODEL,
        timeout_seconds=_parse_timeout(source.get("GUANGHE_LLM_TIMEOUT_SECONDS")),
    )


def _default_transport(api_request: request.Request, timeout: float) -> bytes:
    with request.urlopen(api_request, timeout=timeout) as response:
        return response.read()


def _extract_response_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
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
                return str(part["text"]).strip()
    raise ValueError("OpenAI response does not include output text.")


def _parse_timeout(value: str | None) -> float:
    if value is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS
    return _normalize_timeout(parsed)


def _normalize_timeout(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS
    return parsed if math.isfinite(parsed) and 0 < parsed <= MAX_TIMEOUT_SECONDS else DEFAULT_TIMEOUT_SECONDS
