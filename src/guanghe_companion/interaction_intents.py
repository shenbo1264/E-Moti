from __future__ import annotations

from dataclasses import dataclass

DEFAULT_INTENT_TTL_MS = 5000
DEFAULT_INTENT_PRIORITY = 50
LLM_SOURCE = "llm"
MAX_INTENT_HINT_LENGTH = 40
MAX_INTERACTION_INTENTS = 3

ALLOWED_INTERACTION_INTENTS = frozenset(
    {
        "ask_comfort",
        "invite_play",
        "offer_rest",
        "gentle_reminder",
        "stay_quiet",
        "celebrate",
        "ask_preference",
    }
)


@dataclass(frozen=True, slots=True)
class InteractionIntent:
    intent_id: str
    ttl_ms: int
    priority: int
    source: str = LLM_SOURCE

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.intent_id,
            "ttl_ms": self.ttl_ms,
            "priority": self.priority,
            "source": self.source,
        }


def interaction_intents_from_payload_row(row: object) -> tuple[InteractionIntent, ...]:
    if not isinstance(row, dict):
        return ()
    if row.get("type") != "speech":
        return ()
    hint = row.get("intent_hint", "")
    if not isinstance(hint, str):
        return ()
    intent_id = _clean_intent_hint(hint)
    if intent_id not in ALLOWED_INTERACTION_INTENTS:
        return ()
    return (
        InteractionIntent(
            intent_id=intent_id,
            ttl_ms=DEFAULT_INTENT_TTL_MS,
            priority=DEFAULT_INTENT_PRIORITY,
            source=LLM_SOURCE,
        ),
    )


def interaction_intents_from_payload_rows(rows: object) -> tuple[InteractionIntent, ...]:
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or not rows:
        return ()
    intents: list[InteractionIntent] = []
    seen: set[str] = set()
    for row in rows[:MAX_INTERACTION_INTENTS]:
        for intent in interaction_intents_from_payload_row(row):
            if intent.intent_id in seen:
                continue
            seen.add(intent.intent_id)
            intents.append(intent)
    return tuple(intents)


def interaction_intents_from_dicts(raw_intents: object) -> tuple[InteractionIntent, ...]:
    if not isinstance(raw_intents, list):
        return ()
    intents: list[InteractionIntent] = []
    seen: set[str] = set()
    for raw in raw_intents[:MAX_INTERACTION_INTENTS]:
        if not isinstance(raw, dict):
            continue
        intent_id = raw.get("id")
        ttl_ms = raw.get("ttl_ms")
        priority = raw.get("priority")
        source = raw.get("source", LLM_SOURCE)
        if not isinstance(intent_id, str) or intent_id not in ALLOWED_INTERACTION_INTENTS or intent_id in seen:
            continue
        if isinstance(ttl_ms, bool) or not isinstance(ttl_ms, int) or ttl_ms <= 0:
            continue
        if isinstance(priority, bool) or not isinstance(priority, int):
            continue
        if source != LLM_SOURCE:
            continue
        seen.add(intent_id)
        intents.append(InteractionIntent(intent_id=intent_id, ttl_ms=ttl_ms, priority=priority, source=source))
    return tuple(intents)


def _clean_intent_hint(value: str) -> str:
    text = value.strip()
    if len(text) > MAX_INTENT_HINT_LENGTH or _has_control_character(text):
        return ""
    return text


def _has_control_character(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)
