from hashlib import sha256
from collections.abc import Mapping


SPAN_FIELDS = frozenset({"source_span_start", "source_span_end", "source_text_digest", "source_claim_digest", "source_support_spans"})


def source_span_metadata(text: str, quote: str, *, start: int | None = None) -> dict:
    if not text or not quote:
        return {}
    if start is None:
        if text.count(quote) != 1:
            return {}
        start = text.index(quote)
    end = start + len(quote)
    if start < 0 or text[start:end] != quote:
        raise ValueError("claim span does not match its source text")
    return {"source_span_start": start, "source_span_end": end,
            "source_text_digest": sha256(text.encode("utf-8")).hexdigest(),
            "source_claim_digest": sha256(quote.encode("utf-8")).hexdigest()}


def _span(entry):
    meta = entry.metadata
    text = meta.get("original_quote")
    start, end = meta.get("source_span_start"), meta.get("source_span_end")
    if (not isinstance(text, str) or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(text)
            or sha256(text.encode("utf-8")).hexdigest() != meta.get("source_text_digest")
            or sha256(text[start:end].encode("utf-8")).hexdigest() != meta.get("source_claim_digest")):
        return None
    return start, end, text[start:end]


def _source_group(entry):
    return (entry.owner_id, entry.character_id, entry.metadata.get("message_id"),
            entry.metadata.get("source_text_digest"))


def _claim_spans(entry):
    primary = _span(entry)
    if primary is None:
        return None
    support = entry.metadata.get("source_support_spans", [])
    if (not isinstance(support, list) or len(support) > 8
            or any(not isinstance(part, (list, tuple)) or len(part) != 2
                or any(type(value) is not int for value in part)
                or not 0 <= part[0] < part[1] <= len(entry.metadata["original_quote"])
                for part in support)):
        return None
    return (primary[:2], *(tuple(part) for part in support))


def overlapping_claims(entries, withdrawn):
    targets = tuple(withdrawn)
    result = {entry.memory_id: entry for entry in targets}
    for entry in entries:
        if not entry.metadata.get("message_id"):
            continue
        for target in targets:
            if _source_group(entry) != _source_group(target):
                continue
            spans, removed_span = _claim_spans(entry), _span(target)
            if (spans is None or removed_span is None
                    or any(max(part[0], removed_span[0]) < min(part[1], removed_span[1]) for part in spans)):
                result[entry.memory_id] = entry
                break
    # 只从用户撤回的原始片段扩展一次，不能通过整段卡片继续撤回不相交的独立事实。
    return list(result.values())


def resolve_source_spans(store, bindings, *, expected_epoch: int, now: int,
                         scope: str = "companion", max_sources: int = 8) -> dict:
    if (not isinstance(bindings, Mapping) or not bindings or len(bindings) > max_sources
            or any(not isinstance(key, str) or not key or not isinstance(value, str) or not value
                   for key, value in bindings.items())):
        raise ValueError("source expansion requires bounded memory ID and fingerprint bindings")
    snapshot = store.read_context_snapshot(now=now)
    if snapshot.context_epoch != expected_epoch:
        return {"status": "unavailable", "reason": "stale_epoch", "context_epoch": snapshot.context_epoch, "spans": []}
    by_id = {entry.memory_id: entry for entry in snapshot.entries}
    spans, unavailable = [], {}
    for memory_id, fingerprint in bindings.items():
        entry = by_id.get(memory_id)
        if (entry is None or entry.owner_id != store.owner_id or entry.character_id != store.character_id
                or entry.evidence_fingerprint() != fingerprint or not entry.is_active(now=now, scope=scope)):
            unavailable[memory_id] = "invalid_or_revoked_source"
            continue
        span = _span(entry)
        parts = _claim_spans(entry)
        if span is None or parts is None or not entry.metadata.get("message_id"):
            unavailable[memory_id] = "unbound_source_span"
            continue
        blocked = False
        for sibling in snapshot.entries:
            if sibling.memory_id == memory_id or _source_group(sibling) != _source_group(entry):
                continue
            if sibling.is_active(now=now, scope=scope):
                continue
            withdrawn = _span(sibling)
            if withdrawn is None or any(max(part[0], withdrawn[0]) < min(part[1], withdrawn[1]) for part in parts):
                blocked = True
                break
        if blocked:
            unavailable[memory_id] = "withdrawn_overlapping_span"
            continue
        spans.append({"memory_id": memory_id, "memory_fingerprint": fingerprint, "version": entry.version,
                      "source_id": entry.metadata["message_id"], "source_fingerprint": entry.metadata["source_text_digest"],
                      "start": span[0], "end": span[1], "text": span[2], "scope": entry.scope})
    final_epoch = store.current_context_epoch(now=now)
    if final_epoch != expected_epoch:
        return {"status": "unavailable", "reason": "stale_epoch", "context_epoch": final_epoch, "spans": []}
    return {"status": "sufficient" if spans and not unavailable else "insufficient" if spans else "unknown",
            "context_epoch": expected_epoch, "spans": spans, "unavailable_sources": unavailable}
