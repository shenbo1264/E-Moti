"""Rank fusion adapted from Graphiti's Apache-2.0 licensed rrf utility.

Copyright 2024, Zep Software, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Changes for E-Moti: one-based ranks, a configurable positive integer constant,
per-retriever deduplication, and paired output. See third_party/graphiti/README.md.
"""

from __future__ import annotations

from collections import defaultdict


def reciprocal_rank_fusion(
    ranked_ids: list[list[str]], *, rank_constant: int = 60
) -> list[tuple[str, float]]:
    """Fuse already eligible memory IDs, preserving first-seen order on ties.

    Each distinct ID contributes 1 / (rank_constant + rank) per retriever,
    where rank starts at one after deduplicating that retriever's result. An ID
    found by several retrievers accumulates their contributions.

    This function has no persistence, validity, scope, or relevance semantics.
    Callers must exclude forgotten, superseded, expired, wrong-character, and
    otherwise ineligible candidates before fusion. An RRF score is not a
    probability or a fact-confidence score.
    """
    if isinstance(rank_constant, bool) or not isinstance(rank_constant, int) or rank_constant <= 0:
        raise ValueError("rank_constant must be a positive integer")

    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_ids:
        for rank, memory_id in enumerate(dict.fromkeys(ranked), start=1):
            scores[memory_id] += 1 / (rank_constant + rank)

    # dict insertion order and Python's stable sort make equal-score ties
    # deterministic relative to the order supplied by the retrievers.
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
