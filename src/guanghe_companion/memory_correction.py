"""Shared correction semantics for chat, album, pending confirmation and upgrades.

A replacement has its own evidence. Previous values stay on the superseded row;
they must not be inherited into metadata which drives current recall or speech.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import re
from typing import Mapping
from .memory_source_spans import SPAN_FIELDS, source_span_metadata

FACT_FIELDS = frozenset({"fact_slot", "fact_domain", "fact_value", "fact_subject", "fact_predicate"})
PLAN_FIELDS = frozenset({"plan_status", "time_expression", "expiry_basis", "expiry_note"})
CONTENT_FIELDS = FACT_FIELDS | PLAN_FIELDS | SPAN_FIELDS | {
    "profile_field", "original_quote", "evidence_quote", "source_text",
    "source_memory_ids", "supersedes_memory_id", "message_id",
    "confidence_reason", "extraction",
}


def _typed_literal_supported(value: object, summary: str) -> bool:
    """Prove every normalized scalar leaf in the text that will be saved.

    The caller owns the explicit field schema. This is literal support, not a
    model-generated entailment claim or a parser for arbitrary paraphrases.
    Numbers and JSON true/false/null require whole literals, so 7 is not proved
    by 17 and false is not proved by the English word falsehood.
    """
    if isinstance(value, Mapping):
        return (all(_typed_literal_supported(child, summary) for child in value.values())
                if value else "{}" in summary)
    if isinstance(value, (list, tuple)):
        return (all(_typed_literal_supported(child, summary) for child in value)
                if value else "[]" in summary)
    if isinstance(value, str):
        return bool(value) and (value in summary
            or json.dumps(value, ensure_ascii=False) in summary)
    literal = json.dumps(value, ensure_ascii=False, allow_nan=False)
    return re.search(r"(?<![A-Za-z0-9_.+-])" + re.escape(literal)
                     + r"(?![A-Za-z0-9_.+-])", summary) is not None


def _correction_fact_value(incoming: Mapping[str, object], summary: str) -> object:
    atoms = {"fact_slot", "fact_domain", "fact_value"}
    if (not atoms <= incoming.keys()
            or any(not isinstance(incoming[key], str) or not incoming[key]
                   for key in ("fact_slot", "fact_domain"))):
        raise ValueError("correction fact metadata must match its current summary")
    value = incoming["fact_value"]
    # Preserve the pre-existing string correction contract exactly.
    if isinstance(value, str):
        if not value or value not in summary:
            raise ValueError("correction fact metadata must match its current summary")
        return value
    from .emotional_memory import MAX_MEMORY_TEXT_LENGTH, _clean_text, _sanitize_metadata

    sanitized = _sanitize_metadata({"fact_value": value})
    if "fact_value" not in sanitized:
        raise ValueError("correction fact_value must be a supported literal")
    normalized = sanitized["fact_value"]
    if isinstance(value, (list, tuple)) and len(normalized) != len(value):
        raise ValueError("correction fact_value must not be truncated")
    if not _typed_literal_supported(normalized, _clean_text(summary, MAX_MEMORY_TEXT_LENGTH)):
        raise ValueError("correction fact_value requires every scalar leaf in the saved summary")
    return normalized


def correction_metadata(previous, summary: str, supplied: Mapping[str, object] | None = None,
                        *, source_id: str = "") -> dict[str, object]:
    """Create current content metadata without copying previous fact atoms.

    Host-validated structured callers supply all three fact fields. Free-text
    edits reuse the existing literal parser; unknown wording remains a note.
    Stable event/legacy identifiers are retained for replay protection.
    """
    metadata = {key: value for key, value in previous.metadata.items() if key not in CONTENT_FIELDS}
    incoming = dict(supplied or {})
    atoms = {"fact_slot", "fact_domain", "fact_value"}
    if atoms.intersection(incoming):
        incoming["fact_value"] = _correction_fact_value(incoming, summary)
        metadata.update(incoming)
    else:
        from .chat_memory import _fact_view

        # These are existing canonical summaries; convert only their fixed
        # prefix so the ordinary literal parser can inspect the new text.
        parse_text = re.sub(r"^用户希望被称呼为", "请叫我", summary)
        parse_text = re.sub(r"^用户的姓名是", "我的名字是", parse_text)
        parse_text = re.sub(r"^用户职业是", "我的职业是", parse_text)
        parsed = _fact_view(replace(previous, summary=parse_text, source="user_correction",
                                   user_confirmed=True, metadata=metadata))
        metadata.update({key: value for key, value in parsed.metadata.items() if key in FACT_FIELDS})
        metadata.update(incoming)
        metadata.update(speaker="user", scene="companion_chat", original_quote=summary,
                        evidence_quote=summary, confidence_reason="用户明确更正；结构字段仅由当前更正文解析",
                        recorded_at=datetime.now(timezone.utc).isoformat())
        if source_id:
            metadata["message_id"] = source_id
        metadata.update(source_span_metadata(summary, summary))
    # These are proposal validation fields, not ongoing dependencies of an
    # accepted replacement. The actual revision chain is supersedes.
    metadata.pop("source_memory_ids", None)
    metadata.pop("supersedes_memory_id", None)
    metadata["corrected_by_user"] = True
    return metadata


def repair_legacy_correction(entry):
    """Repair only old corrected rows whose semantic atoms contradict the text.

    Ordinary existing facts are left unchanged. Plans with a matching literal
    value/time and an explicit uncompleted label retain their typed semantics.
    """
    if (entry.source != "user_correction" or not entry.metadata.get("corrected_by_user")
            or not FACT_FIELDS.intersection(entry.metadata)):
        return entry
    meta = entry.metadata
    if "fact_value" in meta and not isinstance(meta["fact_value"], str):
        # These types were not supported by the old free-text correction
        # parser. A current, proved typed value must survive a legacy upgrade.
        # Unsupported or contradictory old values still take the repair path.
        try:
            _correction_fact_value(meta, entry.summary)
        except (TypeError, ValueError):
            pass
        else:
            return entry
    if (meta.get("plan_status") == "planned" and "未确认完成" in entry.summary
            and isinstance(meta.get("fact_value"), str) and meta["fact_value"] in entry.summary
            and (not meta.get("time_expression") or str(meta["time_expression"]) in entry.summary)):
        return entry
    normalized = correction_metadata(entry, entry.summary)
    before = {key: meta[key] for key in FACT_FIELDS | PLAN_FIELDS if key in meta}
    after = {key: normalized[key] for key in FACT_FIELDS | PLAN_FIELDS if key in normalized}
    if before == after:
        return entry
    return replace(entry, metadata=normalized, version=entry.version + 1)
