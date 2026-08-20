from __future__ import annotations

"""Application-facing bootstrap for E-Moti's plugin runtime.

``PluginRuntime`` owns registrations, permissions, and reversible effects.
``PluginHost`` adds the startup behavior needed by the desktop application:
standard paths, configuration, explicit opt-in for user-installed plugins,
failure isolation, catalog data, reload, permission grants, and data cleanup.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .plugin_api import PluginPermission, SENSITIVE_PLUGIN_PERMISSIONS
from .plugin_catalog_view_model import PluginCatalogItem, build_plugin_catalog
from .plugin_configuration import (
    PluginRuntimeConfiguration,
    PluginRuntimeConfigurationStore,
)
from .plugin_manifest import (
    PLUGIN_MANIFEST_NAME,
    PluginCandidate,
    PluginManifestError,
    load_plugin_manifest,
)
from .plugin_runtime import PluginRuntime


@dataclass(frozen=True, slots=True)
class PluginPaths:
    bundled_root: Path
    installed_root: Path
    data_root: Path
    configuration_path: Path

    @classmethod
    def from_roots(
        cls,
        *,
        application_root: Path | str,
        user_data_root: Path | str,
    ) -> "PluginPaths":
        app = Path(application_root)
        user = Path(user_data_root)
        return cls(
            bundled_root=app / "plugins",
            installed_root=user / "plugins" / "installed",
            data_root=user / "plugins" / "data",
            configuration_path=user / "plugins" / "config.json",
        )


@dataclass(frozen=True, slots=True)
class PluginBootFailure:
    plugin_id: str
    stage: str
    error_type: str
    message: str
    source_path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "plugin_id": self.plugin_id,
            "stage": self.stage,
            "error_type": self.error_type,
            "message": self.message,
            "source_path": self.source_path,
        }


@dataclass(frozen=True, slots=True)
class PluginBootReport:
    discovered_plugin_ids: tuple[str, ...]
    loaded_plugin_ids: tuple[str, ...]
    configuration_warning: str = ""
    failures: tuple[PluginBootFailure, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "discovered_plugin_ids": list(self.discovered_plugin_ids),
            "loaded_plugin_ids": list(self.loaded_plugin_ids),
            "configuration_warning": self.configuration_warning,
            "failures": [failure.to_dict() for failure in self.failures],
        }


class PluginHost:
    def __init__(self, paths: PluginPaths) -> None:
        self.paths = paths
        self.configuration_store = PluginRuntimeConfigurationStore(
            paths.configuration_path
        )
        self.configuration = PluginRuntimeConfiguration()
        self.candidates: tuple[PluginCandidate, ...] = ()
        self.runtime = PluginRuntime(data_root=paths.data_root)
        self.discovery_failures: tuple[PluginBootFailure, ...] = ()
        self.boot_failures: tuple[PluginBootFailure, ...] = ()
        self._started = False

    @property
    def started(self) -> bool:
        return self._started

    def discover(self) -> tuple[PluginCandidate, ...]:
        candidates: list[PluginCandidate] = []
        failures: list[PluginBootFailure] = []
        seen: dict[str, Path] = {}
        for base in (self.paths.bundled_root, self.paths.installed_root):
            for manifest_path in _manifest_paths(base):
                try:
                    manifest = load_plugin_manifest(manifest_path)
                except PluginManifestError as exc:
                    failures.append(
                        PluginBootFailure(
                            plugin_id=manifest_path.parent.name,
                            stage="discovery",
                            error_type=type(exc).__name__,
                            message=str(exc)[:500],
                            source_path=str(manifest_path),
                        )
                    )
                    continue
                previous = seen.get(manifest.plugin_id)
                if previous is not None:
                    failures.append(
                        PluginBootFailure(
                            plugin_id=manifest.plugin_id,
                            stage="discovery",
                            error_type="DuplicatePluginId",
                            message=(
                                f"duplicate plugin id; first manifest remains active: {previous}"
                            ),
                            source_path=str(manifest_path),
                        )
                    )
                    continue
                seen[manifest.plugin_id] = manifest_path
                candidates.append(
                    PluginCandidate(
                        root=manifest_path.parent.resolve(),
                        manifest_path=manifest_path.resolve(),
                        manifest=manifest,
                    )
                )
        self.candidates = tuple(
            sorted(candidates, key=lambda item: item.manifest.plugin_id)
        )
        self.discovery_failures = tuple(failures)
        return self.candidates

    def start(self) -> PluginBootReport:
        if self._started:
            return self._report()

        candidates = self.discover()
        configuration = self.configuration_store.load()
        runtime = PluginRuntime.from_configuration(
            data_root=self.paths.data_root,
            configuration=configuration,
        )
        enabled_ids = self._effective_enabled(candidates, configuration)
        failures = list(self.discovery_failures)

        # Load one selected root at a time. A faulty plugin and its dependency
        # closure are rolled back by PluginRuntime, while unrelated plugins can
        # continue loading.
        for plugin_id in sorted(enabled_ids):
            if plugin_id in runtime.loaded_plugin_ids:
                continue
            try:
                runtime.load_all(candidates, enabled_ids={plugin_id})
            except Exception as exc:
                candidate = _find_candidate(candidates, plugin_id)
                failures.append(
                    PluginBootFailure(
                        plugin_id=plugin_id,
                        stage="activation",
                        error_type=type(exc).__name__,
                        message=str(exc)[:500],
                        source_path=(str(candidate.root) if candidate else ""),
                    )
                )

        self.configuration = configuration
        self.runtime = runtime
        self.boot_failures = tuple(failures)
        self._started = True
        return self._report()

    def shutdown(self) -> None:
        self.runtime.shutdown()
        self._started = False

    def reload_from_disk(self) -> PluginBootReport:
        self.shutdown()
        return self.start()

    def catalog(self) -> tuple[PluginCatalogItem, ...]:
        if not self.candidates:
            self.discover()
        return build_plugin_catalog(
            self.candidates,
            runtime=self.runtime,
            configuration=self.configuration,
        )

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        plugin_id = self._require_discovered(plugin_id).manifest.plugin_id
        enabled_plugins = list(self.configuration.enabled_plugins)
        disabled_plugins = list(self.configuration.disabled_plugins)
        if enabled:
            _append_unique(enabled_plugins, plugin_id)
            _remove_all(disabled_plugins, plugin_id)
        else:
            _append_unique(disabled_plugins, plugin_id)
            _remove_all(enabled_plugins, plugin_id)
        self._save_configuration(
            enabled_plugins=enabled_plugins,
            disabled_plugins=disabled_plugins,
        )

    def set_permission_grants(
        self,
        plugin_id: str,
        permissions: Iterable[PluginPermission | str],
    ) -> None:
        candidate = self._require_discovered(plugin_id)
        normalized: list[str] = []
        for raw in permissions:
            permission = (
                raw if isinstance(raw, PluginPermission) else PluginPermission(str(raw))
            )
            if permission not in candidate.manifest.permissions:
                raise ValueError(
                    f"plugin {plugin_id} did not declare permission {permission.value}"
                )
            if permission not in SENSITIVE_PLUGIN_PERMISSIONS:
                raise ValueError(
                    f"permission {permission.value} does not require a persisted grant"
                )
            if permission.value not in normalized:
                normalized.append(permission.value)
        grants = {
            key: tuple(value)
            for key, value in self.configuration.permission_grants.items()
        }
        grants[plugin_id] = tuple(normalized)
        self._save_configuration(permission_grants=grants)
        if self._started:
            self.runtime._permission_grants = self.configuration.grants_for_runtime()
            if plugin_id in self.runtime.loaded_plugin_ids:
                candidate = self._require_discovered(plugin_id)
                self.runtime.unload(plugin_id, force=True)
                self.runtime.load(candidate)

    def set_plugin_settings(
        self,
        plugin_id: str,
        settings: Mapping[str, object],
    ) -> None:
        self._require_discovered(plugin_id)
        all_settings = {
            key: dict(value)
            for key, value in self.configuration.plugin_settings.items()
        }
        all_settings[plugin_id] = dict(settings)
        self._save_configuration(plugin_settings=all_settings)
        if self._started:
            self.runtime._settings_overrides[plugin_id] = dict(settings)
            if plugin_id in self.runtime.loaded_plugin_ids:
                candidate = self._require_discovered(plugin_id)
                self.runtime.unload(plugin_id, force=True)
                self.runtime.load(candidate)

    def clear_plugin_data(self, plugin_id: str) -> None:
        self._require_discovered(plugin_id)
        self.runtime.plugin_storage(plugin_id).clear()

    def _effective_enabled(
        self,
        candidates: tuple[PluginCandidate, ...],
        configuration: PluginRuntimeConfiguration,
    ) -> set[str]:
        explicit_on = set(configuration.enabled_plugins)
        explicit_off = set(configuration.disabled_plugins)
        result = set(explicit_on)
        bundled_root = self.paths.bundled_root.resolve()
        for candidate in candidates:
            plugin_id = candidate.manifest.plugin_id
            if plugin_id in explicit_off:
                result.discard(plugin_id)
                continue
            if _is_within(candidate.root, bundled_root) and candidate.manifest.default_enabled:
                result.add(plugin_id)
        return result

    def _require_discovered(self, plugin_id: str) -> PluginCandidate:
        if not self.candidates:
            self.discover()
        candidate = _find_candidate(self.candidates, plugin_id)
        if candidate is None:
            raise KeyError(f"plugin was not discovered: {plugin_id}")
        return candidate

    def _save_configuration(
        self,
        *,
        enabled_plugins: Iterable[str] | None = None,
        disabled_plugins: Iterable[str] | None = None,
        permission_grants: Mapping[str, tuple[str, ...]] | None = None,
        plugin_settings: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        configuration = PluginRuntimeConfiguration(
            schema_version=self.configuration.schema_version,
            enabled_plugins=tuple(
                enabled_plugins
                if enabled_plugins is not None
                else self.configuration.enabled_plugins
            ),
            disabled_plugins=tuple(
                disabled_plugins
                if disabled_plugins is not None
                else self.configuration.disabled_plugins
            ),
            permission_grants=(
                permission_grants
                if permission_grants is not None
                else self.configuration.permission_grants
            ),
            plugin_settings=(
                plugin_settings
                if plugin_settings is not None
                else self.configuration.plugin_settings
            ),
        )
        self.configuration_store.save(configuration)
        self.configuration = configuration

    def _report(self) -> PluginBootReport:
        return PluginBootReport(
            discovered_plugin_ids=tuple(
                candidate.manifest.plugin_id for candidate in self.candidates
            ),
            loaded_plugin_ids=self.runtime.loaded_plugin_ids,
            configuration_warning=self.configuration_store.last_warning,
            failures=self.boot_failures,
        )


def _manifest_paths(base: Path) -> tuple[Path, ...]:
    root = Path(base).resolve()
    if not root.exists():
        return ()
    if root.is_file() and root.name == PLUGIN_MANIFEST_NAME:
        return (root,)
    direct = root / PLUGIN_MANIFEST_NAME
    if direct.is_file():
        return (direct,)
    if not root.is_dir():
        return ()
    return tuple(
        sorted(
            child / PLUGIN_MANIFEST_NAME
            for child in root.iterdir()
            if child.is_dir() and (child / PLUGIN_MANIFEST_NAME).is_file()
        )
    )


def _find_candidate(
    candidates: Iterable[PluginCandidate], plugin_id: str
) -> PluginCandidate | None:
    return next(
        (
            candidate
            for candidate in candidates
            if candidate.manifest.plugin_id == plugin_id
        ),
        None,
    )


def _is_within(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    return resolved == root or root in resolved.parents


def _append_unique(rows: list[str], value: str) -> None:
    if value not in rows:
        rows.append(value)


def _remove_all(rows: list[str], value: str) -> None:
    while value in rows:
        rows.remove(value)
