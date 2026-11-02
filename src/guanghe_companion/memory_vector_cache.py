"""Rebuildable embeddings in the authoritative memory database.

Only current, authenticated source headers authorize a vector.  This projection
contains no memory text, never changes memory_state, and can be cleared without
changing the v2 save format.  Source UPDATE/DELETE triggers revoke all affected
model versions in the same transaction as ordinary memory changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import sqlite3
from typing import Mapping

from .memory_index import _ready


CACHE_SCHEMA_VERSION = 1
MAX_BATCH_SIZE = 512
_TABLES = ("memory_vector_cache", "memory_vector_cache_meta")
_TRIGGERS = ("memory_vector_cache_invalidate_update", "memory_vector_cache_invalidate_delete")
_COLUMNS = {
    "memory_id", "owner_id", "character_id", "scope", "fingerprint", "model_name",
    "model_revision", "dimensions", "encoding_version", "namespace", "index_generation",
    "vector", "checksum",
}


@dataclass(frozen=True, slots=True)
class VectorCacheSpec:
    model_name: str
    model_revision: str
    dimensions: int
    encoding_version: str

    def __post_init__(self):
        if not all(isinstance(value, str) and value for value in
                   (self.model_name, self.model_revision, self.encoding_version)):
            raise ValueError("vector cache requires explicit pinned model and encoding versions")
        if not isinstance(self.dimensions, int) or not 1 <= self.dimensions <= 8192:
            raise ValueError("vector dimensions must be between 1 and 8192")

    @property
    def namespace(self) -> str:
        payload = (self.model_name, self.model_revision, self.dimensions, self.encoding_version)
        return hashlib.sha256(json.dumps(payload, ensure_ascii=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class VectorCacheResult:
    vectors: dict = field(default_factory=dict)
    written: int = 0
    discarded: int = 0
    available: bool = True
    error: str | None = None


class VectorCacheStale(RuntimeError):
    """The caller's manifest no longer describes the current source snapshot."""


class MemoryVectorCache:
    """Bounded, transactional projection, never an independent evidence store.

    ``sources`` maps memory_id to (source_fingerprint, scope). ``state`` is the
    exact (index_generation, index_revision, context_epoch) from the manifest.
    Callers must still fence final query publication after reading/encoding.
    """

    def __init__(self, spec: VectorCacheSpec):
        self.spec = spec

    @staticmethod
    def _ensure_schema(connection, meta):
        names = _TABLES + _TRIGGERS
        existing = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE name IN (?,?,?,?)", names)}
        ready = set(_TABLES).issubset(existing)
        if ready:
            ready = ({row[1] for row in connection.execute("PRAGMA table_info(memory_vector_cache)")} == _COLUMNS
                     and {row[1] for row in connection.execute("PRAGMA table_info(memory_vector_cache_meta)")}
                     == {"id", "schema_version", "index_generation"})
        cache_meta = connection.execute("SELECT * FROM memory_vector_cache_meta WHERE id=1").fetchone() if ready else None
        ready = ready and cache_meta is not None and cache_meta["schema_version"] == CACHE_SCHEMA_VERSION
        if not ready:
            # Drop references before repairing only our own derived tables.
            for trigger in _TRIGGERS:
                connection.execute("DROP TRIGGER IF EXISTS " + trigger)
            for table in _TABLES:
                connection.execute("DROP TABLE IF EXISTS " + table)
            connection.execute("""CREATE TABLE memory_vector_cache(
                memory_id TEXT NOT NULL,owner_id TEXT NOT NULL,character_id TEXT NOT NULL,
                scope TEXT NOT NULL,fingerprint TEXT NOT NULL,model_name TEXT NOT NULL,
                model_revision TEXT NOT NULL,dimensions INTEGER NOT NULL,
                encoding_version TEXT NOT NULL,namespace TEXT NOT NULL,index_generation TEXT NOT NULL,
                vector BLOB NOT NULL,checksum TEXT NOT NULL,
                PRIMARY KEY(memory_id,owner_id,character_id,scope,namespace,fingerprint)) WITHOUT ROWID""")
            connection.execute("""CREATE TABLE memory_vector_cache_meta(
                id INTEGER PRIMARY KEY CHECK(id=1),schema_version INTEGER NOT NULL,index_generation TEXT NOT NULL)""")
            connection.execute("INSERT INTO memory_vector_cache_meta VALUES(1,?,?)",
                               (CACHE_SCHEMA_VERSION, meta["generation"]))
        elif cache_meta["index_generation"] != meta["generation"]:
            connection.execute("DELETE FROM memory_vector_cache")
            connection.execute("UPDATE memory_vector_cache_meta SET index_generation=? WHERE id=1", (meta["generation"],))
        # A source projection rebuild drops attached triggers automatically;
        # reinstall even if our two cache tables survived the rebuild.
        connection.execute("""CREATE TRIGGER IF NOT EXISTS memory_vector_cache_invalidate_update
            AFTER UPDATE ON memory_index_entries
            WHEN OLD.fingerprint IS NOT NEW.fingerprint OR OLD.deleted IS NOT NEW.deleted
                OR OLD.expired IS NOT NEW.expired OR OLD.memory_id IS NOT NEW.memory_id
                OR OLD.scope IS NOT NEW.scope OR OLD.owner_id IS NOT NEW.owner_id
                OR OLD.character_id IS NOT NEW.character_id OR OLD.confidence IS NOT NEW.confidence
                OR OLD.valid_from IS NOT NEW.valid_from OR OLD.valid_until IS NOT NEW.valid_until
            BEGIN DELETE FROM memory_vector_cache WHERE memory_id IN (OLD.memory_id,NEW.memory_id); END""")
        connection.execute("""CREATE TRIGGER IF NOT EXISTS memory_vector_cache_invalidate_delete
            AFTER DELETE ON memory_index_entries
            BEGIN DELETE FROM memory_vector_cache WHERE memory_id=OLD.memory_id; END""")

    @staticmethod
    def _validate_sources(sources):
        if len(sources) > MAX_BATCH_SIZE:
            raise ValueError("vector cache operation exceeds its bounded batch")
        if any(not isinstance(key, str) or not key or not isinstance(value, tuple) or len(value) != 2
               or not all(isinstance(part, str) and part for part in value) for key, value in sources.items()):
            raise ValueError("vector cache requires explicit source IDs, fingerprints and scopes")

    @staticmethod
    def _current_sources(connection, store, sources, now):
        if not sources:
            return set()
        # Only headers by primary key: no payload decode or unrelated scan.
        sql = """SELECT memory_id,owner_id,character_id,scope,fingerprint,deleted,expired,
            confidence,valid_from,valid_until FROM memory_index_entries WHERE memory_id IN ("""
        rows = connection.execute(sql + ",".join("?" for _ in sources) + ")", tuple(sources))
        return {row["memory_id"] for row in rows
            if row["owner_id"] == store.owner_id and row["character_id"] == store.character_id
            and (row["fingerprint"], row["scope"]) == sources[row["memory_id"]]
            and not row["deleted"] and not row["expired"] and row["confidence"] > 0
            and row["valid_from"] <= now and (not row["valid_until"] or now < row["valid_until"])}

    def _execute(self, store, *, sources, now, state, operation):
        self._validate_sources(sources)
        # Authority/dirty/TTL failures propagate. A vector cannot substitute for
        # an unavailable or revoked authoritative record.
        with _ready(store, now=now) as (connection, meta):
            actual = (meta["generation"], int(meta["revision"]), int(meta["context_epoch"]))
            if actual != state:
                raise VectorCacheStale("memory changed before vector cache transaction")
            connection.execute("SAVEPOINT vector_cache")
            try:
                self._ensure_schema(connection, meta)
                current = self._current_sources(connection, store, sources, now)
                result = operation(connection, meta, current)
                connection.execute("RELEASE vector_cache")
                return result
            except (sqlite3.Error, ValueError, TypeError, OverflowError) as exc:
                # Cache-only failure is a miss. Don't suppress failures raised
                # by _ready or a failed outer authoritative commit.
                connection.execute("ROLLBACK TO vector_cache")
                connection.execute("RELEASE vector_cache")
                return VectorCacheResult(available=False, error=type(exc).__name__)

    def _decode(self, row, meta):
        import numpy as np
        if (row["index_generation"] != meta["generation"]
                or row["dimensions"] != self.spec.dimensions
                or row["model_name"] != self.spec.model_name
                or row["model_revision"] != self.spec.model_revision
                or row["encoding_version"] != self.spec.encoding_version):
            return None
        blob = row["vector"]
        if not isinstance(blob, bytes) or len(blob) != self.spec.dimensions * 4:
            return None
        if hashlib.sha256(blob).hexdigest() != row["checksum"]:
            return None
        value = np.frombuffer(blob, dtype="<f4")
        norm = np.linalg.norm(value)
        if not np.isfinite(value).all() or not np.isfinite(norm) or abs(float(norm) - 1.0) > 0.002:
            return None
        return value.copy()

    def read(self, store, sources: Mapping[str, tuple[str, str]], *, now: int, state: tuple) -> VectorCacheResult:
        def operation(connection, meta, current):
            if not current:
                return VectorCacheResult()
            params = (*sorted(current), store.owner_id, store.character_id, self.spec.namespace)
            sql = "SELECT * FROM memory_vector_cache WHERE memory_id IN (" + ",".join("?" for _ in current)
            rows = connection.execute(sql + ") AND owner_id=? AND character_id=? AND namespace=?", params)
            found, invalid = {}, []
            for row in rows:
                key = row["memory_id"]
                value = self._decode(row, meta) if (row["fingerprint"], row["scope"]) == sources[key] else None
                if value is None:
                    invalid.append((key, row["owner_id"], row["character_id"], row["scope"], row["namespace"], row["fingerprint"]))
                else:
                    found[key] = value
            connection.executemany("""DELETE FROM memory_vector_cache WHERE memory_id=? AND owner_id=?
                AND character_id=? AND scope=? AND namespace=? AND fingerprint=?""", invalid)
            return VectorCacheResult(vectors=found, discarded=len(invalid))
        return self._execute(store, sources=sources, now=now, state=state, operation=operation)

    def write(self, store, sources: Mapping[str, tuple[str, str]], vectors: Mapping, *, now: int, state: tuple) -> VectorCacheResult:
        def operation(connection, meta, current):
            import numpy as np
            values = []
            for key in sorted(current):
                raw = np.asarray(vectors.get(key), dtype="<f4")
                if raw.shape != (self.spec.dimensions,) or not np.isfinite(raw).all():
                    continue
                norm = np.linalg.norm(raw)
                if not np.isfinite(norm) or abs(float(norm) - 1.0) > 0.002:
                    continue
                blob = raw.tobytes()
                fingerprint, scope = sources[key]
                values.append((key, store.owner_id, store.character_id, scope, fingerprint,
                    self.spec.model_name, self.spec.model_revision, self.spec.dimensions, self.spec.encoding_version,
                    self.spec.namespace, meta["generation"], blob, hashlib.sha256(blob).hexdigest()))
            connection.executemany("INSERT OR REPLACE INTO memory_vector_cache VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
            return VectorCacheResult(written=len(values))
        return self._execute(store, sources=sources, now=now, state=state, operation=operation)

    def clear(self, store, *, now: int) -> VectorCacheResult:
        """Delete only derived rows; leave triggers/schema and authority intact."""
        def operation(connection, meta, current):
            connection.execute("DELETE FROM memory_vector_cache")
            return VectorCacheResult()
        return self._execute(store, sources={}, now=now, state=store.current_index_state(now=now), operation=operation)
