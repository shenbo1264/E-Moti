from __future__ import annotations

import json
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any
from urllib import request

from .engine import create_initial_state
from .events import build_fallback_events, validate_events


LLMClient = Callable[[str], str]
HTTPTransport = Callable[[request.Request, float], bytes]
DEFAULT_TIMEOUT_SECONDS = 2.0
DEFAULT_OPENAI_MODEL = "gpt-5.5"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


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
        raw = self.transport(api_request, self.timeout_seconds)
        response = json.loads(raw.decode("utf-8"))
        return _extract_response_text(response)


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
        except (TimeoutError, TypeError, ValueError, OSError, json.JSONDecodeError):
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
    if isinstance(output_text, str) and output_text:
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
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
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
