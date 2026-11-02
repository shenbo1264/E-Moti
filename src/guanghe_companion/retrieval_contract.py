"""Read-only retrieval contract shared by desktop, evaluators and future clients.

Scores are ranking signals. Only source validity and explicit evidence checks
can make a claim eligible; a similarity value is never a fact probability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Mapping

from .emotional_memory import MemoryContextBundle


@dataclass(frozen=True, slots=True)
class RetrievalBudget:
    max_candidates: int = 64
    max_expansions: int = 1
    max_intents: int = 4
    max_source_entries: int = 8
    max_context_chars: int = 4000

    def __post_init__(self):
        if not (1 <= self.max_candidates <= 256 and 0 <= self.max_expansions <= 2
                and 1 <= self.max_intents <= 4 and 1 <= self.max_source_entries <= 16
                and 512 <= self.max_context_chars <= 6000):
            raise ValueError("retrieval budget is outside the bounded local policy")


@dataclass(frozen=True, slots=True)
class RetrievalIntent:
    route: str
    query: str
    subjects: tuple[str, ...] = ()
    predicates: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ("companion",)
    temporal_mode: str = "current"
    as_of: int | None = None
    as_of_end: int | None = None
    detail: bool = False
    requires_shared_event: bool = False
    authority: str = ""
    app: str = ""
    version: str = ""
    reason: str = ""
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RetrievalPlan:
    intents: tuple[RetrievalIntent, ...]
    inherited_context: bool = False
    unresolved_reference: bool = False
    reason: str = "deterministic_local_router"

    @property
    def routes(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(intent.route for intent in self.intents))

    @property
    def needs_semantic(self) -> bool:
        return any(i.route in {"episode", "task", "bounded"} for i in self.intents)


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    memory_id: str
    accepted: bool
    reason: str
    route: str
    supported_details: tuple[str, ...] = ()
    missing_details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExternalStateEvidence:
    """An adapter attests a current external state; retrieval never persists it."""
    authority: str
    summary: str
    observed_at: int
    valid_until: int
    source_id: str
    character_id: str
    owner_id: str = "local_user"
    version: str = ""

    def valid_for(self, *, authority: str, character_id: str, owner_id: str, now: int) -> bool:
        return (self.authority == authority and self.character_id == character_id
                and self.owner_id == owner_id and bool(self.summary.strip())
                and bool(self.source_id) and 0 <= self.observed_at <= now < self.valid_until)


ExternalStateReader = Callable[[RetrievalIntent, int], ExternalStateEvidence | None]


@dataclass(frozen=True, slots=True)
class RetrievalTrace:
    route: tuple[str, ...]
    reason: str
    status: str
    retrieval_calls: int = 0
    rows_loaded: int = 0
    candidate_count: int = 0
    expansion_count: int = 0
    selected_memory_ids: tuple[str, ...] = ()
    stage_ms: Mapping[str, float] = field(default_factory=dict)
    intent_status: tuple[dict[str, object], ...] = ()
    decisions: tuple[EvidenceDecision, ...] = ()
    index_revision: int = 0
    context_epoch: int = 0
    semantic_status: str = "not_needed"
    retries: int = 0
    evidence_level: str = "raw"
    context_chars: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceContextBundle(MemoryContextBundle):
    retrieval: dict[str, object] = field(default_factory=dict)
    overview: dict[str, object] = field(default_factory=dict)
    external_state: tuple[ExternalStateEvidence, ...] = ()
    overview_source_ids: tuple[str, ...] = ()
    resolution_evidence: tuple[dict[str, object], ...] = ()
    source_spans: tuple[dict[str, object], ...] = ()

    def to_prompt_payload(self) -> dict[str, object]:
        payload = super(EvidenceContextBundle, self).to_prompt_payload()
        # The same evidence is represented once. L1 extractive claims replace
        # their L2 cards until a detail request explicitly expands the sources.
        if self.overview:
            payload["memory_overview"] = self.overview
            raw = [r for r in payload.get("shared_memories", [])
                   if r["memory_id"] not in self.overview_source_ids]
            if raw:
                payload["shared_memories"] = raw
            else:
                payload.pop("shared_memories", None)
            payload.pop("relationship_chapter", None)
        by_id = {m.memory_id: m for m in self.memories}
        for row in payload.get("shared_memories", []):
            memory = by_id[row["memory_id"]]
            row["evidence_fingerprint"] = memory.evidence_fingerprint()
            row["valid_from"] = memory.valid_from
            row["facts"] = {key: value for key, value in memory.metadata.items()
                            if key in {"fact_subject", "fact_predicate", "fact_slot", "fact_value",
                                       "fact_domain", "plan_status", "app", "version", "preconditions", "outcome"}}
        if self.retrieval:
            payload["retrieval"] = self.retrieval
        if self.external_state:
            payload["external_state"] = [asdict(state) for state in self.external_state]
        if self.resolution_evidence:
            payload["resolution_evidence"] = list(self.resolution_evidence)
        if self.source_spans:
            payload["source_spans"] = list(self.source_spans)
        return payload


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    bundle: EvidenceContextBundle
    plan: RetrievalPlan
    trace: RetrievalTrace

