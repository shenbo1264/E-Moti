from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from .emotional_memory import EmotionalMemoryEntry

DEFAULT_TOP_K = 4
DEFAULT_MINIMUM_RELEVANCE = 0.12


@dataclass(frozen=True, slots=True)
class MemoryRetrievalScore:
    memory_id: str
    total: float
    relevance: float
    recency: float
    importance: float
    emotion: float
    relationship: float
    reinforcement: float


def tokenize(text: str) -> tuple[str, ...]:
    lowered = str(text).lower()
    latin = re.findall(r"[a-z0-9_]+", lowered)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", lowered)
    chinese_tokens: list[str] = []
    for run in chinese_runs:
        chinese_tokens.extend(run)
        if len(run) > 1:
            chinese_tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return tuple(dict.fromkeys([*latin, *chinese_tokens]))


def lexical_similarity(query: str, text: str) -> float:
    left = set(tokenize(query))
    right = set(tokenize(text))
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    union = len(left | right)
    jaccard = overlap / union if union else 0.0
    query_coverage = overlap / len(left)
    return min(1.0, 0.55 * jaccard + 0.45 * query_coverage)


def memory_strength(memory: EmotionalMemoryEntry, *, now: int) -> float:
    if memory.pinned:
        return max(0.85, memory.importance)
    age_days = max(0.0, (max(0, int(now)) - memory.occurred_at) / 86_400)
    emotion_factor = 1.0 + 1.5 * memory.emotion.intensity
    reinforcement_factor = min(3.0, 1.0 + math.log1p(memory.access_count))
    relationship_factor = 1.0 + max(0.0, memory.relationship_delta)
    half_life_days = 10.0 * emotion_factor * reinforcement_factor * relationship_factor
    decay = math.pow(0.5, age_days / max(1.0, half_life_days))
    return max(0.0, min(1.0, memory.importance * decay))


def score_memory(
    memory: EmotionalMemoryEntry,
    query: str,
    *,
    now: int,
    relationship_stage: str = "初识",
) -> MemoryRetrievalScore:
    relevance = lexical_similarity(
        query,
        " ".join((memory.title, memory.summary, " ".join(memory.tags))),
    )
    age_days = max(0.0, (max(0, int(now)) - memory.occurred_at) / 86_400)
    recency = math.pow(0.5, age_days / 21.0)
    importance = memory.importance
    emotion = memory.emotion.intensity
    relationship = max(0.0, memory.relationship_delta)
    if relationship_stage == "共同日常" and "共同日常" in memory.tags:
        relationship = min(1.0, relationship + 0.25)
    reinforcement = memory_strength(memory, now=now)

    total = (
        0.50 * relevance
        + 0.10 * recency
        + 0.15 * importance
        + 0.08 * emotion
        + 0.07 * relationship
        + 0.10 * reinforcement
    )
    if memory.pinned:
        total += 0.08
    if memory.user_confirmed:
        total += 0.03
    return MemoryRetrievalScore(
        memory_id=memory.memory_id,
        total=min(1.25, total),
        relevance=relevance,
        recency=recency,
        importance=importance,
        emotion=emotion,
        relationship=relationship,
        reinforcement=reinforcement,
    )


def rank_memories(
    memories: Iterable[EmotionalMemoryEntry],
    query: str,
    *,
    now: int,
    relationship_stage: str = "初识",
    top_k: int = DEFAULT_TOP_K,
    minimum_relevance: float = DEFAULT_MINIMUM_RELEVANCE,
) -> list[tuple[EmotionalMemoryEntry, MemoryRetrievalScore]]:
    """Rank episodic memories without forcing unrelated nostalgia.

    Core bonds belong in ``CoreBondProfile`` and are always visible. Episodic
    memories are recalled only when the current query shares a real topical
    signal. This prevents a beloved but unrelated memory from appearing in
    every line the character speaks.
    """

    scored: list[tuple[EmotionalMemoryEntry, MemoryRetrievalScore]] = []
    has_query = bool(tokenize(query))
    threshold = max(0.0, min(1.0, float(minimum_relevance)))
    for memory in memories:
        if memory.deleted:
            continue
        score = score_memory(memory, query, now=now, relationship_stage=relationship_stage)
        if has_query and score.relevance < threshold:
            continue
        scored.append((memory, score))
    scored.sort(
        key=lambda row: (
            row[1].total,
            row[0].pinned,
            row[0].updated_at,
            row[0].occurred_at,
        ),
        reverse=True,
    )
    return scored[: max(0, int(top_k))]
