"""Extractive, source-bound views; never a second authority for facts."""
from __future__ import annotations

from dataclasses import dataclass
import json

from .emotional_memory import EmotionalMemoryEntry, MemoryChapter
from .retrieval_evidence import grounded_shared_event


@dataclass(frozen=True, slots=True)
class LayeredEvidence:
    overview: dict[str, object]
    represented_ids: tuple[str, ...]
    level: str


def distinct_event_count(source_sets) -> int:
    """Connected source groups count events, not supporting-document count."""
    groups = []
    for source_ids in source_sets:
        merged = set(source_ids)
        if not merged:
            continue
        separate = []
        for group in groups:
            if merged.intersection(group):
                merged.update(group)
            else:
                separate.append(group)
        # A new multi-source record can connect earlier disjoint groups.
        groups = separate + [merged]
    return len(groups)


def build_layers(entries: tuple[EmotionalMemoryEntry, ...], *, chapters: tuple[MemoryChapter, ...] = (),
                 detail: bool = False, enabled: bool = True, budget_chars: int = 4000) -> LayeredEvidence:
    if not enabled or detail:
        return LayeredEvidence({}, (), "L2")
    # User facts retain their typed raw cards. A stage overview is only about
    # completed shared events, not a mix of user facts and imagined history.
    selected = tuple(entry for entry in entries if grounded_shared_event(entry))
    if not selected:
        return LayeredEvidence({}, (), "L2")
    claims = []
    seen_sources = set()
    represented = []
    for entry in selected:
        identity = (tuple(sorted(entry.source_ids)), entry.summary)
        represented.append(entry.memory_id)
        if identity in seen_sources:
            continue
        seen_sources.add(identity)
        claim = {"text": entry.summary, "source_memory_id": entry.memory_id, "source_ids": list(entry.source_ids),
                 "source_fingerprint": entry.evidence_fingerprint(), "occurred_at": entry.occurred_at}
        if len(json.dumps(claims + [claim], ensure_ascii=False)) > max(256, budget_chars - 600):
            represented.pop()
            break
        claims.append(claim)
    if not claims:
        return LayeredEvidence({}, (), "L2")
    selected_ids = {entry.memory_id for entry in selected}
    chapter_ids = [chapter.chapter_id for chapter in chapters if selected_ids.intersection(chapter.source_memory_ids)]
    times = [int(claim["occurred_at"]) for claim in claims]
    overview = {"level": "L1", "catalog": {"topic": "已记录的共同经历", "period": [min(times), max(times)],
                "event_count": distinct_event_count(c["source_ids"] for c in claims), "chapter_ids": chapter_ids[:4]},
                "claims": claims, "expansion": "ask_for_details_to_read_valid_sources"}
    return LayeredEvidence(overview, tuple(represented), "L1")


def validate_layers(overview: dict[str, object], entries: tuple[EmotionalMemoryEntry, ...]) -> bool:
    """Deterministic entailment for extractive claims, not an LLM judge score."""
    by_id = {entry.memory_id: entry for entry in entries}
    claims = overview.get("claims", ())
    if not isinstance(claims, (list, tuple)):
        return False
    for claim in claims:
        if not isinstance(claim, dict):
            return False
        entry = by_id.get(claim.get("source_memory_id"))
        if (entry is None or not grounded_shared_event(entry) or claim.get("text") != entry.summary
                or claim.get("source_fingerprint") != entry.evidence_fingerprint()):
            return False
    return bool(claims)
