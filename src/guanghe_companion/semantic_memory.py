from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Iterable

from .emotional_memory import EmotionalMemoryEntry


MODEL_NAME = "BAAI/bge-small-zh-v1.5"
MODEL_REVISION = "46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59"
MODEL_DIMENSIONS = 512
PASSAGE_ENCODING_VERSION = "title-summary-tags:normalized-f32-le:v1"
MANIFEST_PAGE_SIZE = 2048
PAYLOAD_BATCH_SIZE = 256
PASSAGE_BATCH_SIZE = 64


def _identity(entry: EmotionalMemoryEntry) -> tuple:
    # Includes factual metadata, confidence, provenance and effective time;
    # recall counters are excluded from the source fingerprint.
    return (entry.memory_id, entry.character_id, entry.owner_id, entry.evidence_fingerprint())


class _IndexChanged(RuntimeError):
    pass


class SemanticMemoryRetriever:
    """Optional CPU embeddings with revocable, rebuildable derived vectors.

    ``prepare`` retains the full-entry compatibility contract. ``prepare_indexed``
    follows SQLite's revision manifest and reads bodies only for missing content
    revisions. Its default SQLite projection survives process restarts. Cached
    vectors are never evidence; published scores are fenced by context epoch
    and source fingerprint, and retrieval rechecks effective time.
    """

    def __init__(self, *, cache_dir: Path | str, character_id: str, owner_id: str,
                 local_files_only: bool = False, minimum_cosine: float = 0.45,
                 persistent_cache: bool = True) -> None:
        if not 0 <= minimum_cosine <= 1:
            raise ValueError("minimum_cosine must be between zero and one")
        self.cache_dir = Path(cache_dir)
        self.character_id, self.owner_id = character_id, owner_id
        self.local_files_only, self.minimum_cosine = local_files_only, minimum_cosine
        from .memory_vector_cache import MemoryVectorCache, VectorCacheSpec
        self._persistent_cache = (MemoryVectorCache(VectorCacheSpec(MODEL_NAME, MODEL_REVISION,
            MODEL_DIMENSIONS, PASSAGE_ENCODING_VERSION)) if persistent_cache else None)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="memory-embedding")
        self._lock = Lock()
        self._model = None
        self._generation = 0
        self._vectors, self._vector_scopes, self._matrix_cache = {}, {}, {}
        self._cache_pending = set()
        self._headers, self._watched_scopes = {}, ()
        self._index_generation, self._manifest_revision, self._store_path = "", None, ""
        self._prepared_store, self._prepared_epoch = None, None
        self._prepared_now, self._prepared_scopes, self._prepared_query = 0, (), ""
        self._scores, self._cosines, self._candidate_scopes = {}, {}, {}
        self._closed, self._pending, self._error = False, 0, None
        self._encoded_entries_total, self._query_embed_count = 0, 0
        self._persistent_cache_error = None
        self._last_stats = {"last_encoded_entries": 0, "manifest_ms": 0.0,
                            "payload_read_ms": 0.0, "passage_encoding_ms": 0.0,
                            "query_embedding_ms": 0.0, "search_ms": 0.0,
                            "index_prepare_ms": 0.0, "prepare_ms": 0.0,
                            "manifest_pages": 0, "payload_rows_loaded": 0,
                            "prepare_retries": 0, "barrier_reads": 0,
                            "persistent_cache_hits": 0, "persistent_cache_writes": 0,
                            "persistent_cache_discarded": 0, "persistent_cache_errors": 0,
                            "persistent_cache_read_ms": 0.0, "persistent_cache_write_ms": 0.0}

    @property
    def status(self) -> dict:
        with self._lock:
            return {"model": MODEL_NAME, "model_revision": MODEL_REVISION, "model_loaded": self._model is not None,
                    "pending": self._pending, "closed": self._closed,
                    "indexed_entries": len(self._vectors), "prepared_entries": len(self._cosines),
                    "error": self._error, "encoded_entries_total": self._encoded_entries_total,
                    "query_embed_count": self._query_embed_count,
                    "manifest_revision": self._manifest_revision, "index_generation": self._index_generation,
                    "generation": self._generation, "watched_scopes": list(self._watched_scopes),
                    "persistent_cache_enabled": self._persistent_cache is not None,
                    "persistent_cache_error": self._persistent_cache_error,
                    "persistent_cache_pending": len(self._cache_pending),
                    "passage_batch_size": PASSAGE_BATCH_SIZE, **self._last_stats}

    @property
    def last_cosines(self) -> dict[str, float]:
        with self._lock:
            return dict(self._cosines)

    def _load_model(self):
        if self._model is None:
            from fastembed import TextEmbedding
            from huggingface_hub import snapshot_download
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            model_path = snapshot_download(repo_id="Qdrant/bge-small-zh-v1.5", revision=MODEL_REVISION,
                cache_dir=str(self.cache_dir), allow_patterns=["model_optimized.onnx", "*.json"],
                local_files_only=self.local_files_only)
            model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(self.cache_dir), threads=2,
                providers=["CPUExecutionProvider"], specific_model_path=model_path,
                local_files_only=self.local_files_only)
            with self._lock:
                self._model = model
        return self._model

    def _submit(self, operation, *args) -> Future:
        with self._lock:
            if self._closed:
                raise RuntimeError("semantic retriever is closed")
            self._pending += 1
            future = self._executor.submit(operation, *args)
        future.add_done_callback(self._completed)
        return future

    def _completed(self, future: Future) -> None:
        with self._lock:
            self._pending -= 1
            error = None if future.cancelled() else future.exception()
            self._error = type(error).__name__ if error else None

    def warmup(self) -> Future:
        return self._submit(self._load_model)

    def prepare(self, query: str, entries: Iterable[EmotionalMemoryEntry], *, now: int,
                scope: str = "companion") -> Future:
        # Compatibility callers supply the complete current view of this scope.
        eligible = tuple(entry for entry in entries
            if entry.character_id == self.character_id and entry.owner_id == self.owner_id
            and entry.is_active(now=now, scope=scope))
        with self._lock:
            generation = self._generation
        return self._submit(self._prepare, query, eligible, generation, scope, now)

    def prepare_indexed(self, query: str, store, *, now: int,
                        scopes: tuple[str, ...] = ("companion",)) -> Future:
        if store.owner_id != self.owner_id or store.character_id != self.character_id:
            raise ValueError("semantic index requires the same owner and character")
        scopes = tuple(dict.fromkeys(scopes))
        if not scopes or len(scopes) > 8 or any(not isinstance(s, str) or not s for s in scopes):
            raise ValueError("semantic preparation requires one to eight explicit scopes")
        with self._lock:
            generation = self._generation
        return self._submit(self._prepare_indexed, str(query), store, int(now), scopes, generation)

    def _stats(self):
        return {key: 0.0 if key.endswith("_ms") else 0 for key in self._last_stats}

    def _cancelled(self, generation):
        with self._lock:
            return self._closed or generation != self._generation

    def _encode(self, entries, vectors, vector_scopes, stats):
        if not entries:
            return
        import numpy as np
        started = perf_counter()
        texts = [" ".join((entry.title, entry.summary, " ".join(entry.tags))) for entry in entries]
        for entry, raw in zip(entries, self._load_model().passage_embed(texts, batch_size=PASSAGE_BATCH_SIZE), strict=True):
            vector = np.asarray(raw, dtype=np.float32)
            norm = np.linalg.norm(vector)
            if vector.ndim != 1 or not np.isfinite(vector).all() or not np.isfinite(norm) or norm <= 0:
                raise ValueError("embedding provider returned an invalid passage vector")
            key = _identity(entry)
            vectors[key], vector_scopes[key] = vector / norm, entry.scope
            stats["last_encoded_entries"] += 1
            with self._lock:
                self._encoded_entries_total += 1
        stats["passage_encoding_ms"] += (perf_counter() - started) * 1000

    def _search(self, query, keys, vectors, matrix_cache, stats):
        if not query.strip() or not keys:
            return {}, {}
        import numpy as np
        started = perf_counter()
        raw = next(self._load_model().query_embed(query))
        query_vector = np.asarray(raw, dtype=np.float32)
        norm = np.linalg.norm(query_vector)
        if query_vector.ndim != 1 or not np.isfinite(query_vector).all() or not np.isfinite(norm) or norm <= 0:
            raise ValueError("embedding provider returned an invalid query vector")
        with self._lock:
            self._query_embed_count += 1
        stats["query_embedding_ms"] += (perf_counter() - started) * 1000
        started = perf_counter()
        matrix = matrix_cache.get(keys)
        if matrix is None:
            matrix = np.stack([vectors[key] for key in keys])
            if len(matrix_cache) >= 4:
                matrix_cache.clear()
            matrix_cache[keys] = matrix
        cosines_array = matrix @ (query_vector / norm)
        if not np.isfinite(cosines_array).all():
            raise ValueError("semantic similarity must be finite")
        cosines = {key[0]: float(value) for key, value in zip(keys, cosines_array, strict=True)}
        scores = {key: 0.65 + 0.35 * min(1.0, max(0.0, cosines[key[0]]))
                  for key in keys if cosines[key[0]] >= self.minimum_cosine}
        stats["search_ms"] += (perf_counter() - started) * 1000
        return scores, cosines

    def _publish(self, *, query, generation, vectors, vector_scopes, matrix_cache,
                 scores, cosines, scopes, now, stats, started, store=None, epoch=None,
                 headers=None, watched_scopes=None, index_generation=None, revision=None,
                 cache_pending=None):
        with self._lock:
            stats["index_prepare_ms"] = sum(stats[key] for key in
                ("manifest_ms", "payload_read_ms", "passage_encoding_ms",
                 "persistent_cache_read_ms", "persistent_cache_write_ms"))
            stats["prepare_ms"] = (perf_counter() - started) * 1000
            self._last_stats = dict(stats)
            if generation != self._generation or self._closed:
                return
            self._vectors, self._vector_scopes, self._matrix_cache = vectors, vector_scopes, matrix_cache
            self._prepared_query, self._scores, self._cosines = query, scores, cosines
            self._prepared_store, self._prepared_epoch = store, epoch
            self._prepared_now, self._prepared_scopes = now, scopes
            self._candidate_scopes = {key[0]: vector_scopes[key] for key in vectors if key[0] in cosines}
            if headers is not None:
                self._headers, self._watched_scopes = headers, watched_scopes
                self._index_generation, self._manifest_revision = index_generation, revision
                self._store_path = str(store.state_path.resolve())
                self._cache_pending = cache_pending or set()

    def _cache_result(self, result, stats):
        stats["persistent_cache_errors"] += int(not result.available)
        if result.error:
            with self._lock:
                self._persistent_cache_error = result.error

    def _persist_batch(self, store, ids, eligible, vectors, pending, *, now, state, stats):
        requested = {key: (eligible[key].fingerprint, eligible[key].scope) for key in ids}
        keys = [(key, self.character_id, self.owner_id, eligible[key].fingerprint) for key in ids]
        encoded = {key[0]: vectors[key] for key in keys}
        cache_started = perf_counter()
        result = self._persistent_cache.write(store, requested, encoded, now=now, state=state)
        stats["persistent_cache_write_ms"] += (perf_counter() - cache_started) * 1000
        stats["persistent_cache_writes"] += result.written
        self._cache_result(result, stats)
        if result.available and result.written == len(keys):
            pending.difference_update(keys)

    def _prepare(self, query, entries, generation, scope, now):
        started, stats = perf_counter(), self._stats()
        eligible_keys = {_identity(entry) for entry in entries}
        with self._lock:
            vectors = {key: value for key, value in self._vectors.items()
                       if self._vector_scopes.get(key) != scope or key in eligible_keys}
            vector_scopes = {key: value for key, value in self._vector_scopes.items() if key in vectors}
            matrix_cache = dict(self._matrix_cache) if set(vectors) == set(self._vectors) else {}
        if query.strip():
            missing = [entry for entry in entries if _identity(entry) not in vectors]
            self._encode(missing, vectors, vector_scopes, stats)
            if missing:
                matrix_cache.clear()
            scores, cosines = self._search(query, tuple(_identity(entry) for entry in entries), vectors, matrix_cache, stats)
        else:
            scores, cosines = {}, {}
        self._publish(query=query, generation=generation, vectors=vectors, vector_scopes=vector_scopes,
            matrix_cache=matrix_cache, scores=scores, cosines=cosines, scopes=(scope,), now=now,
            stats=stats, started=started)

    @staticmethod
    def _collect_manifest(store, *, now, scopes, after_revision, stats):
        started = perf_counter()
        records, removed, after_id, identity = {}, set(), "", None
        while True:
            page = store.index_manifest(now=now, scopes=scopes, after_revision=after_revision,
                                        limit=MANIFEST_PAGE_SIZE, after_id=after_id)
            stats["manifest_pages"] += 1
            current = (page.generation, page.revision, page.context_epoch)
            if identity is not None and current != identity:
                raise _IndexChanged("manifest changed during pagination")
            identity = current
            records.update((record.memory_id, record) for record in page.records)
            removed.update(page.removed_ids)
            if not page.has_more:
                stats["manifest_ms"] += (perf_counter() - started) * 1000
                return page, records, removed
            if not page.next_after_id or page.next_after_id <= after_id:
                raise RuntimeError("memory manifest did not advance its cursor")
            after_id = page.next_after_id

    def _prepare_indexed(self, query, store, now, scopes, generation):
        from .memory_index import IndexedMemoryQuery
        from .memory_vector_cache import VectorCacheStale
        started, stats = perf_counter(), self._stats()
        with self._lock:
            self._persistent_cache_error = None
            same_store = self._store_path == str(store.state_path.resolve())
            vectors = dict(self._vectors) if same_store else {}
            vector_scopes = dict(self._vector_scopes) if same_store else {}
            matrix_cache = dict(self._matrix_cache) if same_store else {}
            headers = dict(self._headers) if same_store else {}
            watched_scopes = tuple(dict.fromkeys((*self._watched_scopes, *scopes))) if same_store else scopes
            old_generation = self._index_generation if same_store else ""
            cache_pending = set(self._cache_pending) if same_store else set()
            after_revision = self._manifest_revision if same_store and watched_scopes == self._watched_scopes else None
        needs_cache_sync = not same_store
        # A cursor covers all visited scopes. A newly visited scope needs a full
        # metadata snapshot, while unchanged content vectors are reused.
        for attempt in range(3):
            if self._cancelled(generation):
                return
            stats["prepare_retries"] = attempt
            try:
                page, records, removed = self._collect_manifest(store, now=now, scopes=watched_scopes,
                    after_revision=after_revision, stats=stats)
                if old_generation and page.generation != old_generation:
                    vectors, vector_scopes, matrix_cache, headers = {}, {}, {}, {}
                    cache_pending.clear()
                    needs_cache_sync = True
                    old_generation, after_revision = page.generation, None
                    if not page.full_snapshot:
                        continue
                old_generation = page.generation
                if page.full_snapshot:
                    headers = {}
                for key in removed:
                    headers.pop(key, None)
                for key, record in records.items():
                    if record.removed or record.scope not in watched_scopes:
                        headers.pop(key, None)
                    else:
                        # Future sources activate from their effective time;
                        # activation does not require a new write event.
                        headers[key] = record
                previous_keys = set(vectors)
                vectors = {key: vector for key, vector in vectors.items()
                    if key[0] in headers and key[3] == headers[key[0]].fingerprint
                    and (not headers[key[0]].valid_until or now < headers[key[0]].valid_until)}
                if set(vectors) != previous_keys:
                    # Matrices are derived copies too: discard any matrix that
                    # might still contain an invalidated source's vector.
                    matrix_cache.clear()
                vector_scopes = {key: headers[key[0]].scope for key in vectors}
                cache_pending.intersection_update(vectors)
                eligible = {key: record for key, record in headers.items()
                    if record.scope in scopes and record.valid_from <= now
                    and (not record.valid_until or now < record.valid_until)}
                keys = tuple((key, self.character_id, self.owner_id, record.fingerprint)
                             for key, record in sorted(eligible.items()))
                missing_ids = [key[0] for key in keys if key not in vectors] if query.strip() else []
                if self._persistent_cache is not None and query.strip():
                    # Empty first/rebuilt indexes still reinstall invalidation
                    # triggers and clear vectors tied to an older generation.
                    offsets = range(0, len(missing_ids), PAYLOAD_BATCH_SIZE)
                    if not missing_ids and needs_cache_sync:
                        offsets = (0,)
                    for offset in offsets:
                        batch = missing_ids[offset:offset + PAYLOAD_BATCH_SIZE]
                        requested = {key: (eligible[key].fingerprint, eligible[key].scope) for key in batch}
                        cache_started = perf_counter()
                        result = self._persistent_cache.read(store, requested, now=now,
                            state=(page.generation, page.revision, page.context_epoch))
                        stats["persistent_cache_read_ms"] += (perf_counter() - cache_started) * 1000
                        stats["persistent_cache_hits"] += len(result.vectors)
                        stats["persistent_cache_discarded"] += result.discarded
                        self._cache_result(result, stats)
                        needs_cache_sync = not result.available
                        for key, value in result.vectors.items():
                            identity = (key, self.character_id, self.owner_id, eligible[key].fingerprint)
                            vectors[identity], vector_scopes[identity] = value, eligible[key].scope
                            cache_pending.discard(identity)
                        if self._cancelled(generation):
                            return
                    missing_ids = [key[0] for key in keys if key not in vectors]
                    # Retry a previously unavailable/stale durable write while
                    # retaining its already encoded, still-authorized vector.
                    pending_ids = [key[0] for key in sorted(cache_pending) if key[0] in eligible]
                    for offset in range(0, len(pending_ids), PAYLOAD_BATCH_SIZE):
                        self._persist_batch(store, pending_ids[offset:offset + PAYLOAD_BATCH_SIZE],
                            eligible, vectors, cache_pending, now=now,
                            state=(page.generation, page.revision, page.context_epoch), stats=stats)
                for offset in range(0, len(missing_ids), PAYLOAD_BATCH_SIZE):
                    payload_started = perf_counter()
                    ids = tuple(missing_ids[offset:offset + PAYLOAD_BATCH_SIZE])
                    snapshot = store.read_indexed_snapshot(IndexedMemoryQuery(scopes=scopes, memory_ids=ids,
                        limit=len(ids)), now=now, include_chapters=False, include_profile_sources=False)
                    stats["payload_read_ms"] += (perf_counter() - payload_started) * 1000
                    stats["payload_rows_loaded"] += len(snapshot.entries)
                    if (snapshot.index_generation != page.generation or snapshot.index_revision != page.revision
                            or snapshot.context_epoch != page.context_epoch
                            or {entry.memory_id for entry in snapshot.entries} != set(ids)
                            or any(entry.evidence_fingerprint() != eligible[entry.memory_id].fingerprint
                                   for entry in snapshot.entries)):
                        raise _IndexChanged("source changed before embedding")
                    self._encode(snapshot.entries, vectors, vector_scopes, stats)
                    if self._persistent_cache is not None:
                        cache_pending.update(_identity(entry) for entry in snapshot.entries)
                    if self._cancelled(generation):
                        return
                    if self._persistent_cache is not None:
                        self._persist_batch(store, ids, eligible, vectors, cache_pending, now=now,
                            state=(page.generation, page.revision, page.context_epoch), stats=stats)
                if missing_ids or stats["persistent_cache_hits"]:
                    matrix_cache.clear()
                scores, cosines = self._search(query, keys, vectors, matrix_cache, stats)
                # Revision also fences additions, which need not bump epoch.
                check_started = perf_counter()
                fence = store.current_index_state(now=now)
                stats["manifest_ms"] += (perf_counter() - check_started) * 1000
                stats["barrier_reads"] += 1
                if fence != (page.generation, page.revision, page.context_epoch):
                    raise _IndexChanged("source changed during embedding")
                self._publish(query=query, generation=generation, vectors=vectors, vector_scopes=vector_scopes,
                    matrix_cache=matrix_cache, scores=scores, cosines=cosines, scopes=scopes, now=now,
                    stats=stats, started=started, store=store, epoch=page.context_epoch,
                    headers=headers, watched_scopes=watched_scopes, index_generation=page.generation,
                    revision=page.revision, cache_pending=cache_pending)
                return
            except (_IndexChanged, VectorCacheStale):
                # Equal source fingerprints retain vectors during a bounded
                # header refresh. No full JSON body is read by this retry.
                after_revision = None
        self.invalidate()
        raise RuntimeError("semantic index changed repeatedly; retry retrieval")

    def _prepared_current(self, query):
        with self._lock:
            if self._closed or query != self._prepared_query:
                return False
            store, epoch, generation = self._prepared_store, self._prepared_epoch, self._generation
            index_state = (self._index_generation, self._manifest_revision, epoch)
        # Compatible legacy writers can change the authoritative document and
        # its derived revision without incrementing context_epoch themselves.
        # A metadata-only barrier also fences that path and an index rebuild.
        if store is not None and store.current_index_state() != index_state:
            return False
        with self._lock:
            return generation == self._generation and query == self._prepared_query and not self._closed

    def __call__(self, query: str, entries: tuple[EmotionalMemoryEntry, ...]) -> dict[str, float]:
        if not self._prepared_current(query):
            return {}
        with self._lock:
            return {entry.memory_id: self._scores[_identity(entry)] for entry in entries
                if entry.owner_id == self.owner_id and entry.character_id == self.character_id
                and entry.scope in self._prepared_scopes
                and entry.is_active(now=self._prepared_now, scope=entry.scope)
                and _identity(entry) in self._scores}

    def candidate_ids(self, query: str, *, limit: int = 32, scope: str | None = None) -> tuple[str, ...]:
        """Bounded ranked IDs, including weak signals for downstream checks.

        A nearest neighbour is not necessarily relevant or sufficient. Subject,
        field, source, scope and effective-time gates still apply at retrieval.
        """
        if not self._prepared_current(query):
            return ()
        with self._lock:
            ranked = sorted((key for key in self._cosines
                if scope is None or self._candidate_scopes.get(key) == scope),
                key=lambda key: (-self._cosines[key], key))
            return tuple(ranked[:max(0, min(int(limit), 256))])

    def invalidate(self) -> None:
        with self._lock:
            self._generation += 1
            self._scores, self._cosines, self._candidate_scopes = {}, {}, {}
            self._prepared_query = ""
            self._prepared_store, self._prepared_epoch = None, None
            # Vectors stay invisible until a fresh manifest authorizes sources.
            # An unrelated revision need not be reencoded after one deletion.

    def close(self) -> None:
        self.invalidate()
        with self._lock:
            self._closed = True
            self._vectors, self._vector_scopes, self._matrix_cache, self._headers = {}, {}, {}, {}
            self._cache_pending.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)
