from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Iterable

from .emotional_memory import EmotionalMemoryEntry


MODEL_NAME = "BAAI/bge-small-zh-v1.5"
MODEL_REVISION = "46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59"


def _identity(entry: EmotionalMemoryEntry) -> tuple:
    return (entry.memory_id, entry.character_id, entry.owner_id, entry.version,
            entry.title, entry.summary, entry.tags, entry.scope, entry.valid_from,
            entry.valid_until, entry.deleted, entry.source_ids)


class SemanticMemoryRetriever:
    def __init__(self, *, cache_dir: Path | str, character_id: str, owner_id: str,
                 local_files_only: bool = False, minimum_cosine: float = 0.45) -> None:
        if not 0 <= minimum_cosine <= 1:
            raise ValueError("minimum_cosine must be between zero and one")
        self.cache_dir = Path(cache_dir)
        self.character_id = character_id
        self.owner_id = owner_id
        self.local_files_only = local_files_only
        self.minimum_cosine = minimum_cosine
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="memory-embedding")
        self._lock = Lock()
        self._model = None
        self._generation = 0
        self._vectors = {}
        self._prepared_query = ""
        self._scores = {}
        self._cosines = {}
        self._closed = False
        self._pending = 0
        self._error = None

    @property
    def status(self) -> dict:
        with self._lock:
            return {"model": MODEL_NAME, "model_revision": MODEL_REVISION, "model_loaded": self._model is not None,
                    "pending": self._pending, "closed": self._closed,
                    "indexed_entries": len(self._vectors), "error": self._error}

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
                                           cache_dir=str(self.cache_dir),
                                           allow_patterns=["model_optimized.onnx", "*.json"],
                                           local_files_only=self.local_files_only)
            model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(self.cache_dir),
                                  threads=2, providers=["CPUExecutionProvider"],
                                  specific_model_path=model_path,
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
        # 只接受宿主有效视图；不把被撤销的正文保存到第二份磁盘事实库。
        eligible = tuple(entry for entry in entries
                         if entry.character_id == self.character_id and entry.owner_id == self.owner_id
                         and entry.is_active(now=now, scope=scope))
        with self._lock:
            generation = self._generation
        return self._submit(self._prepare, query, eligible, generation)

    def _prepare(self, query: str, entries: tuple[EmotionalMemoryEntry, ...], generation: int) -> None:
        import numpy as np

        if not query.strip() or not entries:
            with self._lock:
                if generation == self._generation:
                    self._scores = {}
                    self._cosines = {}
                    self._vectors = {}
                    self._prepared_query = query
            return
        model = self._load_model()
        eligible_keys = {_identity(entry) for entry in entries}
        with self._lock:
            vectors = {key: value for key, value in self._vectors.items()
                       if key in eligible_keys}
        missing = [entry for entry in entries if _identity(entry) not in vectors]
        if missing:
            texts = [" ".join((entry.title, entry.summary, " ".join(entry.tags))) for entry in missing]
            for entry, vector in zip(missing, model.passage_embed(texts), strict=True):
                vectors[_identity(entry)] = vector
        query_vector = next(model.query_embed(query))
        scores = {}
        cosines = {}
        for entry in entries:
            vector = vectors[_identity(entry)]
            cosine = float(np.dot(query_vector, vector) / (np.linalg.norm(query_vector) * np.linalg.norm(vector)))
            cosines[entry.memory_id] = cosine
            if cosine >= self.minimum_cosine:
                # 现有融合接口以 0.65 为准入阈值；这里先按模型余弦门槛筛选，
                # 再单调映射至该接口区间。分值是排序信号，不是事实置信度。
                scores[_identity(entry)] = 0.65 + 0.35 * min(1.0, max(0.0, cosine))
        with self._lock:
            if generation == self._generation and not self._closed:
                self._vectors = vectors
                self._prepared_query = query
                self._scores = scores
                self._cosines = cosines

    def __call__(self, query: str, entries: tuple[EmotionalMemoryEntry, ...]) -> dict[str, float]:
        # service 已按当前时间/场景筛选；精确版本比较再阻断纠正后的旧向量。
        with self._lock:
            if self._closed or query != self._prepared_query:
                return {}
            return {entry.memory_id: self._scores[_identity(entry)] for entry in entries
                    if not entry.deleted and _identity(entry) in self._scores
                    and entry.owner_id == self.owner_id and entry.character_id == self.character_id}

    def invalidate(self) -> None:
        with self._lock:
            self._generation += 1
            self._scores = {}
            self._cosines = {}
            self._vectors = {}
            self._prepared_query = ""

    def close(self) -> None:
        self.invalidate()
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
