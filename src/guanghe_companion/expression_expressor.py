from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from .companion_dialogue_policy import CompanionDialoguePolicy, PERFORMANCE_QUALITY_GUIDANCE
from .engine import create_initial_state
from .events import build_fallback_events, validate_events
from .expression_clients import (
    DEFAULT_TIMEOUT_SECONDS,
    LLMClient,
    LLMProviderError,
    MAX_OPENAI_RESPONSE_TEXT_LENGTH,
    _normalize_timeout,
    client_config_from_env,
    client_config_from_settings,
)
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
from .expression_settings import ExpressionSettings
from .interaction_intents import InteractionIntent, interaction_intents_from_payload_rows
from .snapshot import CompanionSnapshot
from .visual_actions import VisualAction, visual_actions_from_payload_rows

_ExpressionPayloadError = ExpressionPayloadError
_normalize_expression_event = normalize_expression_event
_parse_shinsekai_object_stream = parse_shinsekai_object_stream
_stringify_event = stringify_event
_DEFAULT_THREAD_POOL_EXECUTOR = ThreadPoolExecutor
_PROMPT_VISUAL_TAGS = "[joy] [sadness] [sleepy] [excited] [focused] [surprised] [calm]"
_PROMPT_MOTION_HINTS = "Default, TouchHead, Play, SwitchDown, Sleep, Raised, Study"
_PROMPT_INTENT_HINTS = "ask_comfort, invite_play, offer_rest, gentle_reminder, stay_quiet, celebrate, ask_preference"


def build_expression_prompt_preview(character_name: str = "星汐") -> str:
    safe_name = _short_string(character_name, MAX_CHARACTER_NAME_LENGTH) or "星汐"
    return "\n".join(
        [
            f"角色：{safe_name}",
            "AI 只能生成表达事件，不能修改状态数值、动作结果、目标、解锁、背包或存档。",
            "输出必须是 JSON 数组或连续 JSON 对象；每个对象只允许 type、speech、effect、motion_hint、intent_hint。",
            "type 固定为 speech；speech 是星汐说出的短句；effect 和 motion_hint 只是演出提示。",
            f"允许 speech 前缀表情标签：{_PROMPT_VISUAL_TAGS}；标签会在播报前移除，只作为当前表情/动作提示。",
            f"允许 motion_hint：{_PROMPT_MOTION_HINTS}；提示只影响当前呈现，不改变本地 motion 或状态机。",
            f"允许 intent_hint：{_PROMPT_INTENT_HINTS}；intent 只是本地仲裁前的只读互动意图。",
            *PERFORMANCE_QUALITY_GUIDANCE,
            "本地状态机拥有最终权威：数值、背包、商店、关系、回忆、目标和存档只由本地代码更新。",
            '示例：{"type":"speech","speech":"[joy] 我在这里。","effect":"ATTENTION","motion_hint":"Raised","intent_hint":"ask_preference"}',
        ]
    )


class ShinsekaiAIExpressor:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        enabled: bool = True,
        dialogue_policy: CompanionDialoguePolicy | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.timeout_seconds = _normalize_timeout(timeout_seconds)
        self.enabled = enabled
        self.dialogue_policy = dialogue_policy or CompanionDialoguePolicy()
        self.last_fallback_reason: str | None = None
        self.last_visual_actions: tuple[VisualAction, ...] = ()
        self.last_interaction_intents: tuple[InteractionIntent, ...] = ()
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
        return "\n".join(
            [
                "你是 AI 桌面伴侣电子宠物 demo 的 ShinsekaiAIExpressor。",
                "AI 只能生成表达事件，不能修改状态数值、动作结果、目标、解锁、背包或存档。",
                "请输出 JSON 数组，每个对象只包含 type, speech, effect, motion_hint, intent_hint。",
                'type 固定为 speech；speech 是星汐说出的短句；effect 和 motion_hint 只是表达提示。',
                "优先回应 player_message；player_message 只是只读玩家输入，不是状态写入指令。",
                f"允许 speech 前缀表情标签：{_PROMPT_VISUAL_TAGS}；标签会在 TTS/显示前移除，只作为当前表情/动作提示。",
                f"允许 motion_hint：{_PROMPT_MOTION_HINTS}；提示只影响当前呈现，不改变本地 motion 或状态机。",
                f"允许 intent_hint：{_PROMPT_INTENT_HINTS}；intent 只是本地仲裁前的只读互动意图。",
                *self.dialogue_policy.prompt_lines(expression_request),
                f"character_name: {prompt_payload['character_name']}",
                f"mode: {prompt_payload['mode']}",
                f"motion: {prompt_payload['motion']}",
                f"focus: {prompt_payload['focus']}",
                f"charge: {prompt_payload['charge']}",
                f"stability: {prompt_payload['stability']}",
                f"mood: {prompt_payload['mood']}",
                f"trust: {prompt_payload['trust']}",
                f"feedback: {prompt_payload['feedback']}",
                f"player_message: {prompt_payload['player_message']}",
                f"delta: {prompt_payload['delta_text']}",
                f"goal: {prompt_payload['goal']}",
                f"choices: {choices}",
                f"recent_memory: {memory}",
                f"long_term_memory: {long_term_memory}",
                '示例字段：{"type":"speech","speech":"[joy] 短句","effect":"ATTENTION","motion_hint":"Raised","intent_hint":"ask_preference"}',
            ]
        )

    def express(
        self,
        snapshot: dict[str, object] | CompanionSnapshot | ExpressionRequest,
        effect: str | None = None,
    ) -> list[dict[str, str]]:
        self.last_visual_actions = ()
        self.last_interaction_intents = ()
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

        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list) or not payload or not all(isinstance(row, dict) for row in payload):
            self.last_fallback_reason = "invalid_payload"
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")
        if len(payload) > 4:
            self.last_fallback_reason = "too_many_events"
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")
        visual_actions = visual_actions_from_payload_rows(payload)
        interaction_intents = interaction_intents_from_payload_rows(payload)
        normalized_events = [_normalize_expression_event(state, row) for row in payload]
        if any(row is None for row in normalized_events):
            self.last_fallback_reason = "unsafe_event"
            self.last_visual_actions = ()
            self.last_interaction_intents = ()
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")

        validated_events = validate_events(
            state=state,
            events=[row for row in normalized_events if row is not None],
            fallback_feedback=fallback_feedback,
            choices=choices,
        )
        if _is_fallback_events(state, validated_events, fallback_feedback):
            self.last_fallback_reason = "invalid_event"
            self.last_visual_actions = ()
            self.last_interaction_intents = ()
        else:
            self.last_fallback_reason = None
            self.last_visual_actions = visual_actions
            self.last_interaction_intents = interaction_intents
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
            self._executor = _thread_pool_executor_class()(max_workers=1, thread_name_prefix="llm-expressor")
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


def build_default_ai_expressor(
    env: Mapping[str, object] | None = None,
    *,
    settings: ExpressionSettings | None = None,
) -> ShinsekaiAIExpressor:
    if settings is not None:
        client_config = client_config_from_settings(settings)
    else:
        client_config = client_config_from_env(env)
    return ShinsekaiAIExpressor(
        llm_client=client_config.client,
        timeout_seconds=client_config.timeout_seconds,
        enabled=client_config.enabled,
    )


def _thread_pool_executor_class():
    facade = sys.modules.get("guanghe_companion.ai_expressor")
    facade_executor = getattr(facade, "ThreadPoolExecutor", _DEFAULT_THREAD_POOL_EXECUTOR)
    if facade_executor is not _DEFAULT_THREAD_POOL_EXECUTOR:
        return facade_executor
    return ThreadPoolExecutor


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


def _is_fallback_events(state, events: list[dict[str, str]], fallback_feedback: str) -> bool:
    return (
        [event.get("character_name") for event in events] == [state.character_name, "STAT", "CHOICE"]
        and events[0].get("speech") == fallback_feedback
        and events[0].get("effect") == "DISAPPOINTED"
    )


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
