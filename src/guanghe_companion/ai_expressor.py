from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any

from .engine import create_initial_state
from .events import build_fallback_events, validate_events


LLMClient = Callable[[str], str]
DEFAULT_TIMEOUT_SECONDS = 2.0


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

    def build_prompt(self, snapshot: dict[str, object]) -> str:
        choices = " / ".join(str(entry["label"]) for entry in snapshot["actions"])
        return "\n".join(
            [
                "你是 AI 桌面伴侣电子宠物 demo 的 ShinsekaiAIExpressor。",
                "AI 只能生成表达事件，不能修改状态数值、动作结果、目标、解锁、背包或存档。",
                "请输出 JSON 数组，每个对象只包含 character_name, speech, sprite, effect。",
                f"character_name: {snapshot['character_name']}",
                f"mode: {snapshot['mode']}",
                f"motion: {snapshot['motion']}",
                f"focus: {snapshot['focus']}",
                f"charge: {snapshot['charge']}",
                f"stability: {snapshot['stability']}",
                f"mood: {snapshot['mood']}",
                f"trust: {snapshot['trust']}",
                f"feedback: {snapshot['feedback']}",
                f"delta: {snapshot['delta_text']}",
                f"goal: {snapshot['goal']}",
                f"choices: {choices}",
                '示例字段：{"character_name":"星汐","speech":"短句","sprite":"1","effect":"ATTENTION"}',
            ]
        )

    def express(self, snapshot: dict[str, object], effect: str | None = None) -> list[dict[str, str]]:
        state = _state_from_snapshot(snapshot)
        choices = [str(entry["label"]) for entry in snapshot["actions"]]
        fallback_feedback = str(snapshot["feedback"])
        fallback_effect = effect or "DISAPPOINTED"

        if not self.enabled or self.llm_client is None:
            return build_fallback_events(state, fallback_feedback, choices, effect=fallback_effect)

        try:
            raw = self._call_llm(self.build_prompt(snapshot))
            payload = json.loads(raw)
        except (TimeoutError, TypeError, ValueError, json.JSONDecodeError):
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")

        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")
        if not all(_is_allowed_expression_event(state, row) for row in payload):
            return build_fallback_events(state, fallback_feedback, choices, effect="DISAPPOINTED")

        return validate_events(
            state=state,
            events=[_stringify_event(row) for row in payload],
            fallback_feedback=fallback_feedback,
            choices=choices,
        )

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


def _is_allowed_expression_event(state, event: dict[Any, Any]) -> bool:
    if {str(key) for key in event.keys()} != {"character_name", "speech", "sprite", "effect"}:
        return False
    return str(event.get("character_name")) == state.character_name
