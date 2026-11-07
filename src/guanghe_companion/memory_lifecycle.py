from dataclasses import replace
from hashlib import sha256

from .memory_source_spans import SPAN_FIELDS, overlapping_claims
from .memory_time import temporal_metadata


def origin_revoked(document, origins, *, retained_origins=()) -> bool:
    origins = set(origins)
    return bool((origins - set(retained_origins)).intersection(document.get("retired_origins", ())) or
                {sha256(origin.encode("utf-8")).hexdigest() for origin in origins}.intersection(
                    document.get("purged_origin_digests", ())))


def revision_ids(entries, memory_id) -> set[str]:
    ids = {memory_id}
    while True:
        related = {entry.memory_id for entry in entries if entry.supersedes in ids}
        related.update(entry.supersedes for entry in entries if entry.memory_id in ids and entry.supersedes)
        if related <= ids:
            return ids
        ids.update(related)


def forget_fact_memory(store, memory_id, *, now: int, expected_epoch: int | None = None):
    with store._document() as document:
        if expected_epoch is not None and expected_epoch != document["context_epoch"]:
            raise ValueError("stale memory forget epoch")
        entries = store._entries(document)
        target = next((entry for entry in entries if entry.memory_id == memory_id), None)
        if target is None:
            return None
        ids = revision_ids(entries, memory_id)
        affected = [entry for entry in entries if entry.memory_id in ids]
        if any(not entry.deleted for entry in affected):
            store._retire(document, affected, now=now)
        return replace(target, deleted=True, updated_at=now)


def change_memory(store, memory_id, replacement, *, now: int, effective_at: int,
                  expected_epoch: int | None = None):
    memory = store._validate(replacement)
    with store._document() as document:
        if expected_epoch is not None and expected_epoch != document["context_epoch"]:
            raise ValueError("stale memory change epoch")
        entries = store._entries(document)
        old = next((entry for entry in entries if entry.memory_id == memory_id and not entry.deleted), None)
        if old is None:
            raise KeyError(f"active memory not found: {memory_id}")
        if memory.deleted or any(entry.memory_id == memory.memory_id for entry in entries):
            raise ValueError("change must supply a new active memory id")
        if (memory.memory_id in document.get("retired_ids", ())
                or origin_revoked(document, store._origins(memory))):
            raise ValueError("change source has been revoked")
        if (type(effective_at) is not int or effective_at <= old.valid_from or effective_at > now
                or (old.valid_until and effective_at >= old.valid_until)):
            raise ValueError("change must close a positive existing interval; future events remain plans")
        basis = document.get("time_basis", "logical")
        meta = temporal_metadata(time_basis=basis, timezone_name=document.get("timezone", ""),
            now=now, occurred_at=effective_at, valid_from=effective_at, valid_until=memory.valid_until)
        closed = replace(old, valid_until=effective_at, updated_at=now, version=old.version + 1)
        memory = replace(memory, supersedes=old.memory_id, valid_from=effective_at,
            occurred_at=effective_at, created_at=now, updated_at=now, version=old.version + 1,
            metadata={**memory.metadata, **meta, "lifecycle_action": "reality_change"})
        memory = store._validate(memory)
        store._invalidate_derived(document, {old.memory_id})
        document["entries"] = [memory.to_dict(), *(closed.to_dict() if entry.memory_id == old.memory_id
                              else entry.to_dict() for entry in entries)]
        document["context_epoch"] += 1
        return memory


def purge_memory(store, memory_id, *, now: int, expected_epoch: int | None = None) -> tuple[str, ...]:
    with store._document() as document:
        if expected_epoch is not None and expected_epoch != document["context_epoch"]:
            raise ValueError("stale memory purge epoch")
        entries = store._entries(document)
        if not any(entry.memory_id == memory_id for entry in entries):
            return ()
        # 用户删除一个事实时一并删除其纠错和现实变化链，避免历史重现。
        ids = revision_ids(entries, memory_id)
        targets = [entry for entry in entries if entry.memory_id in ids]
        affected = overlapping_claims(entries, targets)
        ids.update(entry.memory_id for entry in affected)
        groups = {(entry.metadata.get("message_id"), entry.metadata.get("source_text_digest"))
                  for entry in affected if entry.metadata.get("message_id")}
        store._retire(document, targets, now=now)
        origins = {origin for entry in affected for origin in store._origins(entry)}
        document["retired_origins"] = sorted(set(document.get("retired_origins", ())) - origins)
        document["purged_origin_digests"] = sorted(set(document.get("purged_origin_digests", ())) |
            {sha256(origin.encode("utf-8")).hexdigest() for origin in origins})
        pending = document.get("pending_candidates", {})
        document["pending_candidates"] = {key: row for key, row in pending.items()
            if not ids.intersection(row.get("source_fingerprints", {}))
            and not any("source:" + source in origins for source in row.get("entry", {}).get("source_ids", ()))
            and row.get("entry", {}).get("metadata", {}).get("message_id") not in {group[0] for group in groups}}
        tombstones = list(document.get("purged_memories", ()))
        tombstones.extend({"memory_id": entry.memory_id, "version": entry.version,
                           "fingerprint": entry.evidence_fingerprint()} for entry in affected)
        document["purged_memories"] = tombstones
        kept = []
        for entry in entries:
            if entry.memory_id in ids:
                continue
            if (entry.metadata.get("message_id"), entry.metadata.get("source_text_digest")) in groups:
                # 同源原文仍可能含被删除事实；保留独立事实，撤销整段原文展开。
                drop = SPAN_FIELDS | {"original_quote", "evidence_quote", "source_text"}
                entry = replace(entry, metadata={key: value for key, value in entry.metadata.items() if key not in drop},
                                version=entry.version + 1, updated_at=now)
                store._invalidate_derived(document, {entry.memory_id})
            kept.append(entry.to_dict())
        document["entries"] = kept
        return tuple(entry.memory_id for entry in affected)
