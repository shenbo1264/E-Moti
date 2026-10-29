from __future__ import annotations

"""Adapter between E-Moti's current story runtime and plugin contributions."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Generic, TypeVar

from .companion_story_runtime import CompanionStoryRuntime
from .plugin_api import (
    ActionRequest,
    ActionResult,
    ContextAssembly,
    ContributionFailure,
    EventDispatchReport,
    MemoryProposal,
    PluginEvent,
    SkillRequest,
    SkillResult,
    thaw_value,
)
from .plugin_runtime import PluginRuntime
from .emotional_memory_policy import MemoryCandidate


@dataclass(frozen=True, slots=True)
class PluginEventProcessingResult:
    event: PluginEvent
    dispatch: EventDispatchReport
    memory_ids: tuple[str, ...] = ()
    rejected_proposals: tuple[str, ...] = ()
    pending_confirmation: tuple[str, ...] = ()
    failures: tuple[ContributionFailure, ...] = ()


ExecutionT = TypeVar("ExecutionT", ActionResult, SkillResult)


@dataclass(frozen=True, slots=True)
class PluginExecutionResult(Generic[ExecutionT]):
    execution: ExecutionT
    processed_events: tuple[PluginEventProcessingResult, ...] = ()
    memory_ids: tuple[str, ...] = ()
    rejected_proposals: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SettledEventBridgeResult:
    builtin_memory_ids: tuple[str, ...] = ()
    plugin_memory_ids: tuple[str, ...] = ()
    processed_events: tuple[PluginEventProcessingResult, ...] = ()


@dataclass(slots=True)
class PluginStoryBridge:
    """Run plugin hooks without handing plugins authority over game state."""

    story: CompanionStoryRuntime
    plugins: PluginRuntime
    character_id: str

    def record_settled_events(
        self,
        events: list[object] | tuple[object, ...],
        *,
        now: int,
    ) -> SettledEventBridgeResult:
        rows = tuple({**_domain_event_payload(event), "event_id": _domain_event_id(event, index=index, now=now)}
                     for index, event in enumerate(events))
        builtin_ids = tuple(self.story.record_settled_events(rows, now=now))
        processed: list[PluginEventProcessingResult] = []
        plugin_ids: list[str] = []
        for index, event in enumerate(rows):
            plugin_event = PluginEvent(
                event_type="companion.event.settled",
                event_id=_domain_event_id(event, index=index, now=now),
                character_id=self.character_id,
                occurred_at=now,
                durable=True,
                source_plugin_id="host",
                payload=_domain_event_payload(event),
            )
            result = self.process_plugin_event(plugin_event)
            processed.append(result)
            plugin_ids.extend(result.memory_ids)
        return SettledEventBridgeResult(builtin_ids, tuple(plugin_ids), tuple(processed))

    def execute_action(self, request: ActionRequest) -> PluginExecutionResult[ActionResult]:
        result = self.plugins.execute_action(request)
        return self._process_execution(result)

    def execute_skill(self, request: SkillRequest) -> PluginExecutionResult[SkillResult]:
        result = self.plugins.execute_skill(request)
        return self._process_execution(result)

    def process_plugin_event(self, event: PluginEvent) -> PluginEventProcessingResult:
        if event.character_id != self.character_id or self.story.memory.character_id != self.character_id:
            return PluginEventProcessingResult(event, EventDispatchReport(), rejected_proposals=("character_scope_mismatch",))
        epoch = self.story.memory.store.context_epoch
        dispatch = self.plugins.emit(event)
        proposal_report = self.plugins.collect_memory_proposals(event)
        memory_ids: list[str] = []
        rejected = list(proposal_report.rejected_proposal_ids)
        pending: list[str] = []
        failures = list(dispatch.failures) + list(proposal_report.failures)
        for proposal in proposal_report.proposals:
            if not event.durable or proposal.metadata.get("scope", "companion") != "companion":
                rejected.append(proposal.proposal_id)
                continue
            candidate = self._proposal_candidate(proposal, event=event)
            if self.story.memory.store.is_retired_origin(entry=candidate.to_memory(now=event.occurred_at)):
                rejected.append(proposal.proposal_id)
                continue
            if proposal.requires_user_confirmation:
                try:
                    self.story.memory.propose_candidate(candidate, pending_id=proposal.proposal_id, expected_epoch=epoch)
                    pending.append(proposal.proposal_id)
                except ValueError:
                    rejected.append(proposal.proposal_id)
                continue
            try:
                memory_id = self._persist_proposal(proposal, event=event, expected_epoch=epoch)
            except ValueError:
                rejected.append(proposal.proposal_id)
                continue
            if memory_id:
                memory_ids.append(memory_id)
        return PluginEventProcessingResult(
            event=event,
            dispatch=dispatch,
            memory_ids=tuple(memory_ids),
            rejected_proposals=tuple(rejected),
            pending_confirmation=tuple(pending),
            failures=tuple(failures),
        )

    def build_expression_context(
        self,
        base_context: Mapping[str, object],
        *,
        query: str,
        now: int,
        relationship_stage: str,
        state_snapshot: Mapping[str, object] | None = None,
    ) -> tuple[dict[str, object], object, ContextAssembly]:
        context, bundle = self.story.build_expression_context(
            base_context,
            query=query,
            now=now,
            relationship_stage=relationship_stage,
        )
        assembly = self.plugins.build_context(
            character_id=self.character_id,
            query=query,
            now=now,
            state_snapshot=state_snapshot or {},
        )
        if assembly.sections:
            context["plugin_context"] = thaw_value(assembly.sections)
        return context, bundle, assembly

    def _process_execution(
        self,
        result: ExecutionT,
    ) -> PluginExecutionResult[ExecutionT]:
        processed = tuple(self.process_plugin_event(event) for event in result.events)
        return PluginExecutionResult(
            execution=result,
            processed_events=processed,
            memory_ids=tuple(memory_id for row in processed for memory_id in row.memory_ids),
            rejected_proposals=tuple(
                proposal_id for row in processed for proposal_id in row.rejected_proposals
            ),
        )

    def _proposal_candidate(self, proposal: MemoryProposal, *, event: PluginEvent) -> MemoryCandidate:
        metadata = dict(thaw_value(proposal.metadata))
        metadata.update({"plugin_proposal_id": proposal.proposal_id, "plugin_event_id": event.event_id,
                         "source_plugin_id": event.source_plugin_id})
        return MemoryCandidate(character_id=self.character_id, owner_id=self.story.memory.owner_id,
            kind=proposal.kind, title=proposal.title, summary=proposal.summary, source=proposal.source,
            occurred_at=event.occurred_at, source_ids=tuple(dict.fromkeys((*proposal.source_ids, event.event_id))),
            tags=proposal.tags, importance=proposal.importance, relationship_delta=proposal.relationship_delta,
            pinned=proposal.pinned, requires_user_confirmation=proposal.requires_user_confirmation, metadata=metadata)

    def _persist_proposal(self, proposal: MemoryProposal, *, event: PluginEvent,
                          expected_epoch: int | None = None) -> str:
        existing = next(
            (
                memory
                for memory in self.story.memory.store.load_memories()
                if memory.metadata.get("plugin_proposal_id") == proposal.proposal_id
            ),
            None,
        )
        if existing is not None:
            if existing.deleted or existing.metadata.get("corrected_by_user"):
                return ""
            metadata = dict(existing.metadata)
            metadata.update(dict(thaw_value(proposal.metadata)))
            self.story.memory.store.upsert_memory(
                replace(
                    existing,
                    summary=proposal.summary or existing.summary,
                    updated_at=max(existing.updated_at, event.occurred_at),
                    metadata=metadata,
                ), expected_epoch=expected_epoch,
            )
            return ""
        metadata = dict(thaw_value(proposal.metadata))
        metadata.update(
            {
                "plugin_proposal_id": proposal.proposal_id,
                "plugin_event_id": event.event_id,
                "source_plugin_id": event.source_plugin_id,
                "relationship_delta": proposal.relationship_delta,
            }
        )
        memory = self.story.memory.remember(
            kind=proposal.kind,
            title=proposal.title,
            summary=proposal.summary,
            source=proposal.source,
            now=event.occurred_at,
            importance=proposal.importance,
            tags=proposal.tags,
            pinned=proposal.pinned,
            user_confirmed=False,
            metadata=metadata,
            source_ids=tuple(dict.fromkeys((*proposal.source_ids, event.event_id))),
            expected_epoch=expected_epoch,
        )
        return "" if memory.deleted else memory.memory_id


def _domain_event_payload(event: object) -> dict[str, object]:
    if isinstance(event, Mapping):
        payload = event.get("payload", {})
        return {
            "event_type": str(event.get("event_type", event.get("type", ""))),
            "speech": str(event.get("speech", "")),
            "payload": dict(payload) if isinstance(payload, Mapping) else {},
        }
    payload = getattr(event, "payload", {})
    return {
        "event_type": str(getattr(event, "event_type", getattr(event, "type", ""))),
        "speech": str(getattr(event, "speech", "")),
        "payload": dict(payload) if isinstance(payload, Mapping) else {},
    }


def _domain_event_id(event: object, *, index: int, now: int) -> str:
    if isinstance(event, Mapping):
        value = event.get("event_id") or event.get("id")
    else:
        value = getattr(event, "event_id", None) or getattr(event, "id", None)
    return str(value or f"host-{now}-{index}")
