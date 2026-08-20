from __future__ import annotations

"""Generic data model for a future PySide6 Plugin Center page."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from .plugin_api import SENSITIVE_PLUGIN_PERMISSIONS
from .plugin_configuration import PluginRuntimeConfiguration
from .plugin_manifest import PluginCandidate
from .plugin_runtime import PluginRuntime


@dataclass(frozen=True, slots=True)
class PluginCatalogItem:
    plugin_id: str
    name: str
    version: str
    description: str
    enabled: bool
    state: str
    permissions: tuple[str, ...]
    sensitive_permissions: tuple[str, ...]
    needs_permission_review: bool
    dependencies: tuple[str, ...]
    contributes: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled,
            "state": self.state,
            "permissions": list(self.permissions),
            "sensitive_permissions": list(self.sensitive_permissions),
            "needs_permission_review": self.needs_permission_review,
            "dependencies": list(self.dependencies),
            "contributes": {key: list(value) for key, value in self.contributes.items()},
        }


def build_plugin_catalog(
    candidates: Iterable[PluginCandidate],
    *,
    runtime: PluginRuntime,
    configuration: PluginRuntimeConfiguration,
) -> tuple[PluginCatalogItem, ...]:
    rows = tuple(candidates)
    enabled_ids = configuration.effective_enabled(rows)
    items: list[PluginCatalogItem] = []
    for candidate in rows:
        manifest = candidate.manifest
        permissions = tuple(sorted(permission.value for permission in manifest.permissions))
        sensitive = tuple(
            sorted(
                permission.value
                for permission in manifest.permissions
                if permission in SENSITIVE_PLUGIN_PERMISSIONS
            )
        )
        granted = set(configuration.permission_grants.get(manifest.plugin_id, ()))
        needs_review = any(permission not in granted for permission in sensitive)
        status = runtime.status(manifest.plugin_id)
        state = "not_loaded" if status.state == "not_found" else status.state
        contributes: dict[str, tuple[str, ...]] = {}
        for key, value in manifest.contributes.items():
            if isinstance(value, (list, tuple)):
                contributes[str(key)] = tuple(str(item) for item in value)
            elif value is not None:
                contributes[str(key)] = (str(value),)
        items.append(
            PluginCatalogItem(
                plugin_id=manifest.plugin_id,
                name=manifest.name,
                version=manifest.version,
                description=manifest.description,
                enabled=manifest.plugin_id in enabled_ids,
                state=state,
                permissions=permissions,
                sensitive_permissions=sensitive,
                needs_permission_review=needs_review,
                dependencies=tuple(dep.plugin_id for dep in manifest.dependencies),
                contributes=contributes,
            )
        )
    return tuple(sorted(items, key=lambda item: (item.name.lower(), item.plugin_id)))
