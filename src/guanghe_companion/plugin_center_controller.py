from __future__ import annotations

"""Application-facing controller for Plugin Center operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .plugin_audit import audit_plugin
from .plugin_health import PluginHealthStatus
from .plugin_package import PluginInstallResult, build_plugin_archive
from .plugin_subsystem import PluginSubsystem


@dataclass(frozen=True, slots=True)
class PluginCenterOperation:
    ok: bool
    operation: str
    plugin_id: str = ""
    message: str = ""
    payload: Mapping[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "operation": self.operation, "plugin_id": self.plugin_id, "message": self.message, "payload": dict(self.payload or {})}


class PluginCenterController:
    def __init__(self, subsystem: PluginSubsystem, *, character_id_provider=None, state_snapshot_provider=None) -> None:
        self.subsystem = subsystem
        self.character_id_provider = character_id_provider or (lambda: "xingxi_pixel_pet")
        self.state_snapshot_provider = state_snapshot_provider or (lambda: {})

    def snapshot(self) -> dict[str, object]:
        candidates = self.subsystem.host.candidates or self.subsystem.host.discover()
        rows = []
        bundled = self.subsystem.paths.bundled_root.resolve()
        for item in self.subsystem.host.catalog():
            candidate = next(c for c in candidates if c.manifest.plugin_id == item.plugin_id)
            audit = audit_plugin(candidate)
            health = self.subsystem.health.status(item.plugin_id)
            payload = item.to_dict()
            payload.update(
                {
                    "source_kind": "bundled" if bundled == candidate.root.resolve() or bundled in candidate.root.resolve().parents else "installed",
                    "audit_ok": audit.ok,
                    "risk_level": audit.risk_level,
                    "audit_findings": [row.to_dict() for row in audit.findings],
                    "consecutive_failures": health.consecutive_failures,
                    "quarantined": health.quarantined,
                    "effective_settings": self.effective_settings(item.plugin_id),
                }
            )
            rows.append(payload)
        return {
            "title": "E-Moti 插件中心",
            "subtitle": "安装、启用、授权和排查本地插件。第三方插件在应用进程内运行，请先查看权限与审计结果。",
            "started": self.subsystem.host.started,
            "boot": self.subsystem.host._report().to_dict(),
            "paths": {
                "bundled_root": str(self.subsystem.paths.bundled_root),
                "installed_root": str(self.subsystem.paths.installed_root),
                "data_root": str(self.subsystem.paths.data_root),
            },
            "plugins": rows,
        }

    def set_enabled(self, plugin_id: str, enabled: bool) -> PluginCenterOperation:
        try:
            self.subsystem.host.set_enabled(plugin_id, enabled)
            report = self.subsystem.reload_from_disk()
            self.subsystem.journal.append("plugin.enabled.changed", plugin_id=plugin_id, payload={"enabled": enabled})
            return PluginCenterOperation(True, "enable" if enabled else "disable", plugin_id, "插件状态已更新", report.to_dict())
        except Exception as exc:
            return PluginCenterOperation(False, "enable" if enabled else "disable", plugin_id, str(exc))

    def set_settings(self, plugin_id: str, settings: Mapping[str, object]) -> PluginCenterOperation:
        try:
            self.subsystem.host.set_plugin_settings(plugin_id, settings)
            report = self.subsystem.reload_from_disk()
            return PluginCenterOperation(True, "settings", plugin_id, "插件设置已保存", report.to_dict())
        except Exception as exc:
            return PluginCenterOperation(False, "settings", plugin_id, str(exc))

    def effective_settings(self, plugin_id: str) -> dict[str, object]:
        candidate = self.subsystem.host._require_discovered(plugin_id)
        result = dict(candidate.manifest.settings)
        override = self.subsystem.host.configuration.plugin_settings.get(plugin_id, {})
        if isinstance(override, Mapping):
            result.update(dict(override))
        return result

    def set_permission_grants(self, plugin_id: str, permissions: list[str]) -> PluginCenterOperation:
        try:
            self.subsystem.host.set_permission_grants(plugin_id, permissions)
            report = self.subsystem.reload_from_disk()
            return PluginCenterOperation(True, "permissions", plugin_id, "权限设置已保存", report.to_dict())
        except Exception as exc:
            return PluginCenterOperation(False, "permissions", plugin_id, str(exc))

    def clear_quarantine(self, plugin_id: str) -> PluginCenterOperation:
        status = self.subsystem.health.clear_quarantine(plugin_id)
        return PluginCenterOperation(True, "clear-quarantine", plugin_id, "隔离状态已清除", status.to_dict())

    def clear_data(self, plugin_id: str) -> PluginCenterOperation:
        try:
            self.subsystem.host.clear_plugin_data(plugin_id)
            return PluginCenterOperation(True, "clear-data", plugin_id, "插件本地数据已清除")
        except Exception as exc:
            return PluginCenterOperation(False, "clear-data", plugin_id, str(exc))

    def panel_models(self) -> list[dict[str, object]]:
        character_id = str(self.character_id_provider())
        state = self.state_snapshot_provider()
        rows: list[dict[str, object]] = []
        for definition in self.subsystem.runtime.list_ui_panels():
            try:
                model = self.subsystem.runtime.build_ui_panel_model(definition.panel_id, character_id=character_id, state_snapshot=state)
                rows.append({"panel_id": definition.panel_id, "title": definition.title, "description": definition.description, "model": dict(model)})
            except Exception as exc:
                rows.append({"panel_id": definition.panel_id, "title": definition.title, "error": str(exc)})
        return rows

    def install(self, archive: Path | str) -> PluginCenterOperation:
        result = self.subsystem.install(archive)
        return PluginCenterOperation(result.ok, result.operation, result.plugin_id, result.message, result.payload or {})

    def uninstall(self, plugin_id: str) -> PluginCenterOperation:
        result = self.subsystem.uninstall(plugin_id)
        return PluginCenterOperation(result.ok, result.operation, result.plugin_id, result.message, result.payload or {})

    def package(self, plugin_id: str, output_path: Path | str) -> PluginCenterOperation:
        try:
            candidate = self.subsystem.host._require_discovered(plugin_id)
            report = build_plugin_archive(candidate.root, output_path)
            return PluginCenterOperation(True, "package", plugin_id, "插件包已生成", report.to_dict())
        except Exception as exc:
            return PluginCenterOperation(False, "package", plugin_id, str(exc))
