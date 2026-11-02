"""Bounded reads from projections of the existing authoritative memory document.

No model, second fact database, vector engine, or inference about new entities is
introduced here.  JSON1 replaces only selected canonical rows when recording
recall access.  Semantic writes continue through the existing lifecycle methods.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import re
import sqlite3
import time
from typing import TYPE_CHECKING, Iterable

from .memory_document import MemoryStorageError, _strict_json_loads, _write_initialization_receipt
from .memory_index_schema import ensure_schema, schema_ready

# The primary-key index is part of the explicitly owned schema. Requiring it
# for a bounded ID set prevents a no-ANALYZE SQLite planner from scanning every
# eligible row. Broad, unstructured and FTS searches retain their own plans.
_PRIMARY_LOOKUP = " INDEXED BY sqlite_autoindex_memory_index_entries_1"

if TYPE_CHECKING:
    from .emotional_memory import CoreBondProfile, EmotionalMemoryEntry, EmotionalMemoryStore, MemoryChapter


@dataclass(frozen=True, slots=True)
class IndexedMemoryQuery:
    scopes: tuple[str, ...] = ("companion",)
    subjects: tuple[str, ...] = ()
    predicates: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ()
    query: str = ""
    memory_ids: tuple[str, ...] | None = None
    limit: int = 64
    history: bool = False
    occurred_after: int = 0
    occurred_before: int = 0


@dataclass(frozen=True, slots=True)
class IndexedSourceEligibility:
    memory_id: str
    eligible: bool
    reason: str
    fingerprint: str = ""
    scope: str = ""
    valid_from: int = 0
    valid_until: int = 0


@dataclass(frozen=True, slots=True)
class IndexedMemorySnapshot:
    entries: tuple[EmotionalMemoryEntry, ...]
    profile: CoreBondProfile
    chapters: tuple[MemoryChapter, ...]
    context_epoch: int
    index_revision: int
    index_generation: str
    candidate_ids: tuple[str, ...]
    rows_loaded: int
    total_candidates: int
    source_entries: tuple[EmotionalMemoryEntry, ...]
    source_eligibility: dict[str, IndexedSourceEligibility]
    timings: dict[str, float] = field(default_factory=dict)
    lexical_backend: str = "fts5"


@dataclass(frozen=True, slots=True)
class MemoryIndexRecord:
    memory_id: str
    fingerprint: str
    scope: str
    version: int
    valid_from: int
    valid_until: int
    removed: bool
    eligible: bool


@dataclass(frozen=True, slots=True)
class MemoryIndexManifest:
    generation: str
    revision: int
    context_epoch: int
    records: tuple[MemoryIndexRecord, ...]
    removed_ids: tuple[str, ...]
    has_more: bool = False
    next_after_id: str = ""
    full_snapshot: bool = True


@dataclass(frozen=True, slots=True)
class SubjectResolution:
    mapping: dict[str, tuple[str, ...]]
    source_ids: tuple[str, ...]
    source_fingerprints: dict[str, str]
    context_epoch: int
    index_revision: int
    index_generation: str
    sources_by_input: dict[str, tuple[str, ...]]


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _raw_digest(value) -> str:
    """Disposable row-comparison cache, never a replacement for provenance."""
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                         sort_keys=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def lexical_tokens(text: str, *, for_query: bool = False) -> tuple[str, ...]:
    """Chinese unigrams/bigrams and casefolded word tokens, safe for FTS syntax.

    Multi-character queries use bigrams; one-character queries use the indexed
    unigram. Encoded tokens avoid SQLite unicode61's language assumptions and
    cannot introduce operators, quotes or wildcards into MATCH expressions.
    """
    tokens = []
    for part in re.findall(r"[\u3400-\u9fff]+|[\w]+", text.casefold(), flags=re.UNICODE):
        if all("\u3400" <= c <= "\u9fff" for c in part):
            terms = [part[i:i + 2] for i in range(len(part) - 1)]
            if not for_query or len(part) == 1:
                terms += list(part)
            tokens.extend("c" + "".join(f"{ord(char):04x}" for char in term) for term in terms)
        else:
            tokens.append("w" + part.encode("utf-8").hex())
    return tuple(dict.fromkeys(tokens))[:64 if for_query else 2048]


def _fact_fields(entry):
    # This is the existing conservative literal parser, not a second extractor.
    # Its accepted provenance and negative/hypothetical checks remain intact.
    from .retrieval_fact_schema import read_fact_view
    view = read_fact_view(entry)
    meta = view.metadata
    string = lambda key: meta.get(key, "") if isinstance(meta.get(key, ""), str) else ""
    subject = string("fact_subject") or ("user:self" if string("fact_slot") else "")
    predicate = string("fact_predicate") or string("fact_slot")
    entity = string("entity_id") or string("fact_entity_id") or subject
    aliases = []
    for key in ("subject_aliases", "entity_aliases", "fact_aliases"):
        values = meta.get(key, ())
        if isinstance(values, (list, tuple)):
            aliases.extend(v.strip()[:160] for v in values if isinstance(v, str) and v.strip())
    # Canonical payloads retain JSON types. The disposable TEXT/FTS projection
    # exposes their exact, stable literal representation, including 0/false.
    # Do not make strings look like quoted JSON strings or infer absent values.
    value = meta.get("fact_value")
    literal = value if isinstance(value, str) else (
        json.dumps(value, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":"), allow_nan=False) if value is not None else "")
    return (subject, entity, predicate, string("fact_slot"), string("fact_domain"),
            literal), tuple(dict.fromkeys(aliases))[:32]


def sync_projection(connection: sqlite3.Connection, document: dict) -> None:
    """Synchronize derived data before the canonical transaction commits."""
    from dataclasses import replace
    from .emotional_memory import EmotionalMemoryEntry, MemoryChapter, _clean_text

    ensure_schema(connection)
    meta = connection.execute("SELECT revision,dirty,profile,context_epoch FROM memory_index_meta WHERE id=1").fetchone()
    if not meta[1]:
        return
    owner, character = document.get("owner_id"), document.get("character_id")
    retired = set(document.get("retired_ids", ()))
    expired = set(document.get("expired_revisions", ()))
    old = {row[0]: row for row in connection.execute(
        "SELECT memory_id,fingerprint,deleted,expired,scope,payload,ordinal,lexical_tokens,rowid,raw_digest FROM memory_index_entries")}
    current = {}
    for ordinal, raw in enumerate(document.get("entries", ())):
        if not isinstance(raw, dict):
            continue
        key = _clean_text(raw.get("memory_id"), 80)
        digest = _raw_digest(raw)
        previous = old.get(key)
        if (previous is not None and previous[9] == digest
                and previous[2] == int(bool(raw.get("deleted", False)) or key in retired)):
            # The exact same raw row has already been validated for this
            # authority. Retired/expiry sets are still checked independently.
            # Duplicate IDs retain last-valid-owned-row semantics below.
            current[key] = (ordinal, None, digest)
            continue
        entry = EmotionalMemoryEntry.from_dict(raw)
        if entry is None or entry.owner_id != owner or entry.character_id != character:
            continue
        if entry.memory_id in retired:
            entry = replace(entry, deleted=True)
        current[entry.memory_id] = (ordinal, entry, digest)
    revision = int(meta[0]) + 1
    semantic_changes = []
    for key in old.keys() - current.keys():
        previous = old[key]
        semantic_changes.append((revision, key, previous[1], previous[4], 1))
        connection.execute("DELETE FROM memory_index_fts WHERE rowid=?", (previous[8],))
        for table in ("memory_index_entries", "memory_index_aliases", "memory_index_sources"):
            connection.execute("DELETE FROM " + table + " WHERE memory_id=?", (key,))
    ordinal_updates = []
    for key, (ordinal, entry, digest) in current.items():
        previous = old.get(key)
        if entry is None:
            is_expired = int(previous[1] in expired)
            if is_expired != previous[3]:
                semantic_changes.append((revision, key, previous[1], previous[4], int(previous[2] or is_expired)))
            if ordinal != previous[6] or is_expired != previous[3]:
                ordinal_updates.append((ordinal, is_expired, key))
            continue
        fingerprint = entry.evidence_fingerprint()
        is_expired = int(fingerprint in expired)
        payload = _json(entry.to_dict())
        changed = previous is None or (fingerprint, int(entry.deleted), is_expired, entry.scope) != (
            previous[1], previous[2], previous[3], previous[4])
        if changed:
            semantic_changes.append((revision, key, fingerprint, entry.scope, int(entry.deleted or is_expired)))
        # Touch-only saves still update the projected selected row, without an
        # embedding invalidation, FTS rebuild, or revision increment.
        if previous and not changed and previous[5] == payload:
            if previous[6] != ordinal or previous[9] != digest:
                connection.execute("UPDATE memory_index_entries SET ordinal=?,raw_digest=? WHERE memory_id=?",
                                   (ordinal, digest, key))
            continue
        facts, aliases = _fact_fields(entry)
        text = " ".join((entry.title, entry.summary, *entry.tags, *facts, *aliases))
        tokens = " ".join(lexical_tokens(text))
        connection.execute("""INSERT INTO memory_index_entries VALUES(
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(memory_id) DO UPDATE SET
            ordinal=excluded.ordinal,character_id=excluded.character_id,owner_id=excluded.owner_id,
            scope=excluded.scope,kind=excluded.kind,subject=excluded.subject,entity_id=excluded.entity_id,
            predicate=excluded.predicate,fact_slot=excluded.fact_slot,fact_domain=excluded.fact_domain,
            fact_value=excluded.fact_value,valid_from=excluded.valid_from,valid_until=excluded.valid_until,
            occurred_at=excluded.occurred_at,recorded_at=excluded.recorded_at,version=excluded.version,
            confidence=excluded.confidence,deleted=excluded.deleted,expired=excluded.expired,
            supersedes=excluded.supersedes,fingerprint=excluded.fingerprint,payload=excluded.payload,
            lexical_tokens=excluded.lexical_tokens,raw_digest=excluded.raw_digest""", (
            key, ordinal, character, owner, entry.scope, entry.kind, *facts, entry.valid_from,
            entry.valid_until, entry.occurred_at, entry.created_at, entry.version, entry.confidence,
            int(entry.deleted), is_expired, entry.supersedes, fingerprint, payload, tokens, digest))
        if changed or previous is None:
            connection.execute("DELETE FROM memory_index_aliases WHERE memory_id=?", (key,))
            if not entry.deleted:
                connection.executemany("INSERT INTO memory_index_aliases VALUES(?,?)", ((key, alias) for alias in aliases))
            connection.execute("DELETE FROM memory_index_sources WHERE memory_id=?", (key,))
            connection.executemany("INSERT INTO memory_index_sources VALUES(?,?)", ((key, source) for source in entry.source_ids))
        if entry.deleted:
            if previous is not None:
                connection.execute("DELETE FROM memory_index_fts WHERE rowid=?", (previous[8],))
        elif previous is None or previous[7] != tokens or previous[2]:
            rowid = previous[8] if previous is not None else connection.execute(
                "SELECT rowid FROM memory_index_entries WHERE memory_id=?", (key,)).fetchone()[0]
            if previous is not None:
                connection.execute("DELETE FROM memory_index_fts WHERE rowid=?", (rowid,))
            connection.execute("INSERT INTO memory_index_fts(rowid,memory_id,tokens) VALUES(?,?,?)", (rowid, key, tokens))
    if ordinal_updates:
        connection.executemany("UPDATE memory_index_entries SET ordinal=?,expired=? WHERE memory_id=?", ordinal_updates)
    chapters = {}
    for raw in document.get("chapters", ()):
        chapter = MemoryChapter.from_dict(raw)
        if chapter is not None and chapter.character_id == character:
            chapters[chapter.chapter_id] = chapter
    old_chapters = dict(connection.execute("SELECT chapter_id,payload FROM memory_index_chapters"))
    for key in old_chapters.keys() - chapters.keys():
        connection.execute("DELETE FROM memory_index_chapters WHERE chapter_id=?", (key,))
        connection.execute("DELETE FROM memory_index_chapter_sources WHERE chapter_id=?", (key,))
    for key, chapter in chapters.items():
        payload = _json(chapter.to_dict())
        if old_chapters.get(key) == payload:
            continue
        connection.execute("INSERT OR REPLACE INTO memory_index_chapters VALUES(?,?,?,?)", (
            key, payload, chapter.created_at, " ".join(lexical_tokens(" ".join((chapter.title, chapter.summary, *chapter.tags))))))
        connection.execute("DELETE FROM memory_index_chapter_sources WHERE chapter_id=?", (key,))
        connection.executemany("INSERT INTO memory_index_chapter_sources VALUES(?,?)", ((key, source) for source in chapter.source_memory_ids))
    profile = _json(document.get("profile", {}))
    document_epoch = int(document.get("context_epoch", 0))
    # Legacy document/SQL writers can edit a previously exposed source without
    # running _invalidate_derived/_retire. A changed fingerprint alone fences
    # retrieval, but an already-running model and unlineaged dialogue history
    # still carry the old epoch. Repair that authority-wide barrier in this
    # same transaction. New sources and access-only changes do not revoke it;
    # lifecycle methods that already advanced the epoch are not counted twice.
    epoch = max(document_epoch, int(meta[3]))
    if document_epoch <= meta[3] and any(change[1] in old for change in semantic_changes):
        epoch = int(meta[3]) + 1
    if epoch != document_epoch:
        document["context_epoch"] = epoch
        connection.execute("UPDATE memory_state SET payload=json_set(payload,'$.context_epoch',?) WHERE id=1", (epoch,))
    if not semantic_changes and profile == meta[2] and epoch == meta[3]:
        revision = int(meta[0])
    if semantic_changes:
        connection.executemany("INSERT INTO memory_index_changes VALUES(?,?,?,?,?)", semantic_changes)
    next_expiry = connection.execute("SELECT COALESCE(MIN(valid_until),0) FROM memory_index_entries WHERE deleted=0 AND expired=0 AND valid_until>0").fetchone()[0]
    connection.execute("""UPDATE memory_index_meta SET revision=?,dirty=0,character_id=?,owner_id=?,
        context_epoch=?,profile=?,next_expiry=?,entry_count=? WHERE id=1""",
        (revision, character, owner, epoch, profile, next_expiry, len(current)))


def _initialize_or_repair(store, *, now: int | None = None) -> None:
    with store._document() as document:
        store._check_document(document)
        if now is not None:
            store._expire_document(document, store._entries(document), now=now)


@contextmanager
def _ready(store, *, now: int | None = None):
    """Lock a current projection. Full-document work is only migration/expiry."""
    connection = None
    try:
        for _ in range(4):
            if not store.state_path.exists():
                _initialize_or_repair(store, now=now)
            connection = sqlite3.connect(store.state_path, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version != 2:
                raise MemoryStorageError("Unsupported authoritative memory version; refusing legacy fallback")
            if not connection.execute("SELECT 1 FROM memory_state WHERE id=1").fetchone():
                raise MemoryStorageError("Authoritative memory state is missing; refusing legacy fallback")
            ready = schema_ready(connection)
            meta = connection.execute("SELECT * FROM memory_index_meta WHERE id=1").fetchone() if ready else None
            needs_expiry = meta is not None and now is not None and 0 < meta["next_expiry"] <= now
            if not ready or meta["dirty"] or needs_expiry:
                connection.rollback()
                connection.close()
                connection = None
                _initialize_or_repair(store, now=now)
                continue
            if meta["owner_id"] != store.owner_id or meta["character_id"] != store.character_id:
                raise MemoryStorageError("Memory projection belongs to a different character or owner")
            _write_initialization_receipt(store.state_path.with_suffix(".initialized"))
            yield connection, meta
            connection.commit()
            return
        raise MemoryStorageError("Memory projection could not reach a current revision")
    except (OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        if connection is not None:
            connection.rollback()
        raise MemoryStorageError("Cannot read authoritative indexed memory; refusing legacy fallback") from exc
    except BaseException:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if connection is not None:
            connection.close()


def _in_clause(column: str, values, params: list) -> str:
    values = tuple(dict.fromkeys(values))
    if not values:
        return "0"
    params.extend(values)
    return column + " IN (" + ",".join("?" for _ in values) + ")"


def _where(store, request, now, *, fts_enabled):
    params = [store.character_id, store.owner_id]
    terms = ["e.character_id=?", "e.owner_id=?", "e.deleted=0", "e.confidence>0"]
    terms.append(_in_clause("e.scope", request.scopes, params))
    terms.append("e.valid_from<=?")
    params.append(now)
    if not request.history:
        terms.append("(e.valid_until=0 OR e.valid_until>?)")
        params.append(now)
    if request.memory_ids is not None:
        terms.append(_in_clause("e.memory_id", request.memory_ids, params))
    if request.subjects:
        # Resolve aliases first, then use subject/entity indexes to enumerate
        # IDs. A correlated alias EXISTS over all eligible rows would make
        # exact fact queries linear even though an index exists on paper.
        selects = []
        for identity in ("subject", "entity_id"):
            for field in (("predicate", "fact_slot", "fact_domain") if request.predicates else (None,)):
                clause = _in_clause(identity, request.subjects, params)
                if field:
                    clause += " AND " + _in_clause(field, request.predicates, params)
                selects.append("SELECT memory_id FROM memory_index_entries WHERE " + clause)
        terms.append("e.memory_id IN (" + " UNION ".join(selects) + ")")
    elif request.predicates:
        selects = ["SELECT memory_id FROM memory_index_entries WHERE " + _in_clause(column, request.predicates, params)
                   for column in ("predicate", "fact_slot", "fact_domain")]
        terms.append("e.memory_id IN (" + " UNION ".join(selects) + ")")
    if request.kinds:
        terms.append(_in_clause("e.kind", request.kinds, params))
    if request.occurred_after:
        terms.append("e.occurred_at>=?")
        params.append(request.occurred_after)
    if request.occurred_before:
        terms.append("e.occurred_at<?")
        params.append(request.occurred_before)
    tokens = lexical_tokens(request.query, for_query=True)
    join = ""
    order = "e.occurred_at DESC,e.memory_id"
    if request.query.strip():
        if not tokens:
            terms.append("0")
        elif fts_enabled:
            join = " JOIN memory_index_fts ON memory_index_fts.rowid=e.rowid"
            terms.append("memory_index_fts MATCH ?")
            params.append(" OR ".join('"' + token + '"' for token in tokens))
            order = "bm25(memory_index_fts)," + order
        else:
            terms.append("(" + " OR ".join("instr(' '||e.lexical_tokens||' ',?)>0" for _ in tokens) + ")")
            params.extend(" " + token + " " for token in tokens)
    return " AND ".join(terms), params, join, order


def _resolve_bindings(connection, store, subjects, *, now, scopes):
    result = {}
    fingerprints = {}
    sources_by_input = {}
    for subject in dict.fromkeys(subjects):
        if subject == "user:self" or subject.startswith(("relation:", "entity:")):
            # Canonical identifiers are constraints, not inferred name links.
            # Reading every fact of user:self to prove its identity defeats
            # bounded structured reads and provides no additional evidence.
            result[subject] = (subject,)
            sources_by_input[subject] = ()
            continue
        args = [subject, subject, subject, subject, store.character_id, store.owner_id, now, now]
        scope_filter = _in_clause("e.scope", scopes, args)
        rows = connection.execute("SELECT e.memory_id,e.fingerprint,e.subject,e.entity_id FROM memory_index_entries e" + _PRIMARY_LOOKUP + """
            WHERE e.memory_id IN (
                SELECT memory_id FROM memory_index_entries WHERE subject=? UNION
                SELECT memory_id FROM memory_index_entries WHERE entity_id=? UNION
                SELECT memory_id FROM memory_index_entries WHERE predicate IN ('name','姓名','称呼') AND fact_value=? UNION
                SELECT memory_id FROM memory_index_aliases WHERE alias=?)
            AND e.character_id=? AND e.owner_id=? AND e.deleted=0 AND e.confidence>0
            AND e.valid_from<=? AND (e.valid_until=0 OR e.valid_until>?) AND """ + scope_filter +
            " ORDER BY e.subject,e.entity_id,e.memory_id", args).fetchall()
        result[subject] = tuple(dict.fromkeys(row["subject"] or row["entity_id"] for row in rows
            if row["subject"] or row["entity_id"]))
        canonical_input = subject == "user:self" or subject.startswith(("relation:", "entity:"))
        evidence = [row for row in rows if not (canonical_input and subject in (row["subject"], row["entity_id"]))]
        sources_by_input[subject] = tuple(row["memory_id"] for row in evidence)
        fingerprints.update((row["memory_id"], row["fingerprint"]) for row in evidence)
    return result, fingerprints, sources_by_input


def _resolve_subjects(connection, store, subjects, *, now, scopes):
    return _resolve_bindings(connection, store, subjects, now=now, scopes=scopes)[0]


def resolve_subjects(store, subjects, *, now, scopes=("companion",)):
    with _ready(store, now=now) as (connection, _):
        return _resolve_subjects(connection, store, subjects, now=now, scopes=scopes)


def resolve_subject_bindings(store, subjects, *, now, scopes=("companion",)):
    with _ready(store, now=now) as (connection, meta):
        mapping, fingerprints, by_input = _resolve_bindings(connection, store, subjects, now=now, scopes=scopes)
        return SubjectResolution(mapping, tuple(fingerprints), fingerprints, int(meta["context_epoch"]),
            int(meta["revision"]), meta["generation"], by_input)


def _decode(row):
    from .emotional_memory import EmotionalMemoryEntry
    entry = EmotionalMemoryEntry.from_dict(_strict_json_loads(row["payload"]))
    if (entry is None or entry.memory_id != row["memory_id"]
            or entry.evidence_fingerprint() != row["fingerprint"]
            or entry.character_id != row["character_id"] or entry.owner_id != row["owner_id"]
            or entry.scope != row["scope"] or int(entry.deleted) != row["deleted"]
            or entry.valid_from != row["valid_from"] or entry.valid_until != row["valid_until"]):
        raise MemoryStorageError("Invalid derived memory row; rebuild projection from authoritative SQLite")
    return entry


def _eligibility(row, *, now, scopes):
    if row is None:
        return False, "missing"
    if row["deleted"]:
        return False, "revoked"
    if row["scope"] not in scopes:
        return False, "scope"
    if row["confidence"] <= 0:
        return False, "confidence"
    if row["valid_from"] > now:
        return False, "future"
    if row["valid_until"] and now >= row["valid_until"]:
        return False, "expired"
    return True, "valid"


def read_snapshot(store, request=None, *, now, include_chapters=True, chapter_limit=8,
                  include_profile_sources=True):
    from dataclasses import replace
    from .emotional_memory import CoreBondProfile, MemoryChapter
    request = request or IndexedMemoryQuery()
    if not isinstance(request, IndexedMemoryQuery):
        raise TypeError("indexed query must be IndexedMemoryQuery")
    limit = max(0, min(int(request.limit), 512))
    chapter_limit = max(0, min(int(chapter_limit), 32))
    start = time.perf_counter()
    with _ready(store, now=now) as (connection, meta):
        ready_time = time.perf_counter()
        if request.subjects:
            bindings = _resolve_subjects(connection, store, request.subjects, now=now, scopes=request.scopes)
            expanded = tuple(dict.fromkeys(value for subject in request.subjects
                for value in (bindings[subject] or (subject,))))
            request = replace(request, subjects=expanded)
        where, params, join, order = _where(store, request, now, fts_enabled=meta["fts_enabled"])
        bounded_ids = request.memory_ids is not None or request.subjects or request.predicates
        table = "memory_index_entries e" + (_PRIMARY_LOOKUP if bounded_ids else "") + join
        if join and not bounded_ids:
            # SQLite otherwise chooses eligibility as the outer loop and runs
            # the same MATCH once per record. CROSS JOIN fixes only this join
            # order: enumerate postings once, then authorize each row by PK.
            table = "memory_index_fts CROSS JOIN memory_index_entries e ON memory_index_fts.rowid=e.rowid"
        total = connection.execute("SELECT COUNT(*) FROM " + table + " WHERE " + where, params).fetchone()[0]
        filtered_time = time.perf_counter()
        rows = connection.execute("SELECT e.* FROM " + table + " WHERE " + where + " ORDER BY " + order + " LIMIT ?", (*params, limit)).fetchall()
        loaded = {row["memory_id"]: _decode(row) for row in rows}
        entries = tuple(loaded[row["memory_id"]] for row in rows)
        candidate_time = time.perf_counter()
        profile = CoreBondProfile.from_dict(_strict_json_loads(meta["profile"]), fallback_character_id=store.character_id)
        if profile.character_id != store.character_id or profile.owner_id != store.owner_id:
            profile = CoreBondProfile(store.character_id, store.owner_id)
        chapters = []
        if include_chapters and chapter_limit:
            # Chapters linked to the retrieved evidence have first priority;
            # the remaining small budget admits recent overviews for expansion.
            if loaded:
                args = list(loaded)
                predicate = _in_clause("s.memory_id", args, [])
                chapter_rows = connection.execute("SELECT c.payload FROM memory_index_chapters c ORDER BY EXISTS(SELECT 1 FROM memory_index_chapter_sources s WHERE s.chapter_id=c.chapter_id AND " + predicate + ") DESC,c.created_at DESC,c.chapter_id LIMIT ?", (*args, chapter_limit)).fetchall()
            else:
                chapter_rows = connection.execute("SELECT payload FROM memory_index_chapters ORDER BY created_at DESC,chapter_id LIMIT ?", (chapter_limit,)).fetchall()
            chapters = [chapter for raw in chapter_rows if (chapter := MemoryChapter.from_dict(_strict_json_loads(raw[0]))) is not None]
        referenced = (dict.fromkeys(key for refs in profile.evidence.values() for key in refs)
                      if include_profile_sources else {})
        for chapter in chapters:
            referenced.update(dict.fromkeys(chapter.source_memory_ids))
        # Source validation is intentionally independent of query relevance:
        # every included derived claim must authenticate its dependencies.
        source_rows = {row["memory_id"]: row for row in rows}
        source_ids = tuple(referenced)[:512]
        missing = [key for key in source_ids if key not in source_rows]
        if missing:
            args = [store.character_id, store.owner_id]
            clause = _in_clause("memory_id", missing, args)
            source_rows.update((row["memory_id"], row) for row in connection.execute("SELECT * FROM memory_index_entries" + _PRIMARY_LOOKUP + " WHERE character_id=? AND owner_id=? AND " + clause, args))
        eligibility = {}
        sources = []
        for key in dict.fromkeys((*loaded, *referenced)):
            row = source_rows.get(key)
            allowed, reason = _eligibility(row, now=now, scopes=request.scopes)
            if key in referenced and key not in source_ids:
                allowed, reason = False, "source_budget"
            eligibility[key] = IndexedSourceEligibility(key, allowed, reason,
                row["fingerprint"] if row else "", row["scope"] if row else "",
                row["valid_from"] if row else 0, row["valid_until"] if row else 0)
            if key in referenced and allowed:
                if key not in loaded:
                    loaded[key] = _decode(row)
                sources.append(loaded[key])
        end = time.perf_counter()
        return IndexedMemorySnapshot(entries, profile, tuple(chapters), int(meta["context_epoch"]),
            int(meta["revision"]), meta["generation"], tuple(row.memory_id for row in entries),
            len(loaded), int(total), tuple(sources), eligibility,
            {"database_prepare_ms": (ready_time - start) * 1000,
             "qualification_ms": (filtered_time - ready_time) * 1000,
             "candidate_read_ms": (candidate_time - filtered_time) * 1000,
             "derived_read_ms": (end - candidate_time) * 1000,
             "indexed_read_ms": (end - start) * 1000},
            "fts5" if meta["fts_enabled"] else "token_scan")


def finalize(store, selected: Iterable[EmotionalMemoryEntry], *, expected_epoch, now,
             scope="companion", scopes=None, allow_history=False, dependency_entries=()):
    expected = {}
    for entry in selected:
        previous = expected.get(entry.memory_id)
        if previous is not None and previous.evidence_fingerprint() != entry.evidence_fingerprint():
            return None
        if entry.owner_id != store.owner_id or entry.character_id != store.character_id:
            return None
        expected[entry.memory_id] = entry
    dependencies = {}
    required = dict(expected)
    for entry in dependency_entries:
        if entry.owner_id != store.owner_id or entry.character_id != store.character_id:
            return None
        previous = required.get(entry.memory_id)
        if previous is not None and previous.evidence_fingerprint() != entry.evidence_fingerprint():
            return None
        dependencies[entry.memory_id] = entry
        required[entry.memory_id] = entry
    allowed_scopes = tuple(scopes) if scopes is not None else (scope,)
    with _ready(store, now=now) as (connection, meta):
        if meta["context_epoch"] != expected_epoch:
            return None
        if not required:
            return ()
        args = [store.character_id, store.owner_id]
        clause = _in_clause("memory_id", required, args)
        rows = {row["memory_id"]: row for row in connection.execute("SELECT * FROM memory_index_entries" + _PRIMARY_LOOKUP + " WHERE character_id=? AND owner_id=? AND " + clause, args)}
        for key, dependency in dependencies.items():
            row = rows.get(key)
            if (not _eligibility(row, now=now, scopes=allowed_scopes)[0]
                    or row["fingerprint"] != dependency.evidence_fingerprint()):
                return None
            _decode(row)
        if not expected:
            return ()
        touched = []
        for key, source in expected.items():
            row = rows.get(key)
            eligible, reason = _eligibility(row, now=now, scopes=allowed_scopes)
            if not (eligible or (allow_history and reason == "expired")) or row["fingerprint"] != source.evidence_fingerprint():
                return None
            touched.append(_decode(row).touch(now))
        # One JSON1 update maintains the sole canonical document. SQLite still
        # serializes its JSON text, but Python never parses unrelated records.
        # Chunk at 32 to support builds with a conservative SQL-argument limit.
        for offset in range(0, len(touched), 32):
            batch = touched[offset:offset + 32]
            expression = "json_set(payload," + ",".join("?,json(?)" for _ in batch) + ")"
            parameters = []
            for entry in batch:
                parameters.extend((f"$.entries[{rows[entry.memory_id]['ordinal']}]", _json(entry.to_dict())))
            connection.execute("UPDATE memory_state SET payload=" + expression + " WHERE id=1", parameters)
        for entry in touched:
            value = entry.to_dict()
            connection.execute("UPDATE memory_index_entries SET payload=?,raw_digest=? WHERE memory_id=?",
                               (_json(value), _raw_digest(value), entry.memory_id))
        connection.execute("UPDATE memory_index_meta SET dirty=0 WHERE id=1")
        return tuple(touched)


def read_epoch(store, *, now=None):
    with _ready(store, now=now) as (_, meta):
        return int(meta["context_epoch"])


def read_index_state(store, *, now=None):
    with _ready(store, now=now) as (_, meta):
        return meta["generation"], int(meta["revision"]), int(meta["context_epoch"])


def manifest(store, *, now, scopes=("companion",), after_revision=None, limit=2048, after_id=""):
    limit = max(1, min(int(limit), 10000))
    with _ready(store, now=now) as (connection, meta):
        revision = int(meta["revision"])
        full = after_revision is None or int(after_revision) > revision
        if after_revision is not None and int(after_revision) == revision:
            return MemoryIndexManifest(meta["generation"], revision, int(meta["context_epoch"]),
                (), (), False, "", False)
        params = [store.character_id, store.owner_id, after_id]
        where = "e.character_id=? AND e.owner_id=? AND e.memory_id>?"
        columns = "e.memory_id,e.fingerprint,e.scope,e.version,e.valid_from,e.valid_until,e.deleted,e.confidence"
        # Incremental records include transitions OUT of the requested scope,
        # otherwise a semantic cache could retain a now-private/work fact.
        if full:
            where += " AND " + _in_clause("e.scope", scopes, params)
            rows = connection.execute("SELECT " + columns + " FROM memory_index_entries e WHERE " + where + " ORDER BY e.memory_id LIMIT ?", (*params, limit + 1)).fetchall()
        else:
            rows = connection.execute("SELECT " + columns + " FROM (SELECT DISTINCT memory_id FROM memory_index_changes WHERE revision>? AND memory_id>?) c JOIN memory_index_entries e ON e.memory_id=c.memory_id WHERE " + where + " ORDER BY e.memory_id LIMIT ?", (int(after_revision), after_id, *params, limit + 1)).fetchall()
        records = []
        for row in rows[:limit]:
            allowed, reason = _eligibility(row, now=now, scopes=scopes)
            removed = reason in {"revoked", "scope", "confidence", "expired"}
            records.append(MemoryIndexRecord(row["memory_id"], row["fingerprint"], row["scope"],
                row["version"], row["valid_from"], row["valid_until"], removed, allowed))
        removed_ids = [record.memory_id for record in records if record.removed]
        if not full:
            # Physical removal is rare (legacy tools), but has no current row.
            # Supply explicit tombstones and paginate them in the same ID order.
            args = [int(after_revision), after_id]
            scope_clause = _in_clause("c.scope", scopes, args)
            deleted = connection.execute("SELECT DISTINCT c.memory_id FROM memory_index_changes c WHERE c.revision>? AND c.memory_id>? AND " + scope_clause + " AND c.removed=1 AND NOT EXISTS(SELECT 1 FROM memory_index_entries e WHERE e.memory_id=c.memory_id) ORDER BY c.memory_id LIMIT ?", (*args, limit + 1)).fetchall()
            candidates = [(record.memory_id, record) for record in records] + [(row[0], None) for row in deleted]
            candidates.sort(key=lambda item: item[0])
            has_more = len(rows) > limit or len(candidates) > limit
            selected = candidates[:limit]
            records = [record for _, record in selected if record is not None]
            removed_ids = [key for key, record in selected if record is None or record.removed]
            next_id = selected[-1][0] if selected else ""
        else:
            has_more = len(rows) > limit
            next_id = records[-1].memory_id if records else ""
        return MemoryIndexManifest(meta["generation"], revision, int(meta["context_epoch"]),
            tuple(records), tuple(removed_ids), has_more, next_id, full)
