from __future__ import annotations

import json
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any
from urllib import request

from .engine import create_initial_state
from .events import build_fallback_events, validate_events


LLMClient = Callable[[str], str]
HTTPTransport = Callable[[request.Request, float], bytes]
DEFAULT_TIMEOUT_SECONDS = 2.0
DEFAULT_OPENAI_MODEL = "gpt-5.5"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_PERCEPTION_SUMMARY_LENGTH = 240
MAX_TOOL_RESULTS = 3


class LLMProviderError(RuntimeError):
    pass


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
        actions = tuple(
            {"label": str(action.get("label", ""))}
            for action in _as_dict_list(snapshot.get("actions", []))
            if action.get("label")
        )
        recent_memory = tuple(
            {
                "kind": str(entry.get("kind", "")),
                "summary": str(entry.get("summary", "")),
                "motion": str(entry.get("motion", "")),
            }
            for entry in _as_dict_list(snapshot.get("memory_log", []))[:3]
        )
        return cls(
            character_name=str(snapshot["character_name"]),
            mode=str(snapshot["mode"]),
            motion=str(snapshot.get("motion", snapshot.get("current_motion", ""))),
            focus=float(snapshot["focus"]),
            charge=float(snapshot["charge"]),
            stability=float(snapshot["stability"]),
            mood=float(snapshot["mood"]),
            trust=float(snapshot["trust"]),
            feedback=str(snapshot["feedback"]),
            delta_text=str(snapshot["delta_text"]),
            goal=str(snapshot["goal"]),
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
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport or _default_transport

    def __call__(self, prompt: str) -> str:
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
            response = json.loads(raw.decode("utf-8"))
            return _extract_response_text(response)
        except Exception as exc:
            raise LLMProviderError(f"OpenAI expression provider failed: {type(exc).__name__}") from exc


class ShinsekaiAIExpressor:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        enabled: bool = True,
    ) -> None:
        self.llm_client = llm_client
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled
        self.last_fallback_reason: str | None = None

    def build_prompt(self, snapshot: dict[str, object] | ExpressionRequest) -> str:
        expression_request = _ensure_expression_request(snapshot)
        prompt_payload = expression_request.to_prompt_dict()
        choices = " / ".join(str(entry["label"]) for entry in prompt_payload["actions"])
        memory = " / ".join(
            f"{entry['kind']}: {entry['summary']}" for entry in prompt_payload["recent_memory"]
        )
        tool_results = " / ".join(
            f"{entry['source']}: {entry['title']} - {entry['summary']}" for entry in prompt_payload["tool_results"]
        )
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
        expression_request = _ensure_expression_request(snapshot)
        prompt_payload = expression_request.to_prompt_dict()
        state = _state_from_snapshot(prompt_payload)
        choices = [str(entry["label"]) for entry in prompt_payload["actions"]]
        fallback_feedback = str(prompt_payload["feedback"])
        fallback_effect = effect or "DISAPPOINTED"

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
        except (LLMProviderError, TypeError, ValueError, OSError):
            self.last_fallback_reason = "provider_error"
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")

        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            self.last_fallback_reason = "invalid_payload"
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")
        normalized_events = [_normalize_expression_event(state, row) for row in payload]
        if any(row is None for row in normalized_events):
            self.last_fallback_reason = "unsafe_event"
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")
        if len(normalized_events) > 4:
            self.last_fallback_reason = "too_many_events"
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
        if self.llm_client is None:
            raise TypeError("LLM client is not configured.")
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm-expressor")
        future = executor.submit(self.llm_client, prompt)
        try:
            return future.result(timeout=self.timeout_seconds)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


def _state_from_snapshot(snapshot: dict[str, object]):
    state = create_initial_state(now=0)
    state.character_name = str(snapshot["character_name"])
    state.focus = float(snapshot["focus"])
    state.charge = float(snapshot["charge"])
    state.stability = float(snapshot["stability"])
    state.mood = float(snapshot["mood"])
    state.trust = float(snapshot["trust"])
    state.mode = str(snapshot["mode"])
    return state


def _stringify_event(event: dict[Any, Any]) -> dict[str, str]:
    return {str(key): str(value) for key, value in event.items()}


def _ensure_expression_request(snapshot: dict[str, object] | ExpressionRequest) -> ExpressionRequest:
    if isinstance(snapshot, ExpressionRequest):
        return snapshot
    return ExpressionRequest.from_snapshot(snapshot)


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
        results.append({"source": source, "title": title, "summary": summary})
        if len(results) >= MAX_TOOL_RESULTS:
            break
    return tuple(results)


def _short_string(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def _normalize_expression_event(state, event: dict[Any, Any]) -> dict[str, str] | None:
    if _is_allowed_legacy_expression_event(state, event):
        return _stringify_event(event)
    return _normalize_speech_schema_event(state, event)


def _is_allowed_legacy_expression_event(state, event: dict[Any, Any]) -> bool:
    if {str(key) for key in event.keys()} != {"character_name", "speech", "sprite", "effect"}:
        return False
    if not all(isinstance(event.get(key), str) for key in ("character_name", "speech", "sprite", "effect")):
        return False
    return str(event.get("character_name")) == state.character_name


def _normalize_speech_schema_event(state, event: dict[Any, Any]) -> dict[str, str] | None:
    allowed_keys = {"type", "speech", "effect", "motion_hint"}
    if not set(event.keys()).issubset(allowed_keys):
        return None
    if event.get("type") != "speech":
        return None

    speech = event.get("speech")
    effect = event.get("effect", "")
    motion_hint = event.get("motion_hint", "")
    if not isinstance(speech, str):
        return None
    if not isinstance(effect, str):
        return None
    if motion_hint != "" and not isinstance(motion_hint, str):
        return None

    return {
        "character_name": state.character_name,
        "speech": speech,
        "sprite": "1",
        "effect": effect,
    }


def _is_fallback_events(state, events: list[dict[str, str]], fallback_feedback: str) -> bool:
    return (
        [event.get("character_name") for event in events] == [state.character_name, "STAT", "CHOICE"]
        and events[0].get("speech") == fallback_feedback
        and events[0].get("effect") == "DISAPPOINTED"
    )


def build_default_ai_expressor(env: dict[str, str] | None = None) -> ShinsekaiAIExpressor:
    source = os.environ if env is None else env
    if source.get("GUANGHE_LLM_ENABLED") != "1":
        return ShinsekaiAIExpressor(enabled=False)
    api_key = source.get("OPENAI_API_KEY")
    if not api_key:
        return ShinsekaiAIExpressor(enabled=False)
    timeout_seconds = _parse_timeout(source.get("GUANGHE_LLM_TIMEOUT_SECONDS"))
    client = OpenAIResponsesClient(
        api_key=api_key,
        model=source.get("GUANGHE_LLM_MODEL") or DEFAULT_OPENAI_MODEL,
        timeout_seconds=timeout_seconds,
    )
    return ShinsekaiAIExpressor(
        llm_client=client,
        timeout_seconds=timeout_seconds,
        enabled=True,
    )


def _default_transport(api_request: request.Request, timeout: float) -> bytes:
    with request.urlopen(api_request, timeout=timeout) as response:
        return response.read()


def _extract_response_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
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
                return str(part["text"])
    raise ValueError("OpenAI response does not include output text.")


def _parse_timeout(value: str | None) -> float:
    if value is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    return parsed if parsed > 0 else DEFAULT_TIMEOUT_SECONDS
