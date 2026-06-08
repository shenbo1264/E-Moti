from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .controller import CompanionController
from .dialogue import DialogueRequest
from .expression_settings import ExpressionSettings, normalize_expression_settings

DEFAULT_LLM_SMOKE_PROMPTS = (
    "我刚打开桌面，脑子有点空，星汐，安静陪我一下好吗？",
    "下班了，我想和你玩一小会儿，别太正经，可以开心一点。",
    "我突然回来了，你可以露出一点惊讶的神态，抬头看看我吗？",
    "已经很晚了，我有点困倦，想听你软软地说句晚安。",
    "我想专注一会儿，但不要被监督，你在旁边轻轻陪我就好。",
    "刚才有点难过，心里沉沉的，你能靠近一点吗？",
    "我轻轻摸了摸星汐的头，看看她会有什么反应。",
    "你还在这里吗？我想确认一下。",
    "我今天完成了一件小事，想让你知道。",
    "我要睡了，星汐，今晚也一起安静收尾吧。",
)
_DEFAULT_EXPRESSION_CUE_PROBE_ROWS = (
    # Prompts intentionally do not include bracket tags; the LLM must infer the tag from player-facing wording.
    # Keep these as explicit emotion/expression requests so they can catch prompt regressions.
    ("joy", "我刚完成一件小事，心里很开心。星汐，请露出开心的神态陪我庆祝一下。", "joy"),
    ("sadness", "我刚才真的有点难过和低落。星汐，请露出一点难过的神态，靠近一点陪我。", "sadness"),
    ("sleepy", "已经很晚了，我困得眼睛快睁不开。星汐，请用困倦的神态轻轻说晚安。", "sleepy"),
    ("focused", "我想专注学习一会儿，不要监督我。星汐，请露出专注的神态安静陪在旁边。", "focused"),
    ("surprised", "我突然回到桌面了。星汐，请露出一点惊讶的神态，抬头看看我。", "surprised"),
)
STATE_GUARD_FIELDS = (
    "character_id",
    "character_name",
    "focus",
    "charge",
    "stability",
    "mood",
    "trust",
    "coins",
    "exp",
    "level",
    "mode",
    "resting",
    "inventory",
    "unlocks",
    "goal",
    "player_alias",
    "relationship_stage",
    "next_relationship_unlock",
    "memory_log",
    "long_term_memory",
    "motion",
)


@dataclass(frozen=True, slots=True)
class LLMExpressionCueProbeCase:
    case_id: str
    prompt: str
    expected_expression_id: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "prompt_preview": self.prompt[:60],
            "expected_expression_id": self.expected_expression_id,
        }


DEFAULT_EXPRESSION_CUE_PROBES = tuple(
    LLMExpressionCueProbeCase(*entry) for entry in _DEFAULT_EXPRESSION_CUE_PROBE_ROWS
)


@dataclass(frozen=True, slots=True)
class LLMExpressionCueProbeResult:
    case: LLMExpressionCueProbeCase
    ok: bool
    reason: str
    speech_len: int
    speech_preview: str
    effect: str
    expression_ids: tuple[str, ...]
    motion_ids: tuple[str, ...]
    visual_actions: list[dict[str, object]]
    interaction_intents: list[dict[str, object]]
    fallback_reason: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            **self.case.to_public_dict(),
            "ok": self.ok,
            "reason": self.reason,
            "speech_len": self.speech_len,
            "speech_preview": self.speech_preview,
            "effect": self.effect,
            "expression_ids": list(self.expression_ids),
            "motion_ids": list(self.motion_ids),
            "visual_actions": self.visual_actions,
            "interaction_intents": self.interaction_intents,
            "fallback_reason": self.fallback_reason,
        }


@dataclass(frozen=True, slots=True)
class LLMExpressionCueProbeReport:
    ok: bool
    reason: str
    diagnostic: dict[str, object]
    cases: tuple[LLMExpressionCueProbeResult, ...]
    speech_quality: dict[str, object]
    state_mutation_check: dict[str, object]
    growth_before: dict[str, object]
    growth_after: dict[str, object]
    history_len: int

    def to_public_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "diagnostic": _redact_mapping(self.diagnostic),
            "probe_count": len(self.cases),
            "passed_count": sum(1 for case in self.cases if case.ok),
            "failed_count": sum(1 for case in self.cases if not case.ok),
            "cases": [case.to_public_dict() for case in self.cases],
            "speech_quality": dict(self.speech_quality),
            "state_mutation_check": dict(self.state_mutation_check),
            "growth_before": dict(self.growth_before),
            "growth_after": dict(self.growth_after),
            "history_len": self.history_len,
        }


@dataclass(frozen=True, slots=True)
class LLMDialogueSmokeTurn:
    turn: int
    user_preview: str
    speech_len: int
    speech_preview: str
    effect: str
    visual_actions: list[dict[str, object]]
    interaction_intents: list[dict[str, object]]
    fallback_reason: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "turn": self.turn,
            "user_preview": self.user_preview,
            "speech_len": self.speech_len,
            "speech_preview": self.speech_preview,
            "effect": self.effect,
            "visual_actions": self.visual_actions,
            "interaction_intents": self.interaction_intents,
            "fallback_reason": self.fallback_reason,
        }


@dataclass(frozen=True, slots=True)
class LLMDialogueSmokeReport:
    ok: bool
    reason: str
    diagnostic: dict[str, object]
    turns: tuple[LLMDialogueSmokeTurn, ...]
    visual_action_coverage: dict[str, object]
    speech_quality: dict[str, object]
    state_mutation_check: dict[str, object]
    growth_before: dict[str, object]
    growth_after: dict[str, object]
    history_len: int

    def to_public_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "diagnostic": _redact_mapping(self.diagnostic),
            "turns": [turn.to_public_dict() for turn in self.turns],
            "visual_action_coverage": dict(self.visual_action_coverage),
            "speech_quality": dict(self.speech_quality),
            "state_mutation_check": dict(self.state_mutation_check),
            "growth_before": dict(self.growth_before),
            "growth_after": dict(self.growth_after),
            "history_len": self.history_len,
        }


def _default_expression_cue_probe_cases() -> tuple[LLMExpressionCueProbeCase, ...]:
    return DEFAULT_EXPRESSION_CUE_PROBES


def run_llm_dialogue_smoke(
    settings: ExpressionSettings | Mapping[str, object],
    *,
    prompts: Iterable[str] = DEFAULT_LLM_SMOKE_PROMPTS,
    min_expression_actions: int = 0,
    min_motion_actions: int = 0,
    min_speech_chars: int = 0,
    max_speech_chars: int = 0,
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
        return run_configured_llm_dialogue_smoke(
            controller,
            prompts=prompts,
            min_expression_actions=min_expression_actions,
            min_motion_actions=min_motion_actions,
            min_speech_chars=min_speech_chars,
            max_speech_chars=max_speech_chars,
        )


def run_llm_expression_cue_probes(
    settings: ExpressionSettings | Mapping[str, object],
    *,
    cases: Iterable[LLMExpressionCueProbeCase] = _default_expression_cue_probe_cases(),
    min_speech_chars: int = 0,
    max_speech_chars: int = 0,
) -> LLMExpressionCueProbeReport:
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
        return run_configured_llm_expression_cue_probes(
            controller,
            cases=cases,
            min_speech_chars=min_speech_chars,
            max_speech_chars=max_speech_chars,
        )


def run_configured_llm_dialogue_smoke(
    controller: CompanionController,
    *,
    prompts: Iterable[str] = DEFAULT_LLM_SMOKE_PROMPTS,
    min_expression_actions: int = 0,
    min_motion_actions: int = 0,
    min_speech_chars: int = 0,
    max_speech_chars: int = 0,
) -> LLMDialogueSmokeReport:
    min_expression_actions = _non_negative_int(min_expression_actions)
    min_motion_actions = _non_negative_int(min_motion_actions)
    min_speech_chars = _non_negative_int(min_speech_chars)
    max_speech_chars = _non_negative_int(max_speech_chars)
    diagnostic = _redact_mapping(controller.test_expression_provider())
    if diagnostic.get("ok") is not True:
        return _report(
            ok=False,
            reason=f"diagnostic:{diagnostic.get('reason') or 'failed'}",
            diagnostic=diagnostic,
            controller=controller,
            turns=(),
            growth_before=_growth_snapshot(controller.get_snapshot()),
            min_speech_chars=min_speech_chars,
            max_speech_chars=max_speech_chars,
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
                interaction_intents=_public_interaction_intents(snapshot.get("interaction_intents", [])),
                fallback_reason=fallback_reason,
            )
        )

    growth_after = _growth_snapshot(controller.get_snapshot())
    state_mutation_check = _growth_mutation_check(growth_before, growth_after)
    visual_action_coverage = _visual_action_coverage(turns)
    speech_quality = _speech_quality(turns, min_speech_chars=min_speech_chars, max_speech_chars=max_speech_chars)
    if state_mutation_check["ok"] is False and not reason:
        reason = "growth_mutated"
    if not reason:
        expression_count = int(visual_action_coverage["expression_count"])
        motion_count = int(visual_action_coverage["motion_count"])
        if expression_count < min_expression_actions or motion_count < min_motion_actions:
            reason = (
                "visual_action_coverage:"
                f"expressions={expression_count}/{min_expression_actions},"
                f"motions={motion_count}/{min_motion_actions}"
            )
    if speech_quality["violations"] and not reason:
        reason = (
            "speech_quality:"
            f"empty={speech_quality['empty_count']},"
            f"short={speech_quality['short_count']},"
            f"long={speech_quality['long_count']}"
        )
    return LLMDialogueSmokeReport(
        ok=not reason,
        reason=reason,
        diagnostic=diagnostic,
        turns=tuple(turns),
        visual_action_coverage=visual_action_coverage,
        speech_quality=speech_quality,
        state_mutation_check=state_mutation_check,
        growth_before=growth_before,
        growth_after=growth_after,
        history_len=len(controller.get_snapshot().get("dialogue_history", [])),
    )


def run_configured_llm_expression_cue_probes(
    controller: CompanionController,
    *,
    cases: Iterable[LLMExpressionCueProbeCase] = _default_expression_cue_probe_cases(),
    min_speech_chars: int = 0,
    max_speech_chars: int = 0,
) -> LLMExpressionCueProbeReport:
    probe_cases = tuple(cases)
    min_speech_chars = _non_negative_int(min_speech_chars)
    max_speech_chars = _non_negative_int(max_speech_chars)
    diagnostic = _redact_mapping(controller.test_expression_provider())
    growth_before = _growth_snapshot(controller.get_snapshot())
    if diagnostic.get("ok") is not True:
        return _cue_probe_report(
            ok=False,
            reason=f"diagnostic:{diagnostic.get('reason') or 'failed'}",
            diagnostic=diagnostic,
            controller=controller,
            cases=(),
            growth_before=growth_before,
            min_speech_chars=min_speech_chars,
            max_speech_chars=max_speech_chars,
        )

    results: list[LLMExpressionCueProbeResult] = []
    turns: list[LLMDialogueSmokeTurn] = []
    reason = ""
    for index, case in enumerate(probe_cases, 1):
        snapshot = controller.submit_dialogue_request(
            DialogueRequest(case.prompt, source="desktop_pet"),
            include_ai_expression=True,
        )
        speech, effect = _first_companion_speech(snapshot)
        visual_actions = _public_visual_actions(snapshot.get("visual_actions", []))
        interaction_intents = _public_interaction_intents(snapshot.get("interaction_intents", []))
        expression_ids, motion_ids = _visual_action_ids(visual_actions)
        fallback_reason = str(getattr(controller.ai_expressor, "last_fallback_reason", "") or "")
        case_reason = _cue_case_reason(case, expression_ids, fallback_reason)
        if case_reason and not reason:
            reason = f"cue:{case.case_id}:{case_reason}"
        results.append(
            LLMExpressionCueProbeResult(
                case=case,
                ok=not case_reason,
                reason=case_reason,
                speech_len=len(speech),
                speech_preview=speech[:60],
                effect=effect,
                expression_ids=expression_ids,
                motion_ids=motion_ids,
                visual_actions=visual_actions,
                interaction_intents=interaction_intents,
                fallback_reason=fallback_reason,
            )
        )
        turns.append(
            LLMDialogueSmokeTurn(
                turn=index,
                user_preview=case.prompt[:36],
                speech_len=len(speech),
                speech_preview=speech[:60],
                effect=effect,
                visual_actions=visual_actions,
                interaction_intents=interaction_intents,
                fallback_reason=fallback_reason,
            )
        )

    state_mutation_check = _growth_mutation_check(growth_before, _growth_snapshot(controller.get_snapshot()))
    speech_quality = _speech_quality(turns, min_speech_chars=min_speech_chars, max_speech_chars=max_speech_chars)
    if state_mutation_check["ok"] is False and not reason:
        reason = "growth_mutated"
    if speech_quality["violations"] and not reason:
        reason = (
            "speech_quality:"
            f"empty={speech_quality['empty_count']},"
            f"short={speech_quality['short_count']},"
            f"long={speech_quality['long_count']}"
        )
    return LLMExpressionCueProbeReport(
        ok=not reason,
        reason=reason,
        diagnostic=diagnostic,
        cases=tuple(results),
        speech_quality=speech_quality,
        state_mutation_check=state_mutation_check,
        growth_before=growth_before,
        growth_after=_growth_snapshot(controller.get_snapshot()),
        history_len=len(controller.get_snapshot().get("dialogue_history", [])),
    )


def _cue_probe_report(
    *,
    ok: bool,
    reason: str,
    diagnostic: dict[str, object],
    controller: CompanionController,
    cases: tuple[LLMExpressionCueProbeResult, ...],
    growth_before: dict[str, object],
    min_speech_chars: int,
    max_speech_chars: int,
) -> LLMExpressionCueProbeReport:
    turns = tuple(
        LLMDialogueSmokeTurn(
            turn=index,
            user_preview=case.case.prompt[:36],
            speech_len=case.speech_len,
            speech_preview=case.speech_preview,
            effect=case.effect,
            visual_actions=case.visual_actions,
            interaction_intents=case.interaction_intents,
            fallback_reason=case.fallback_reason,
        )
        for index, case in enumerate(cases, 1)
    )
    return LLMExpressionCueProbeReport(
        ok=ok,
        reason=reason,
        diagnostic=diagnostic,
        cases=cases,
        speech_quality=_speech_quality(
            turns,
            min_speech_chars=_non_negative_int(min_speech_chars),
            max_speech_chars=_non_negative_int(max_speech_chars),
        ),
        state_mutation_check=_growth_mutation_check(growth_before, _growth_snapshot(controller.get_snapshot())),
        growth_before=growth_before,
        growth_after=_growth_snapshot(controller.get_snapshot()),
        history_len=len(controller.get_snapshot().get("dialogue_history", [])),
    )


def _cue_case_reason(
    case: LLMExpressionCueProbeCase,
    expression_ids: tuple[str, ...],
    fallback_reason: str,
) -> str:
    if fallback_reason:
        return f"fallback:{fallback_reason}"
    if case.expected_expression_id not in expression_ids:
        return f"expected_expression:{case.expected_expression_id}"
    return ""


def _report(
    *,
    ok: bool,
    reason: str,
    diagnostic: dict[str, object],
    controller: CompanionController,
    turns: tuple[LLMDialogueSmokeTurn, ...],
    growth_before: dict[str, object],
    min_speech_chars: int = 0,
    max_speech_chars: int = 0,
) -> LLMDialogueSmokeReport:
    return LLMDialogueSmokeReport(
        ok=ok,
        reason=reason,
        diagnostic=diagnostic,
        turns=turns,
        visual_action_coverage=_visual_action_coverage(turns),
        speech_quality=_speech_quality(
            turns,
            min_speech_chars=_non_negative_int(min_speech_chars),
            max_speech_chars=_non_negative_int(max_speech_chars),
        ),
        state_mutation_check=_growth_mutation_check(growth_before, _growth_snapshot(controller.get_snapshot())),
        growth_before=growth_before,
        growth_after=_growth_snapshot(controller.get_snapshot()),
        history_len=len(controller.get_snapshot().get("dialogue_history", [])),
    )


def _visual_action_ids(actions: Iterable[Mapping[str, object]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    expression_ids: set[str] = set()
    motion_ids: set[str] = set()
    for action in actions:
        action_type = action.get("type")
        action_id = action.get("id")
        if not isinstance(action_id, str) or not action_id:
            continue
        if action_type == "expression":
            expression_ids.add(action_id)
        elif action_type == "motion":
            motion_ids.add(action_id)
    return tuple(sorted(expression_ids)), tuple(sorted(motion_ids))


def _growth_snapshot(snapshot: Mapping[str, object]) -> dict[str, object]:
    return {field: deepcopy(snapshot.get(field)) for field in STATE_GUARD_FIELDS}


def _growth_mutation_check(before: Mapping[str, object], after: Mapping[str, object]) -> dict[str, object]:
    changed_fields = sorted(
        field
        for field, value in before.items()
        if after.get(field) != value
    )
    return {
        "ok": not changed_fields,
        "changed_fields": changed_fields,
    }


def _visual_action_coverage(turns: Iterable[LLMDialogueSmokeTurn]) -> dict[str, object]:
    expression_ids: set[str] = set()
    motion_ids: set[str] = set()
    for turn in turns:
        for action in turn.visual_actions:
            action_type = action.get("type")
            action_id = action.get("id")
            if not isinstance(action_id, str) or not action_id:
                continue
            if action_type == "expression":
                expression_ids.add(action_id)
            elif action_type == "motion":
                motion_ids.add(action_id)
    expressions = sorted(expression_ids)
    motions = sorted(motion_ids)
    return {
        "expression_count": len(expressions),
        "expression_ids": expressions,
        "motion_count": len(motions),
        "motion_ids": motions,
    }


def _speech_quality(
    turns: Iterable[LLMDialogueSmokeTurn],
    *,
    min_speech_chars: int,
    max_speech_chars: int,
) -> dict[str, object]:
    minimum = _non_negative_int(min_speech_chars)
    maximum = _non_negative_int(max_speech_chars)
    violations: list[dict[str, object]] = []
    empty_count = 0
    short_count = 0
    long_count = 0
    for turn in turns:
        speech_len = int(turn.speech_len)
        if speech_len <= 0:
            empty_count += 1
            violations.append({"turn": turn.turn, "kind": "empty", "speech_len": speech_len})
            continue
        if minimum and speech_len < minimum:
            short_count += 1
            violations.append({"turn": turn.turn, "kind": "short", "speech_len": speech_len})
        if maximum and speech_len > maximum:
            long_count += 1
            violations.append({"turn": turn.turn, "kind": "long", "speech_len": speech_len})
    return {
        "min_speech_chars": minimum,
        "max_speech_chars": maximum,
        "empty_count": empty_count,
        "short_count": short_count,
        "long_count": long_count,
        "violations": violations,
    }


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


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


def _public_interaction_intents(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(intent) for intent in value if isinstance(intent, dict)]


def _redact_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {str(key): item for key, item in value.items() if str(key) != "api_key"}
