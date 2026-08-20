from __future__ import annotations

"""Reversible, permission-aware plugin runtime for E-Moti.

The runtime borrows the useful mechanics behind an "everything can be a
plugin" architecture while preserving E-Moti's current authority boundaries:
plugins register contributions and return typed proposals; the host owns game
state, persistence, UI placement, credentials, and external side effects.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import sys
import types
from typing import Any, Generic, TypeVar

from .plugin_api import (
    PLUGIN_API_VERSION,
    SAFE_PLUGIN_PERMISSIONS,
    ActionDefinition,
    ActionRequest,
    ActionResult,
    ContextAssembly,
    ContextProviderDefinition,
    ContextRequest,
    ContributionFailure,
    EventDispatchReport,
    MemoryProposal,
    MemoryProposalReport,
    MemoryRuleDefinition,
    PluginEvent,
    PluginManifest,
    PluginPermission,
    PluginStatus,
    SkillDefinition,
    SkillRequest,
    SkillResult,
    ServiceDefinition,
    ServiceProviderDefinition,
    UiPanelDefinition,
    UiPanelRequest,
    freeze_mapping,
    thaw_value,
)
from .plugin_manifest import PluginCandidate


class PluginRuntimeError(RuntimeError):
    pass


class PluginLoadError(PluginRuntimeError):
    pass


class PluginPermissionError(PluginRuntimeError):
    pass


class PluginDependencyError(PluginRuntimeError):
    pass


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class _OwnedContribution(Generic[T]):
    owner_id: str
    contribution_id: str
    value: T
    order: int
    sequence: int


class RegistrationHandle:
    def __init__(self, dispose: Callable[[], None]) -> None:
        self._dispose = dispose
        self._disposed = False

    @property
    def disposed(self) -> bool:
        return self._disposed

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        self._dispose()


class _EffectScope:
    def __init__(self) -> None:
        self._handles: list[RegistrationHandle] = []
        self._disposed = False

    def add(self, handle_or_callback: RegistrationHandle | Callable[[], None]) -> RegistrationHandle:
        if isinstance(handle_or_callback, RegistrationHandle):
            handle = handle_or_callback
        else:
            handle = RegistrationHandle(handle_or_callback)
        if self._disposed:
            handle.dispose()
        else:
            self._handles.append(handle)
        return handle

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        for handle in reversed(self._handles):
            try:
                handle.dispose()
            except Exception:
                # Unload should continue even if one plugin cleanup is faulty.
                pass
        self._handles.clear()


class _ContributionRegistry(Generic[T]):
    def __init__(self) -> None:
        self._items: dict[str, _OwnedContribution[T]] = {}
        self._sequence = 0

    def register(
        self,
        *,
        owner_id: str,
        contribution_id: str,
        value: T,
        order: int = 100,
    ) -> RegistrationHandle:
        key = str(contribution_id).strip()
        if not key:
            raise PluginLoadError("plugin contribution id cannot be empty")
        existing = self._items.get(key)
        if existing is not None:
            raise PluginLoadError(
                f"plugin contribution id {key!r} is already owned by {existing.owner_id}"
            )
        self._sequence += 1
        record = _OwnedContribution(owner_id, key, value, int(order), self._sequence)
        self._items[key] = record

        def dispose() -> None:
            if self._items.get(key) is record:
                self._items.pop(key, None)

        return RegistrationHandle(dispose)

    def get(self, contribution_id: str) -> _OwnedContribution[T] | None:
        return self._items.get(contribution_id)

    def ordered(self) -> tuple[_OwnedContribution[T], ...]:
        return tuple(sorted(self._items.values(), key=lambda row: (row.order, row.sequence, row.contribution_id)))


@dataclass(frozen=True, slots=True)
class _EventListenerRecord:
    owner_id: str
    event_pattern: str
    callback: Callable[[PluginEvent], object]
    priority: int
    sequence: int
    listener_id: str


class _EventBus:
    def __init__(self) -> None:
        self._listeners: list[_EventListenerRecord] = []
        self._sequence = 0

    def on(
        self,
        *,
        owner_id: str,
        event_pattern: str,
        callback: Callable[[PluginEvent], object],
        priority: int = 0,
    ) -> RegistrationHandle:
        pattern = str(event_pattern).strip()
        if not pattern:
            raise PluginLoadError("event pattern cannot be empty")
        self._sequence += 1
        record = _EventListenerRecord(
            owner_id=owner_id,
            event_pattern=pattern,
            callback=callback,
            priority=int(priority),
            sequence=self._sequence,
            listener_id=f"{owner_id}:{pattern}:{self._sequence}",
        )
        self._listeners.append(record)

        def dispose() -> None:
            try:
                self._listeners.remove(record)
            except ValueError:
                pass

        return RegistrationHandle(dispose)

    def emit(self, event: PluginEvent) -> EventDispatchReport:
        listeners = sorted(
            (row for row in self._listeners if _event_matches(row.event_pattern, event.event_type)),
            key=lambda row: (-row.priority, row.sequence),
        )
        results: list[object] = []
        failures: list[ContributionFailure] = []
        for row in listeners:
            try:
                result = row.callback(event)
            except Exception as exc:
                failures.append(_failure(row.owner_id, row.listener_id, exc))
                continue
            if result is not None:
                results.append(result)
        return EventDispatchReport(tuple(results), tuple(failures))


@dataclass(slots=True)
class PluginDataStore:
    path: Path
    max_bytes: int = 256 * 1024

    def snapshot(self) -> Mapping[str, object]:
        if not self.path.exists():
            return freeze_mapping({})
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return freeze_mapping({})
        return freeze_mapping(payload if isinstance(payload, Mapping) else {})

    def get(self, key: str, default: object = None) -> object:
        return self.snapshot().get(str(key), default)

    def set(self, key: str, value: object) -> None:
        payload = dict(self.snapshot())
        payload[str(key)] = value
        self._save(payload)

    def delete(self, key: str) -> None:
        payload = dict(self.snapshot())
        payload.pop(str(key), None)
        self._save(payload)

    def clear(self) -> None:
        self._save({})

    def _save(self, payload: Mapping[str, object]) -> None:
        try:
            encoded = json.dumps(thaw_value(payload), ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise PluginLoadError("plugin local storage only accepts JSON-compatible values") from exc
        if len(encoded) > self.max_bytes:
            raise PluginLoadError(f"plugin local storage exceeds {self.max_bytes} bytes")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(self.path)


@dataclass(slots=True)
class _LoadedPlugin:
    candidate: PluginCandidate
    scope: _EffectScope
    module_names: tuple[str, ...]
    load_order: int


class PluginContext:
    """Plugin-facing capability surface.

    It intentionally has no setter for game state, inventory, relationships,
    saves, credentials, or raw screen data.
    """

    def __init__(
        self,
        *,
        runtime: "PluginRuntime",
        manifest: PluginManifest,
        scope: _EffectScope,
    ) -> None:
        self._runtime = runtime
        self.manifest = manifest
        self.plugin_id = manifest.plugin_id
        merged_settings = dict(manifest.settings)
        merged_settings.update(runtime._settings_overrides.get(manifest.plugin_id, {}))
        self.settings = freeze_mapping(merged_settings)
        self._scope = scope

    @property
    def storage(self) -> PluginDataStore:
        self.require(PluginPermission.STORAGE_LOCAL)
        return self._runtime.plugin_storage(self.plugin_id)

    def require(self, permission: PluginPermission | str) -> None:
        self._runtime.require_permission(self.manifest, permission)

    def on(
        self,
        event_pattern: str,
        callback: Callable[[PluginEvent], object],
        *,
        priority: int = 0,
    ) -> RegistrationHandle:
        self.require(PluginPermission.EVENTS_SUBSCRIBE)
        return self._scope.add(
            self._runtime._events.on(
                owner_id=self.plugin_id,
                event_pattern=event_pattern,
                callback=callback,
                priority=priority,
            )
        )

    def publish(
        self,
        event_type: str,
        *,
        payload: Mapping[str, object] | None = None,
        character_id: str = "",
        occurred_at: int = 0,
        durable: bool = False,
    ) -> EventDispatchReport:
        self.require(PluginPermission.EVENTS_PUBLISH)
        if not event_type.startswith(f"plugin.{self.plugin_id}."):
            raise PluginPermissionError(
                f"plugin {self.plugin_id} may only publish events under plugin.{self.plugin_id}.*"
            )
        return self._runtime.emit(
            PluginEvent(
                event_type=event_type,
                payload=payload or {},
                character_id=character_id,
                occurred_at=occurred_at,
                source_plugin_id=self.plugin_id,
                durable=durable,
            )
        )

    def register_action(self, definition: ActionDefinition) -> RegistrationHandle:
        self.require(PluginPermission.ACTIONS_REGISTER)
        _validate_action_definition(definition)
        return self._scope.add(
            self._runtime._actions.register(
                owner_id=self.plugin_id,
                contribution_id=definition.action_id,
                value=definition,
                order=definition.order,
            )
        )

    def register_skill(self, definition: SkillDefinition) -> RegistrationHandle:
        self.require(PluginPermission.SKILLS_REGISTER)
        _validate_skill_definition(definition)
        return self._scope.add(
            self._runtime._skills.register(
                owner_id=self.plugin_id,
                contribution_id=definition.skill_id,
                value=definition,
                order=definition.order,
            )
        )

    def register_context_provider(self, definition: ContextProviderDefinition) -> RegistrationHandle:
        self.require(PluginPermission.CONTEXT_PROVIDE)
        if not definition.provider_id.strip() or not callable(definition.provider):
            raise PluginLoadError("context provider requires an id and callable")
        contribution_id = f"{self.plugin_id}:{definition.provider_id}"
        return self._scope.add(
            self._runtime._context_providers.register(
                owner_id=self.plugin_id,
                contribution_id=contribution_id,
                value=definition,
                order=definition.order,
            )
        )

    def register_memory_rule(self, definition: MemoryRuleDefinition) -> RegistrationHandle:
        self.require(PluginPermission.MEMORY_PROPOSE)
        if not definition.rule_id.strip() or not callable(definition.handler):
            raise PluginLoadError("memory rule requires an id and callable")
        contribution_id = f"{self.plugin_id}:{definition.rule_id}"
        return self._scope.add(
            self._runtime._memory_rules.register(
                owner_id=self.plugin_id,
                contribution_id=contribution_id,
                value=definition,
                order=definition.order,
            )
        )

    def define_service(self, definition: ServiceDefinition) -> RegistrationHandle:
        self.require(PluginPermission.SERVICES_REGISTER)
        if (
            not definition.service_id.strip()
            or not definition.version.strip()
            or not definition.description.strip()
        ):
            raise PluginLoadError("service definition requires id, version, and description")
        return self._scope.add(
            self._runtime._service_definitions.register(
                owner_id=self.plugin_id,
                contribution_id=definition.service_id,
                value=definition,
                order=100,
            )
        )

    def register_service_provider(
        self, definition: ServiceProviderDefinition
    ) -> RegistrationHandle:
        self.require(PluginPermission.SERVICES_REGISTER)
        if not definition.provider_id.strip() or not definition.service_id.strip():
            raise PluginLoadError("service provider requires provider_id and service_id")
        service_record = self._runtime._service_definitions.get(definition.service_id)
        if service_record is None:
            raise PluginLoadError(
                f"service definition was not found: {definition.service_id}"
            )
        missing = [
            method
            for method in service_record.value.required_methods
            if not callable(getattr(definition.provider, method, None))
        ]
        if missing:
            raise PluginLoadError(
                f"service provider {definition.provider_id} does not implement: {', '.join(missing)}"
            )
        return self._scope.add(
            self._runtime._service_providers.register(
                owner_id=self.plugin_id,
                contribution_id=definition.provider_id,
                value=definition,
                order=-int(definition.priority),
            )
        )

    def register_ui_panel(self, definition: UiPanelDefinition) -> RegistrationHandle:
        self.require(PluginPermission.UI_REGISTER)
        if not definition.panel_id.strip() or not definition.title.strip() or not callable(definition.view_model):
            raise PluginLoadError("UI panel requires id, title, and view-model provider")
        return self._scope.add(
            self._runtime._ui_panels.register(
                owner_id=self.plugin_id,
                contribution_id=definition.panel_id,
                value=definition,
                order=definition.order,
            )
        )


class PluginRuntime:
    def __init__(
        self,
        *,
        data_root: Path | str,
        permission_grants: Mapping[str, Iterable[PluginPermission | str]] | None = None,
        settings_overrides: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        self.data_root = Path(data_root)
        self._permission_grants = _normalize_grants(permission_grants or {})
        self._settings_overrides = {
            str(plugin_id): dict(payload)
            for plugin_id, payload in (settings_overrides or {}).items()
        }
        self._events = _EventBus()
        self._actions: _ContributionRegistry[ActionDefinition] = _ContributionRegistry()
        self._skills: _ContributionRegistry[SkillDefinition] = _ContributionRegistry()
        self._context_providers: _ContributionRegistry[ContextProviderDefinition] = _ContributionRegistry()
        self._memory_rules: _ContributionRegistry[MemoryRuleDefinition] = _ContributionRegistry()
        self._ui_panels: _ContributionRegistry[UiPanelDefinition] = _ContributionRegistry()
        self._service_definitions: _ContributionRegistry[ServiceDefinition] = _ContributionRegistry()
        self._service_providers: _ContributionRegistry[ServiceProviderDefinition] = _ContributionRegistry()
        self._loaded: dict[str, _LoadedPlugin] = {}
        self._statuses: dict[str, PluginStatus] = {}
        self._candidate_cache: dict[str, PluginCandidate] = {}
        self._load_counter = 0

    @classmethod
    def from_configuration(
        cls,
        *,
        data_root: Path | str,
        configuration: object,
    ) -> "PluginRuntime":
        from .plugin_configuration import PluginRuntimeConfiguration

        if not isinstance(configuration, PluginRuntimeConfiguration):
            raise TypeError("configuration must be PluginRuntimeConfiguration")
        return cls(
            data_root=data_root,
            permission_grants=configuration.grants_for_runtime(),
            settings_overrides=configuration.settings_for_runtime(),
        )

    @property
    def loaded_plugin_ids(self) -> tuple[str, ...]:
        return tuple(
            row.candidate.manifest.plugin_id
            for row in sorted(self._loaded.values(), key=lambda item: item.load_order)
        )

    def status(self, plugin_id: str) -> PluginStatus:
        return self._statuses.get(plugin_id, PluginStatus(plugin_id, "not_found"))

    def plugin_storage(self, plugin_id: str) -> PluginDataStore:
        safe_id = hashlib.sha256(plugin_id.encode("utf-8")).hexdigest()[:20]
        return PluginDataStore(self.data_root / safe_id / "state.json")

    def require_permission(
        self,
        manifest: PluginManifest,
        permission: PluginPermission | str,
    ) -> None:
        try:
            normalized = permission if isinstance(permission, PluginPermission) else PluginPermission(str(permission))
        except ValueError as exc:
            raise PluginPermissionError(f"unknown plugin permission: {permission}") from exc
        if normalized not in manifest.permissions:
            raise PluginPermissionError(
                f"permission {normalized.value} was not declared by plugin {manifest.plugin_id}"
            )
        if normalized in SAFE_PLUGIN_PERMISSIONS:
            return
        if normalized not in self._permission_grants.get(manifest.plugin_id, frozenset()):
            raise PluginPermissionError(
                f"permission {normalized.value} was not granted to plugin {manifest.plugin_id}"
            )

    def load(self, candidate: PluginCandidate) -> PluginStatus:
        manifest = candidate.manifest
        plugin_id = manifest.plugin_id
        if plugin_id in self._loaded:
            return self.status(plugin_id)
        if manifest.api_version.split(".", 1)[0] != PLUGIN_API_VERSION.split(".", 1)[0]:
            error = PluginLoadError(
                f"plugin {plugin_id} requires API version {manifest.api_version}; "
                f"host provides {PLUGIN_API_VERSION}"
            )
            self._statuses[plugin_id] = PluginStatus(plugin_id, "failed", manifest.version, str(error))
            raise error
        missing = [
            dep.plugin_id
            for dep in manifest.dependencies
            if not dep.optional and dep.plugin_id not in self._loaded
        ]
        if missing:
            raise PluginDependencyError(
                f"plugin {plugin_id} requires loaded dependencies: {', '.join(missing)}"
            )

        scope = _EffectScope()
        module_names: tuple[str, ...] = ()
        try:
            module, module_names = _load_plugin_module(candidate)
            activation = getattr(module, manifest.entrypoint_callable, None)
            if not callable(activation):
                raise PluginLoadError(
                    f"plugin entrypoint callable {manifest.entrypoint_callable!r} was not found"
                )
            context = PluginContext(runtime=self, manifest=manifest, scope=scope)
            cleanup = activation(context)
            if cleanup is not None:
                if callable(cleanup):
                    scope.add(cleanup)
                elif callable(getattr(cleanup, "dispose", None)):
                    scope.add(cleanup.dispose)
                elif callable(getattr(cleanup, "close", None)):
                    scope.add(cleanup.close)
                else:
                    raise PluginLoadError("plugin activation must return None, a cleanup callable, or a disposable")
        except PluginPermissionError:
            scope.dispose()
            _remove_modules(module_names)
            self._statuses[plugin_id] = PluginStatus(plugin_id, "failed", manifest.version, "permission denied")
            raise
        except Exception as exc:
            scope.dispose()
            _remove_modules(module_names)
            error = exc if isinstance(exc, PluginLoadError) else PluginLoadError(
                f"plugin {plugin_id} activation failed: {exc}"
            )
            self._statuses[plugin_id] = PluginStatus(plugin_id, "failed", manifest.version, str(error))
            raise error from exc

        self._load_counter += 1
        self._loaded[plugin_id] = _LoadedPlugin(candidate, scope, module_names, self._load_counter)
        self._candidate_cache[plugin_id] = candidate
        status = PluginStatus(plugin_id, "loaded", manifest.version, loaded_order=self._load_counter)
        self._statuses[plugin_id] = status
        self.emit(
            PluginEvent(
                event_type="plugin.runtime.loaded",
                source_plugin_id="host",
                payload={"plugin_id": plugin_id, "version": manifest.version},
            )
        )
        return status

    def load_all(
        self,
        candidates: Iterable[PluginCandidate],
        *,
        enabled_ids: set[str] | None = None,
    ) -> tuple[str, ...]:
        by_id = {candidate.manifest.plugin_id: candidate for candidate in candidates}
        selected = (
            {plugin_id for plugin_id in enabled_ids}
            if enabled_ids is not None
            else {
                plugin_id
                for plugin_id, candidate in by_id.items()
                if candidate.manifest.default_enabled
            }
        )
        for plugin_id in selected:
            if plugin_id not in by_id:
                raise PluginDependencyError(f"enabled plugin was not discovered: {plugin_id}")
        required = set(selected)

        def include_dependencies(plugin_id: str) -> None:
            candidate = by_id[plugin_id]
            for dep in candidate.manifest.dependencies:
                if dep.optional:
                    continue
                if dep.plugin_id not in by_id:
                    raise PluginDependencyError(
                        f"plugin {plugin_id} requires missing dependency {dep.plugin_id}"
                    )
                if dep.plugin_id not in required:
                    required.add(dep.plugin_id)
                    include_dependencies(dep.plugin_id)

        for plugin_id in tuple(selected):
            include_dependencies(plugin_id)

        order: list[str] = []
        visiting: list[str] = []
        visited: set[str] = set()

        def visit(plugin_id: str) -> None:
            if plugin_id in visited:
                return
            if plugin_id in visiting:
                cycle = visiting[visiting.index(plugin_id) :] + [plugin_id]
                raise PluginDependencyError(f"plugin dependency cycle: {' -> '.join(cycle)}")
            visiting.append(plugin_id)
            for dep in by_id[plugin_id].manifest.dependencies:
                if dep.plugin_id in required:
                    visit(dep.plugin_id)
            visiting.pop()
            visited.add(plugin_id)
            order.append(plugin_id)

        for plugin_id in sorted(required):
            visit(plugin_id)

        loaded_here: list[str] = []
        try:
            for plugin_id in order:
                if plugin_id in self._loaded:
                    continue
                self.load(by_id[plugin_id])
                loaded_here.append(plugin_id)
        except Exception:
            for plugin_id in reversed(loaded_here):
                self.unload(plugin_id, force=True)
            raise
        return tuple(order)

    def load_configured(
        self,
        candidates: Iterable[PluginCandidate],
        *,
        configuration: object,
    ) -> tuple[str, ...]:
        from .plugin_configuration import PluginRuntimeConfiguration

        if not isinstance(configuration, PluginRuntimeConfiguration):
            raise TypeError("configuration must be PluginRuntimeConfiguration")
        rows = tuple(candidates)
        return self.load_all(rows, enabled_ids=configuration.effective_enabled(rows))

    def unload(self, plugin_id: str, *, force: bool = False) -> None:
        loaded = self._loaded.get(plugin_id)
        if loaded is None:
            return
        dependents = [
            other_id
            for other_id, row in self._loaded.items()
            if other_id != plugin_id
            and any(
                not dep.optional and dep.plugin_id == plugin_id
                for dep in row.candidate.manifest.dependencies
            )
        ]
        if dependents and not force:
            raise PluginDependencyError(
                f"cannot unload {plugin_id}; loaded dependents: {', '.join(sorted(dependents))}"
            )
        if force:
            for dependent in sorted(
                dependents,
                key=lambda item: self._loaded[item].load_order,
                reverse=True,
            ):
                self.unload(dependent, force=True)
        loaded.scope.dispose()
        _remove_modules(loaded.module_names)
        self._loaded.pop(plugin_id, None)
        self._statuses[plugin_id] = PluginStatus(
            plugin_id,
            "unloaded",
            loaded.candidate.manifest.version,
            loaded_order=loaded.load_order,
        )

    def reload(self, plugin_id: str) -> PluginStatus:
        candidate = self._candidate_cache.get(plugin_id)
        if candidate is None:
            raise PluginLoadError(f"plugin {plugin_id} has no cached candidate")
        self.unload(plugin_id)
        return self.load(candidate)

    def shutdown(self) -> None:
        for plugin_id in reversed(self.loaded_plugin_ids):
            self.unload(plugin_id, force=True)

    def emit(self, event: PluginEvent) -> EventDispatchReport:
        return self._events.emit(event)

    def make_event(
        self,
        event_type: str,
        *,
        character_id: str = "",
        payload: Mapping[str, object] | None = None,
        occurred_at: int = 0,
        durable: bool = False,
    ) -> PluginEvent:
        return PluginEvent(
            event_type=event_type,
            character_id=character_id,
            payload=payload or {},
            occurred_at=occurred_at,
            source_plugin_id="host",
            durable=durable,
        )

    def list_actions(self) -> tuple[ActionDefinition, ...]:
        return tuple(row.value for row in self._actions.ordered())

    def action_owner(self, action_id: str) -> str | None:
        record = self._actions.get(action_id)
        return record.owner_id if record is not None else None

    def execute_action(self, request: ActionRequest) -> ActionResult:
        record = self._actions.get(request.action_id)
        if record is None:
            raise PluginLoadError(f"plugin action was not found: {request.action_id}")
        try:
            result = record.value.handler(request)
        except Exception as exc:
            raise PluginLoadError(
                f"plugin action {request.action_id} failed; request snapshots are read-only: {exc}"
            ) from exc
        if not isinstance(result, ActionResult):
            raise PluginLoadError(f"plugin action {request.action_id} returned an invalid result")
        return _normalize_action_result(result, owner_id=record.owner_id)

    def list_skills(self) -> tuple[SkillDefinition, ...]:
        return tuple(row.value for row in self._skills.ordered())

    def skill_owner(self, skill_id: str) -> str | None:
        record = self._skills.get(skill_id)
        return record.owner_id if record is not None else None

    def execute_skill(self, request: SkillRequest) -> SkillResult:
        record = self._skills.get(request.skill_id)
        if record is None:
            raise PluginLoadError(f"plugin skill was not found: {request.skill_id}")
        if record.value.requires_confirmation and not request.user_confirmed:
            raise PluginPermissionError(
                f"plugin skill {request.skill_id} requires current user confirmation"
            )
        try:
            result = record.value.handler(request)
        except Exception as exc:
            raise PluginLoadError(
                f"plugin skill {request.skill_id} failed; request snapshots are read-only: {exc}"
            ) from exc
        if not isinstance(result, SkillResult):
            raise PluginLoadError(f"plugin skill {request.skill_id} returned an invalid result")
        return _normalize_skill_result(result, owner_id=record.owner_id)

    def build_context(
        self,
        *,
        character_id: str,
        query: str = "",
        now: int = 0,
        state_snapshot: Mapping[str, object] | None = None,
    ) -> ContextAssembly:
        request = ContextRequest(
            character_id=character_id,
            query=query,
            now=now,
            state_snapshot=state_snapshot or {},
        )
        sections: dict[str, Mapping[str, object]] = {}
        failures: list[ContributionFailure] = []
        for record in self._context_providers.ordered():
            try:
                payload = record.value.provider(request)
                if not isinstance(payload, Mapping):
                    raise TypeError("context provider must return a mapping")
                sections[record.contribution_id] = freeze_mapping(payload)
            except Exception as exc:
                failures.append(_failure(record.owner_id, record.contribution_id, exc))
        return ContextAssembly(sections, tuple(failures))

    def collect_memory_proposals(self, event: PluginEvent) -> MemoryProposalReport:
        proposals: list[MemoryProposal] = []
        failures: list[ContributionFailure] = []
        rejected: list[str] = []
        seen: set[str] = set()
        for record in self._memory_rules.ordered():
            try:
                rows = tuple(record.value.handler(event))
            except Exception as exc:
                failures.append(_failure(record.owner_id, record.contribution_id, exc))
                continue
            for index, proposal in enumerate(rows):
                if not isinstance(proposal, MemoryProposal):
                    failures.append(
                        _failure(
                            record.owner_id,
                            f"{record.contribution_id}[{index}]",
                            TypeError("memory rule must return MemoryProposal objects"),
                        )
                    )
                    continue
                try:
                    proposal.validate()
                except Exception as exc:
                    rejected.append(proposal.proposal_id or f"{record.contribution_id}[{index}]")
                    failures.append(_failure(record.owner_id, record.contribution_id, exc))
                    continue
                if proposal.proposal_id in seen:
                    continue
                seen.add(proposal.proposal_id)
                proposals.append(proposal)
        return MemoryProposalReport(tuple(proposals), tuple(failures), tuple(rejected))

    def list_service_definitions(self) -> tuple[ServiceDefinition, ...]:
        return tuple(row.value for row in self._service_definitions.ordered())

    def register_host_service_provider(
        self, definition: ServiceProviderDefinition
    ) -> RegistrationHandle:
        """Register a trusted host-owned provider beside plugin providers.

        The service definition must already be loaded. The returned handle
        reverses the registration during window or subsystem shutdown.
        """
        service_record = self._service_definitions.get(definition.service_id)
        if service_record is None:
            raise PluginLoadError(f"service definition was not found: {definition.service_id}")
        missing = [
            method
            for method in service_record.value.required_methods
            if not callable(getattr(definition.provider, method, None))
        ]
        if missing:
            raise PluginLoadError(
                f"service provider {definition.provider_id} does not implement: {', '.join(missing)}"
            )
        return self._service_providers.register(
            owner_id="host",
            contribution_id=definition.provider_id,
            value=definition,
            order=-int(definition.priority),
        )

    def list_service_providers(
        self, service_id: str | None = None
    ) -> tuple[ServiceProviderDefinition, ...]:
        rows = tuple(row.value for row in self._service_providers.ordered())
        if service_id is None:
            return rows
        return tuple(row for row in rows if row.service_id == service_id)

    def resolve_service(
        self, service_id: str, *, provider_id: str | None = None
    ) -> object:
        definition = self._service_definitions.get(service_id)
        if definition is None:
            raise PluginLoadError(f"service definition was not found: {service_id}")
        providers = [
            row
            for row in self._service_providers.ordered()
            if row.value.service_id == service_id
        ]
        if provider_id is not None:
            providers = [row for row in providers if row.value.provider_id == provider_id]
        if not providers:
            target = f" provider {provider_id}" if provider_id else ""
            raise PluginLoadError(f"service {service_id} has no registered{target}")
        return providers[0].value.provider

    def list_ui_panels(self) -> tuple[UiPanelDefinition, ...]:
        return tuple(row.value for row in self._ui_panels.ordered())

    def build_ui_panel_model(
        self,
        panel_id: str,
        *,
        character_id: str,
        state_snapshot: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        record = self._ui_panels.get(panel_id)
        if record is None:
            raise PluginLoadError(f"plugin UI panel was not found: {panel_id}")
        request = UiPanelRequest(character_id=character_id, state_snapshot=state_snapshot or {})
        try:
            payload = record.value.view_model(request)
        except Exception as exc:
            raise PluginLoadError(f"plugin UI panel {panel_id} failed: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise PluginLoadError(f"plugin UI panel {panel_id} must return a mapping")
        return freeze_mapping(payload)


def _load_plugin_module(candidate: PluginCandidate) -> tuple[types.ModuleType, tuple[str, ...]]:
    root = candidate.root
    entrypoint = (root / candidate.manifest.entrypoint_path).resolve()
    digest = hashlib.sha256(
        f"{candidate.manifest.plugin_id}|{root}|{candidate.manifest.version}".encode("utf-8")
    ).hexdigest()[:16]
    package_name = f"_emoti_plugin_{digest}"
    created: list[str] = []

    package = types.ModuleType(package_name)
    package.__path__ = [str(root)]  # type: ignore[attr-defined]
    package.__package__ = package_name
    sys.modules[package_name] = package
    created.append(package_name)

    relative = entrypoint.relative_to(root)
    parts = list(relative.with_suffix("").parts)
    parent_name = package_name
    parent_path = root
    for part in parts[:-1]:
        parent_name = f"{parent_name}.{part}"
        parent_path = parent_path / part
        parent = types.ModuleType(parent_name)
        parent.__path__ = [str(parent_path)]  # type: ignore[attr-defined]
        parent.__package__ = parent_name
        sys.modules[parent_name] = parent
        created.append(parent_name)

    module_name = f"{parent_name}.{parts[-1]}"
    module = types.ModuleType(module_name)
    module.__file__ = str(entrypoint)
    module.__package__ = parent_name
    sys.modules[module_name] = module
    created.append(module_name)
    try:
        source = entrypoint.read_text(encoding="utf-8-sig")
        code = compile(source, str(entrypoint), "exec")
        exec(code, module.__dict__)
    except Exception:
        _remove_modules(tuple(created))
        raise
    return module, tuple(created)


def _remove_modules(names: tuple[str, ...]) -> None:
    for name in reversed(names):
        sys.modules.pop(name, None)


def _event_matches(pattern: str, event_type: str) -> bool:
    if pattern == "*" or pattern == event_type:
        return True
    if pattern.endswith(".*"):
        return event_type.startswith(pattern[:-1])
    return False


def _normalize_grants(
    value: Mapping[str, Iterable[PluginPermission | str]],
) -> dict[str, frozenset[PluginPermission]]:
    result: dict[str, frozenset[PluginPermission]] = {}
    for plugin_id, grants in value.items():
        normalized: set[PluginPermission] = set()
        for grant in grants:
            normalized.add(grant if isinstance(grant, PluginPermission) else PluginPermission(str(grant)))
        result[str(plugin_id)] = frozenset(normalized)
    return result


def _normalize_action_result(result: ActionResult, *, owner_id: str) -> ActionResult:
    events = tuple(
        event if event.source_plugin_id else replace(event, source_plugin_id=owner_id)
        for event in result.events
    )
    return replace(result, events=events)


def _normalize_skill_result(result: SkillResult, *, owner_id: str) -> SkillResult:
    events = tuple(
        event if event.source_plugin_id else replace(event, source_plugin_id=owner_id)
        for event in result.events
    )
    return replace(result, events=events)


def _validate_action_definition(definition: ActionDefinition) -> None:
    if not definition.action_id.strip() or not definition.label.strip() or not callable(definition.handler):
        raise PluginLoadError("action requires id, label, and handler")


def _validate_skill_definition(definition: SkillDefinition) -> None:
    if (
        not definition.skill_id.strip()
        or not definition.title.strip()
        or not definition.description.strip()
        or not callable(definition.handler)
    ):
        raise PluginLoadError("skill requires id, title, description, and handler")


def _failure(plugin_id: str, contribution_id: str, exc: Exception) -> ContributionFailure:
    return ContributionFailure(
        plugin_id=plugin_id,
        contribution_id=contribution_id,
        error_type=type(exc).__name__,
        message=str(exc)[:500],
    )
