"""Rebuildable SQLite projections; memory_state.payload remains authoritative.

Projection maintenance runs in the same transaction as the JSON document.  The
dirty triggers also catch tools which edit the canonical row directly.  Index
schema changes never change the v2 save-file contract or replay legacy files.
"""
from __future__ import annotations

import sqlite3
import uuid

INDEX_VERSION = 1
# Changes to conservative typed-read rules, lexical terms or FTS row mapping
# require a rebuild even when the SQL table layout is unchanged.
ALGORITHM_VERSION = "typed-literal-v3:structured-value-v1:cn-grams-v1:fts-rowid-v1:structured-pk-v1:raw-diff-v1"
TABLES = (
    "memory_index_meta", "memory_index_entries", "memory_index_aliases",
    "memory_index_sources", "memory_index_chapters", "memory_index_chapter_sources",
    "memory_index_changes", "memory_index_fts",
)
TRIGGERS = ("memory_index_dirty_update", "memory_index_dirty_insert", "memory_index_dirty_delete")


def schema_ready(connection: sqlite3.Connection) -> bool:
    names = TABLES + TRIGGERS
    found = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE name IN (" + ",".join("?" for _ in names) + ")", names)}
    if not set(names).issubset(found):
        return False
    try:
        row = connection.execute("SELECT version,algorithm_version FROM memory_index_meta WHERE id=1").fetchone()
    except sqlite3.OperationalError as exc:
        if "no such column" in str(exc).lower():
            return False
        raise
    return row is not None and row[0] == INDEX_VERSION and row[1] == ALGORITHM_VERSION


def ensure_schema(connection: sqlite3.Connection) -> bool:
    """Return True when the index must be rebuilt, preserving the JSON row."""
    if schema_ready(connection):
        return False
    # Only rebuild the named derived tables. Authority, retirement fences and
    # the initialization receipt are deliberately outside this list.
    for name in TRIGGERS:
        connection.execute("DROP TRIGGER IF EXISTS " + name)
    for name in reversed(TABLES):
        connection.execute("DROP TABLE IF EXISTS " + name)
    connection.execute("""CREATE TABLE memory_index_meta (
        id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL,
        generation TEXT NOT NULL, revision INTEGER NOT NULL, dirty INTEGER NOT NULL,
        character_id TEXT NOT NULL, owner_id TEXT NOT NULL, context_epoch INTEGER NOT NULL,
        profile TEXT NOT NULL, next_expiry INTEGER NOT NULL, entry_count INTEGER NOT NULL,
        fts_enabled INTEGER NOT NULL,algorithm_version TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE memory_index_entries (
        memory_id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL, character_id TEXT NOT NULL,
        owner_id TEXT NOT NULL, scope TEXT NOT NULL, kind TEXT NOT NULL,
        subject TEXT NOT NULL, entity_id TEXT NOT NULL, predicate TEXT NOT NULL,
        fact_slot TEXT NOT NULL, fact_domain TEXT NOT NULL, fact_value TEXT NOT NULL,
        valid_from INTEGER NOT NULL, valid_until INTEGER NOT NULL, occurred_at INTEGER NOT NULL,
        recorded_at INTEGER NOT NULL, version INTEGER NOT NULL, confidence REAL NOT NULL,
        deleted INTEGER NOT NULL, expired INTEGER NOT NULL, supersedes TEXT NOT NULL,
        fingerprint TEXT NOT NULL, payload TEXT NOT NULL, lexical_tokens TEXT NOT NULL,
        raw_digest TEXT NOT NULL)""")
    connection.execute("CREATE INDEX memory_index_eligibility ON memory_index_entries(character_id,owner_id,scope,deleted,valid_from,valid_until)")
    connection.execute("CREATE INDEX memory_index_facts ON memory_index_entries(character_id,owner_id,subject,predicate,deleted,valid_until)")
    connection.execute("CREATE INDEX memory_index_subject_lookup ON memory_index_entries(subject,memory_id)")
    connection.execute("CREATE INDEX memory_index_subject_predicate ON memory_index_entries(subject,predicate,memory_id)")
    connection.execute("CREATE INDEX memory_index_subject_slot ON memory_index_entries(subject,fact_slot,memory_id)")
    connection.execute("CREATE INDEX memory_index_subject_domain ON memory_index_entries(subject,fact_domain,memory_id)")
    connection.execute("CREATE INDEX memory_index_entities ON memory_index_entries(entity_id,predicate,memory_id)")
    connection.execute("CREATE INDEX memory_index_entity_slot ON memory_index_entries(entity_id,fact_slot,memory_id)")
    connection.execute("CREATE INDEX memory_index_entity_domain ON memory_index_entries(entity_id,fact_domain,memory_id)")
    connection.execute("CREATE INDEX memory_index_predicate_lookup ON memory_index_entries(predicate,memory_id)")
    connection.execute("CREATE INDEX memory_index_slots ON memory_index_entries(fact_slot,deleted)")
    connection.execute("CREATE INDEX memory_index_domains ON memory_index_entries(fact_domain,deleted)")
    connection.execute("CREATE INDEX memory_index_names ON memory_index_entries(predicate,fact_value)")
    connection.execute("CREATE INDEX memory_index_time ON memory_index_entries(occurred_at DESC)")
    connection.execute("CREATE INDEX memory_index_expiry ON memory_index_entries(expired,deleted,valid_until)")
    connection.execute("CREATE TABLE memory_index_aliases(memory_id TEXT NOT NULL,alias TEXT NOT NULL,PRIMARY KEY(memory_id,alias))")
    connection.execute("CREATE INDEX memory_index_alias_lookup ON memory_index_aliases(alias,memory_id)")
    connection.execute("CREATE TABLE memory_index_sources(memory_id TEXT NOT NULL,source_id TEXT NOT NULL,PRIMARY KEY(memory_id,source_id))")
    connection.execute("CREATE INDEX memory_index_source_lookup ON memory_index_sources(source_id,memory_id)")
    connection.execute("CREATE TABLE memory_index_chapters(chapter_id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at INTEGER NOT NULL,lexical_tokens TEXT NOT NULL)")
    connection.execute("CREATE TABLE memory_index_chapter_sources(chapter_id TEXT NOT NULL,memory_id TEXT NOT NULL,PRIMARY KEY(chapter_id,memory_id))")
    connection.execute("CREATE INDEX memory_index_chapter_lookup ON memory_index_chapter_sources(memory_id,chapter_id)")
    connection.execute("""CREATE TABLE memory_index_changes(
        revision INTEGER NOT NULL,memory_id TEXT NOT NULL,fingerprint TEXT NOT NULL,
        scope TEXT NOT NULL,removed INTEGER NOT NULL,PRIMARY KEY(revision,memory_id))""")
    connection.execute("CREATE INDEX memory_index_change_lookup ON memory_index_changes(memory_id,revision)")
    fts_enabled = 1
    try:
        connection.execute("CREATE VIRTUAL TABLE memory_index_fts USING fts5(memory_id UNINDEXED,tokens,tokenize='unicode61')")
    except sqlite3.OperationalError as exc:
        if "no such module" not in str(exc).lower():
            raise
        # A portable fallback is explicit in snapshot diagnostics. It uses the
        # same pretokenized terms but cannot claim BM25 ranking or FTS speed.
        fts_enabled = 0
        connection.execute("CREATE TABLE memory_index_fts(memory_id TEXT PRIMARY KEY,tokens TEXT NOT NULL)")
    connection.execute("INSERT INTO memory_index_meta VALUES(1,?,?,?,?,?,?,?,?,?,?,?,?)",
        (INDEX_VERSION, uuid.uuid4().hex, 0, 1, "", "", 0, "{}", 0, 0, fts_enabled, ALGORITHM_VERSION))
    for event, trigger in zip(("UPDATE", "INSERT", "DELETE"), TRIGGERS):
        connection.execute(f"CREATE TRIGGER {trigger} AFTER {event} ON memory_state BEGIN UPDATE memory_index_meta SET dirty=1 WHERE id=1; END")
    return True
