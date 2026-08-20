from __future__ import annotations

"""High-level, fault-contained plugin subsystem for the desktop application."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .plugin_api import ActionRequest, ActionResult, SkillRequest, SkillResult
from .plugin_health import PluginHealthStore
from .plugin_host import PluginBootReport, PluginHost, PluginPaths
from .plugin_journal import PluginJournal
from .plugin_package import PluginInstallResult, PluginPackageManager
from .plugin_provider_adapters import register_host_capability_providers
from .plugin_runtime import PluginLoadError


@dataclass(frozen=True, slots=True)
class SafeExecutionResult:
    ok: bool
    plugin_id: str
    value: object | None = None
    message: str = ""
    quarantined: bool = False


class PluginSubsystem:
    def __init__(self, *, application_root: Path | str, user_data_root: Path | str) -> None:
        self.paths = PluginPaths.from_roots(application_root=application_root, user_data_root=user_data_root)
        self.host = PluginHost(self.paths)
        plugin_root = Path(user_data_root) / "plugins"
        self.health = PluginHealthStore(plugin_root / "health.json")
        self.journal = PluginJournal(plugin_root / "journal.jsonl")
        self.packages = PluginPackageManager(self.paths.installed_root)
        self._provider_handles: tuple[object, ...] = ()
        self._host_providers: dict[str, object] = {}

    @property
    def runtime(self):
        return self.host.runtime

    def start(self) -> PluginBootReport:
        report = self.host.start()
        for failure in report.failures:
            self.health.record_failure(failure.plugin_id, failure.message)
            self.journal.append("plugin.boot.failed", plugin_id=failure.plugin_id, payload=failure.to_dict())
        for plugin_id in report.loaded_plugin_ids:
            self.health.record_success(plugin_id)
            self.journal.append("plugin.loaded", plugin_id=plugin_id)
        return report

    def shutdown(self) -> None:
        for handle in self._provider_handles:
            dispose = getattr(handle, "dispose", None)
            if callable(dispose):
                dispose()
        self._provider_handles = ()
        self.host.shutdown()
        self.journal.append("plugin.runtime.shutdown")

    def bind_host_capabilities(self, **providers: object) -> None:
        self._host_providers = {key: value for key, value in providers.items() if value is not None}
        self._rebind_host_capabilities()

    def _rebind_host_capabilities(self) -> None:
        for handle in self._provider_handles:
            dispose = getattr(handle, "dispose", None)
            if callable(dispose):
                dispose()
        self._provider_handles = register_host_capability_providers(self.runtime, **self._host_providers)

    def reload_from_disk(self) -> PluginBootReport:
        report = self.host.reload_from_disk()
        self._rebind_host_capabilities()
        return report

    def execute_action(self, request: ActionRequest) -> SafeExecutionResult:
        owner = self.runtime.action_owner(request.action_id) or ""
        return self._execute(owner, "action", request.action_id, lambda: self.runtime.execute_action(request))

    def execute_skill(self, request: SkillRequest) -> SafeExecutionResult:
        owner = self.runtime.skill_owner(request.skill_id) or ""
        return self._execute(owner, "skill", request.skill_id, lambda: self.runtime.execute_skill(request))

    def install(self, archive: Path | str) -> PluginInstallResult:
        result = self.packages.install(archive)
        self.journal.append("plugin.install", plugin_id=result.plugin_id, payload=result.to_dict())
        if result.ok:
            self.reload_from_disk()
        return result

    def uninstall(self, plugin_id: str) -> PluginInstallResult:
        self.host.set_enabled(plugin_id, False)
        self.reload_from_disk()
        result = self.packages.uninstall(plugin_id)
        self.health.remove(plugin_id)
        self.journal.append("plugin.uninstall", plugin_id=plugin_id, payload=result.to_dict())
        if result.ok:
            self.reload_from_disk()
        return result

    def _execute(self, plugin_id: str, kind: str, contribution_id: str, callback: Callable[[], object]) -> SafeExecutionResult:
        if plugin_id and self.health.status(plugin_id).quarantined:
            return SafeExecutionResult(False, plugin_id, message="插件已隔离", quarantined=True)
        try:
            value = callback()
        except Exception as exc:
            status = self.health.record_failure(plugin_id or "unknown", exc)
            self.journal.append(
                f"plugin.{kind}.failed",
                plugin_id=plugin_id,
                payload={"contribution_id": contribution_id, "error_type": type(exc).__name__, "message": str(exc)},
            )
            if plugin_id and status.quarantined:
                self.runtime.unload(plugin_id, force=True)
            return SafeExecutionResult(False, plugin_id, message=str(exc)[:400], quarantined=status.quarantined)
        if plugin_id:
            self.health.record_success(plugin_id)
        self.journal.append(f"plugin.{kind}.completed", plugin_id=plugin_id, payload={"contribution_id": contribution_id})
        return SafeExecutionResult(True, plugin_id, value=value)
