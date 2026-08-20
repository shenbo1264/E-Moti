from __future__ import annotations

"""Public contracts for E-Moti's lightweight plugin runtime.

The contracts intentionally expose read-only snapshots and typed contribution
objects. Plugins propose behavior; the host remains authoritative for game
state, saves, inventory, relationships, and memory persistence.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, TypeAlias
from uuid import uuid4

PLUGIN_API_VERSION = "1"
PLUGIN_MANIFEST_SCHEMA_VERSION = 1


class PluginPermission(StrEnum):
    EVENTS_SUBSCRIBE = "events.subscribe"
    EVENTS_PUBLISH = "events.publish"
    ACTIONS_REGISTER = "actions.register"
    SKILLS_REGISTER = "skills.register"
    CONTEXT_PROVIDE = "context.provide"
    MEMORY_PROPOSE = "memory.propose"
    UI_REGISTER = "ui.register"
    SERVICES_REGISTER = "services.register"
    STORAGE_LOCAL = "storage.local"
    GAME_SNAPSHOT_READ = "game.snapshot.read"

    # Sensitive permissions require an explicit user grant.
    SCREEN_SUMMARY_READ = "screen.summary.read"
    NETWORK_HTTP = "network.http"
    CREDENTIALS_USE = "credentials.use"
    FILESYSTEM_EXTERNAL = "filesystem.external"
    TIMER_BACKGROUND = "timer.background"


SAFE_PLUGIN_PERMISSIONS = frozenset(
    {
        PluginPermission.EVENTS_SUBSCRIBE,
        PluginPermission.EVENTS_PUBLISH,
        PluginPermission.ACTIONS_REGISTER,
        PluginPermission.SKILLS_REGISTER,
        PluginPermission.CONTEXT_PROVIDE,
        PluginPermission.MEMORY_PROPOSE,
        PluginPermission.UI_REGISTER,
        PluginPermission.SERVICES_REGISTER,
        PluginPermission.STORAGE_LOCAL,
        PluginPermission.GAME_SNAPSHOT_READ,
    }
)

SENSITIVE_PLUGIN_PERMISSIONS = frozenset(set(PluginPermission) - set(SAFE_PLUGIN_PERMISSIONS))


@dataclass(frozen=True, slots=True)
class PluginDependency:
    plugin_id: str
    optional: bool = False


@dataclass(frozen=True, slots=True)
class PluginManifest:
    schema_version: int
    plugin_id: str
    name: str
    version: str
    api_version: str
    entrypoint_path: str
    entrypoint_callable: str
    description: str = ""
    default_enabled: bool = False
    permissions: frozenset[PluginPermission] = frozenset()
    dependencies: tuple[PluginDependency, ...] = ()
    settings: Mapping[str, object] = field(default_factory=dict)
    contributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", freeze_mapping(self.settings))
        object.__setattr__(self, "contributes", freeze_mapping(self.contributes))


@dataclass(frozen=True, slots=True)
class PluginEvent:
    event_type: str
    payload: Mapping[str, object] = field(default_factory=dict)
    character_id: str = ""
    occurred_at: int = 0
    event_id: str = ""
    source_plugin_id: str = ""
    durable: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", clean_identifier(self.event_type, 120))
        object.__setattr__(self, "character_id", clean_identifier(self.character_id, 80))
        object.__setattr__(self, "source_plugin_id", clean_identifier(self.source_plugin_id, 80))
        object.__setattr__(self, "event_id", clean_identifier(self.event_id, 120) or uuid4().hex)
        object.__setattr__(self, "occurred_at", max(0, int(self.occurred_at or 0)))
        object.__setattr__(self, "payload", freeze_mapping(self.payload))

    def to_public_dict(self) -> dict[str, object]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "character_id": self.character_id,
            "occurred_at": self.occurred_at,
            "source_plugin_id": self.source_plugin_id,
            "durable": self.durable,
            "payload": thaw_value(self.payload),
        }


@dataclass(frozen=True, slots=True)
class HostCommandProposal:
    command_type: str
    payload: Mapping[str, object] = field(default_factory=dict)
    requires_confirmation: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "command_type", clean_identifier(self.command_type, 100))
        object.__setattr__(self, "payload", freeze_mapping(self.payload))


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action_id: str
    character_id: str
    now: int = 0
    payload: Mapping[str, object] = field(default_factory=dict)
    state_snapshot: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", clean_identifier(self.action_id, 100))
        object.__setattr__(self, "character_id", clean_identifier(self.character_id, 80))
        object.__setattr__(self, "now", max(0, int(self.now or 0)))
        object.__setattr__(self, "payload", freeze_mapping(self.payload))
        object.__setattr__(self, "state_snapshot", freeze_mapping(self.state_snapshot))


@dataclass(frozen=True, slots=True)
class ActionResult:
    speech: str = ""
    motion: str = "Default"
    payload: Mapping[str, object] = field(default_factory=dict)
    events: tuple[PluginEvent, ...] = ()
    command_proposals: tuple[HostCommandProposal, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "speech", clean_text(self.speech, 240))
        object.__setattr__(self, "motion", clean_identifier(self.motion, 80) or "Default")
        object.__setattr__(self, "payload", freeze_mapping(self.payload))
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "command_proposals", tuple(self.command_proposals))


@dataclass(frozen=True, slots=True)
class SkillRequest:
    skill_id: str
    character_id: str
    now: int = 0
    payload: Mapping[str, object] = field(default_factory=dict)
    state_snapshot: Mapping[str, object] = field(default_factory=dict)
    user_confirmed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_id", clean_identifier(self.skill_id, 100))
        object.__setattr__(self, "character_id", clean_identifier(self.character_id, 80))
        object.__setattr__(self, "now", max(0, int(self.now or 0)))
        object.__setattr__(self, "payload", freeze_mapping(self.payload))
        object.__setattr__(self, "state_snapshot", freeze_mapping(self.state_snapshot))


@dataclass(frozen=True, slots=True)
class SkillResult:
    speech: str = ""
    motion: str = "Default"
    payload: Mapping[str, object] = field(default_factory=dict)
    events: tuple[PluginEvent, ...] = ()
    command_proposals: tuple[HostCommandProposal, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "speech", clean_text(self.speech, 240))
        object.__setattr__(self, "motion", clean_identifier(self.motion, 80) or "Default")
        object.__setattr__(self, "payload", freeze_mapping(self.payload))
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "command_proposals", tuple(self.command_proposals))


@dataclass(frozen=True, slots=True)
class ContextRequest:
    character_id: str
    query: str = ""
    now: int = 0
    state_snapshot: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "character_id", clean_identifier(self.character_id, 80))
        object.__setattr__(self, "query", clean_text(self.query, 500))
        object.__setattr__(self, "now", max(0, int(self.now or 0)))
        object.__setattr__(self, "state_snapshot", freeze_mapping(self.state_snapshot))


@dataclass(frozen=True, slots=True)
class UiPanelRequest:
    character_id: str
    state_snapshot: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "character_id", clean_identifier(self.character_id, 80))
        object.__setattr__(self, "state_snapshot", freeze_mapping(self.state_snapshot))


ActionHandler: TypeAlias = Callable[[ActionRequest], ActionResult]
SkillHandler: TypeAlias = Callable[[SkillRequest], SkillResult]
ContextProvider: TypeAlias = Callable[[ContextRequest], Mapping[str, object]]
UiPanelViewModelProvider: TypeAlias = Callable[[UiPanelRequest], Mapping[str, object]]
MemoryRuleHandler: TypeAlias = Callable[[PluginEvent], Sequence["MemoryProposal"]]
EventListener: TypeAlias = Callable[[PluginEvent], object]


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    action_id: str
    label: str
    handler: ActionHandler
    description: str = ""
    order: int = 100


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    skill_id: str
    title: str
    description: str
    handler: SkillHandler
    requires_confirmation: bool = True
    input_schema: Mapping[str, object] = field(default_factory=dict)
    order: int = 100

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_schema", freeze_mapping(self.input_schema))


@dataclass(frozen=True, slots=True)
class ContextProviderDefinition:
    provider_id: str
    provider: ContextProvider
    order: int = 100


@dataclass(frozen=True, slots=True)
class MemoryProposal:
    proposal_id: str
    kind: str
    title: str
    summary: str
    source: str
    source_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    importance: float = 0.7
    relationship_delta: float = 0.0
    pinned: bool = False
    requires_user_confirmation: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposal_id", clean_identifier(self.proposal_id, 120))
        object.__setattr__(self, "kind", clean_text(self.kind, 40))
        object.__setattr__(self, "title", clean_text(self.title, 60))
        object.__setattr__(self, "summary", clean_text(self.summary, 240))
        object.__setattr__(self, "source", clean_identifier(self.source, 100))
        object.__setattr__(self, "source_ids", tuple(clean_identifier(item, 120) for item in self.source_ids if item))
        object.__setattr__(self, "tags", tuple(clean_text(item, 32) for item in self.tags if item))
        object.__setattr__(self, "importance", max(0.0, min(1.0, float(self.importance))))
        object.__setattr__(
            self,
            "relationship_delta",
            max(-1.0, min(1.0, float(self.relationship_delta))),
        )
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))

    def validate(self) -> None:
        if not all((self.proposal_id, self.kind, self.title, self.summary, self.source)):
            raise ValueError("memory proposal requires id, kind, title, summary, and source")
        if bool(self.metadata.get("contains_screen_content", False)):
            raise ValueError("raw screen content cannot enter long-term memory")
        forbidden_keys = {"screenshot", "window_title", "clipboard", "raw_screen", "code_text"}
        if forbidden_keys.intersection(str(key).lower() for key in self.metadata):
            raise ValueError("raw screen content cannot enter long-term memory")


@dataclass(frozen=True, slots=True)
class MemoryRuleDefinition:
    rule_id: str
    handler: MemoryRuleHandler
    order: int = 100


@dataclass(frozen=True, slots=True)
class UiPanelDefinition:
    panel_id: str
    title: str
    navigation_group: str
    view_model: UiPanelViewModelProvider
    order: int = 100
    description: str = ""


@dataclass(frozen=True, slots=True)
class ServiceDefinition:
    service_id: str
    version: str
    description: str
    required_methods: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "service_id", clean_identifier(self.service_id, 100))
        object.__setattr__(self, "version", clean_identifier(self.version, 40))
        object.__setattr__(self, "description", clean_text(self.description, 300))
        object.__setattr__(
            self,
            "required_methods",
            tuple(clean_identifier(item, 80) for item in self.required_methods if item),
        )


@dataclass(frozen=True, slots=True)
class ServiceProviderDefinition:
    provider_id: str
    service_id: str
    provider: object
    priority: int = 0
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", clean_identifier(self.provider_id, 120))
        object.__setattr__(self, "service_id", clean_identifier(self.service_id, 100))
        object.__setattr__(self, "description", clean_text(self.description, 300))


@dataclass(frozen=True, slots=True)
class ContributionFailure:
    plugin_id: str
    contribution_id: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class EventDispatchReport:
    results: tuple[object, ...] = ()
    failures: tuple[ContributionFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class ContextAssembly:
    sections: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    failures: tuple[ContributionFailure, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "sections", freeze_mapping(self.sections))


@dataclass(frozen=True, slots=True)
class MemoryProposalReport:
    proposals: tuple[MemoryProposal, ...] = ()
    failures: tuple[ContributionFailure, ...] = ()
    rejected_proposal_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PluginStatus:
    plugin_id: str
    state: str
    version: str = ""
    message: str = ""
    loaded_order: int = -1


def clean_text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    normalized = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value)
    return " ".join(normalized.strip().split())[:limit]


def clean_identifier(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return clean_text(value, limit)


def freeze_mapping(value: Mapping[str, object] | None) -> Mapping[str, object]:
    source = value or {}
    return MappingProxyType({str(key): freeze_value(item) for key, item in source.items()})


def freeze_value(value: object) -> object:
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    if isinstance(value, tuple):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, list):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(freeze_value(item) for item in value)
    return value


def thaw_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_value(item) for item in value]
    if isinstance(value, frozenset):
        return [thaw_value(item) for item in sorted(value, key=str)]
    return value
