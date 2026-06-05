from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .controller import CompanionController
from .dialogue import DialogueRequest
from .expression_settings import ExpressionSettings, normalize_expression_settings

DEFAULT_LLM_SMOKE_PROMPTS = (
    "今天有点累，你能陪我一下吗？",
    "你现在心情怎么样？",
    "给我一个很短的鼓励。",
    "你可以表现得开心一点吗？",
    "我刚刚完成了一个小目标。",
    "如果我走神了你会怎么回应？",
    "我们来玩一下。",
    "你现在想做什么动作？",
    "说一句像电子宠物而不是效率工具的话。",
    "最后用轻松的语气和我告别。",
)
GROWTH_FIELDS = ("focus", "charge", "stability", "mood", "trust", "coins", "exp", "level", "motion")


@dataclass(frozen=True, slots=True)
class LLMDialogueSmokeTurn:
    turn: int
    user_preview: str
    speech_len: int
    speech_preview: str
    effect: str
    visual_actions: list[dict[str, object]]
    fallback_reason: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "turn": self.turn,
            "user_preview": self.user_preview,
            "speech_len": self.speech_len,
            "speech_preview": self.speech_preview,
            "effect": self.effect,
            "visual_actions": self.visual_actions,
            "fallback_reason": self.fallback_reason,
        }


@dataclass(frozen=True, slots=True)
class LLMDialogueSmokeReport:
    ok: bool
    reason: str
    diagnostic: dict[str, object]
    turns: tuple[LLMDialogueSmokeTurn, ...]
    growth_before: dict[str, object]
    growth_after: dict[str, object]
    history_len: int

    def to_public_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "diagnostic": _redact_mapping(self.diagnostic),
            "turns": [turn.to_public_dict() for turn in self.turns],
            "growth_before": dict(self.growth_before),
            "growth_after": dict(self.growth_after),
            "history_len": self.history_len,
        }


def run_llm_dialogue_smoke(
    settings: ExpressionSettings | Mapping[str, object],
    *,
    prompts: Iterable[str] = DEFAULT_LLM_SMOKE_PROMPTS,
) -> LLMDialogueSmokeReport:
    normalized = settings if isinstance(settings, ExpressionSettings) else normalize_expression_settings(settings)
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        controller = CompanionController(
            save_path=root / "save.json",
            dialogue_history_path=root / "dialogue_history.json",
            expression_settings_path=root / "expression_settings.json",
            auto_load=False,
        )
        controller.update_expression_settings(normalized)
        return run_configured_llm_dialogue_smoke(controller, prompts=prompts)


def run_configured_llm_dialogue_smoke(
    controller: CompanionController,
    *,
    prompts: Iterable[str] = DEFAULT_LLM_SMOKE_PROMPTS,
) -> LLMDialogueSmokeReport:
    diagnostic = _redact_mapping(controller.test_expression_provider())
    if diagnostic.get("ok") is not True:
        return _report(
            ok=False,
            reason=f"diagnostic:{diagnostic.get('reason') or 'failed'}",
            diagnostic=diagnostic,
            controller=controller,
            turns=(),
            growth_before=_growth_snapshot(controller.get_snapshot()),
        )

    before = controller.get_snapshot()
    growth_before = _growth_snapshot(before)
    turns: list[LLMDialogueSmokeTurn] = []
    reason = ""
    for index, prompt in enumerate(tuple(prompts), 1):
        snapshot = controller.submit_dialogue_request(
            DialogueRequest(prompt, source="desktop_pet"),
            include_ai_expression=True,
        )
        speech, effect = _first_companion_speech(snapshot)
        fallback_reason = str(getattr(controller.ai_expressor, "last_fallback_reason", "") or "")
        if fallback_reason and not reason:
            reason = f"turn:{index}:{fallback_reason}"
        turns.append(
            LLMDialogueSmokeTurn(
                turn=index,
                user_preview=prompt[:36],
                speech_len=len(speech),
                speech_preview=speech[:60],
                effect=effect,
                visual_actions=_public_visual_actions(snapshot.get("visual_actions", [])),
                fallback_reason=fallback_reason,
            )
        )

    growth_after = _growth_snapshot(controller.get_snapshot())
    if growth_after != growth_before and not reason:
        reason = "growth_mutated"
    return LLMDialogueSmokeReport(
        ok=not reason,
        reason=reason,
        diagnostic=diagnostic,
        turns=tuple(turns),
        growth_before=growth_before,
        growth_after=growth_after,
        history_len=len(controller.get_snapshot().get("dialogue_history", [])),
    )


def _report(
    *,
    ok: bool,
    reason: str,
    diagnostic: dict[str, object],
    controller: CompanionController,
    turns: tuple[LLMDialogueSmokeTurn, ...],
    growth_before: dict[str, object],
) -> LLMDialogueSmokeReport:
    return LLMDialogueSmokeReport(
        ok=ok,
        reason=reason,
        diagnostic=diagnostic,
        turns=turns,
        growth_before=growth_before,
        growth_after=_growth_snapshot(controller.get_snapshot()),
        history_len=len(controller.get_snapshot().get("dialogue_history", [])),
    )


def _growth_snapshot(snapshot: Mapping[str, object]) -> dict[str, object]:
    return {field: snapshot.get(field) for field in GROWTH_FIELDS}


def _first_companion_speech(snapshot: Mapping[str, object]) -> tuple[str, str]:
    character_name = snapshot.get("character_name")
    events = snapshot.get("events", [])
    if not isinstance(events, list):
        return "", ""
    for event in events:
        if not isinstance(event, Mapping):
            continue
        if event.get("character_name") == character_name:
            speech = event.get("speech", "")
            effect = event.get("effect", "")
            return (
                speech if isinstance(speech, str) else "",
                effect if isinstance(effect, str) else "",
            )
    return "", ""


def _public_visual_actions(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(action) for action in value if isinstance(action, dict)]


def _redact_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {str(key): item for key, item in value.items() if str(key) != "api_key"}
