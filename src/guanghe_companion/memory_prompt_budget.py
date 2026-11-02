"""Trim whole evidence claims and keep their sufficiency verdict honest."""
from __future__ import annotations


def evidence_ids(memory: dict) -> set[str]:
    ids = {row.get("memory_id", "") for row in memory.get("shared_memories", []) if isinstance(row, dict)}
    ids.update(row.get("source_memory_id", "") for row in memory.get("memory_overview", {}).get("claims", [])
               if isinstance(row, dict))
    return ids - {""}


def _reconcile(memory: dict) -> None:
    overview = memory.get("memory_overview", {})
    claims = overview.get("claims", [])
    if overview and not claims:
        memory.pop("memory_overview", None)
    elif claims:
        from .memory_hierarchy import distinct_event_count
        catalog = overview.get("catalog", {})
        catalog["event_count"] = distinct_event_count(row.get("source_ids") or (row.get("source_memory_id"),) for row in claims)
        times = [row["occurred_at"] for row in claims if isinstance(row.get("occurred_at"), (int, float))]
        if times:
            catalog["period"] = [min(times), max(times)]
    kept = evidence_ids(memory)
    if "resolution_evidence" in memory:
        bindings = [row for row in memory["resolution_evidence"] if kept and
                    (not row.get("dependent_memory_ids") or kept.intersection(row["dependent_memory_ids"]))]
        if bindings:
            memory["resolution_evidence"] = bindings
        else:
            memory.pop("resolution_evidence")
    retrieval = memory.get("retrieval")
    if isinstance(retrieval, dict):
        retrieval.update(status="insufficient", budget_limited=True)
        for intent in retrieval.get("intent_status", []):
            previous = intent.get("source_ids", [])
            if previous and any(key not in kept for key in previous):
                intent["status"] = "insufficient"
                intent["source_ids"] = [key for key in previous if key in kept]


def trim_memory_evidence(memory: dict, *, preserve_one: bool = False) -> bool:
    """Remove one lowest-priority complete claim; never cut a fact's text.

    Alias proofs are kept atomically with the answers that depend on them.
    This mutates an already copied prompt view, never authoritative records.
    """
    raw = memory.get("shared_memories", [])
    claims = memory.get("memory_overview", {}).get("claims", [])
    if len(raw) + len(claims) > int(preserve_one):
        # Keep the leading item in each channel while possible.
        target = raw if len(raw) > 1 or not claims else claims
        target.pop()
        _reconcile(memory)
        return True
    external = memory.get("external_state", [])
    if external and not preserve_one:
        removed = external.pop()
        _reconcile(memory)
        for intent in memory.get("retrieval", {}).get("intent_status", []):
            if intent.get("route") == "live" and intent.get("authority") == removed.get("authority"):
                intent["status"] = "insufficient"
        return True
    if memory.get("resolution_evidence") and not evidence_ids(memory):
        memory.pop("resolution_evidence")
        _reconcile(memory)
        return True
    return False


def trim_memory_metadata(memory: dict) -> bool:
    """Optional diagnostics can shrink, but status and epoch cannot disappear."""
    retrieval = memory.get("retrieval", {})
    for key in ("instruction", "intent_status", "evidence_level", "reason"):
        if key in retrieval:
            retrieval.pop(key)
            return True
    return False


def trim_profile(memory: dict, *, keep_each: int = 0, include_boundaries: bool = False) -> bool:
    """Drop a derived profile value together with its value-bearing source key."""
    profile = memory.get("bond_profile", {})
    if not isinstance(profile, dict):
        return False
    names = ("stable_preferences", "shared_rituals", "active_story_threads")
    if include_boundaries:
        names += ("boundaries",)
    options = [name for name in names if isinstance(profile.get(name), list) and len(profile[name]) > keep_each]
    if not options:
        return False
    name = max(options, key=lambda key: len(profile[key]))
    value = profile[name].pop()
    evidence = profile.get("evidence", {})
    if isinstance(evidence, dict):
        evidence.pop(f"{name}:{value}", None)
    return True
