from __future__ import annotations

"""Persistent, credential-free configuration for E-Moti plugins."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import json
from pathlib import Path

from .plugin_api import PluginPermission, freeze_mapping, thaw_value
from .plugin_manifest import PluginCandidate

PLUGIN_CONFIGURATION_SCHEMA_VERSION = 1
_CREDENTIAL_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "authorization",
    "password",
    "secret",
    "client_secret",
}


class PluginConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PluginRuntimeConfiguration:
    schema_version: int = PLUGIN_CONFIGURATION_SCHEMA_VERSION
    enabled_plugins: tuple[str, ...] = ()
    disabled_plugins: tuple[str, ...] = ()
    permission_grants: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    plugin_settings: Mapping[str, Mapping[str, object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        enabled = _unique_strings(self.enabled_plugins)
        disabled = _unique_strings(self.disabled_plugins)
        grants: dict[str, tuple[str, ...]] = {}
        for plugin_id, rows in self.permission_grants.items():
            permissions: list[str] = []
            for raw in rows:
                permission = PluginPermission(str(raw)).value
                if permission not in permissions:
                    permissions.append(permission)
            grants[str(plugin_id)] = tuple(permissions)
        settings: dict[str, Mapping[str, object]] = {}
        for plugin_id, payload in self.plugin_settings.items():
            if not isinstance(payload, Mapping):
                raise PluginConfigurationError(f"settings for {plugin_id} must be an object")
            _assert_no_inline_credentials(payload, path=f"settings.{plugin_id}")
            settings[str(plugin_id)] = freeze_mapping(payload)
        object.__setattr__(self, "enabled_plugins", enabled)
        object.__setattr__(self, "disabled_plugins", disabled)
        object.__setattr__(self, "permission_grants", freeze_mapping(grants))
        object.__setattr__(self, "plugin_settings", freeze_mapping(settings))

    def effective_enabled(self, candidates: Iterable[PluginCandidate]) -> set[str]:
        explicit_on = set(self.enabled_plugins)
        explicit_off = set(self.disabled_plugins)
        result = set(explicit_on)
        for candidate in candidates:
            plugin_id = candidate.manifest.plugin_id
            if plugin_id in explicit_off:
                result.discard(plugin_id)
            elif candidate.manifest.default_enabled:
                result.add(plugin_id)
        return result

    def grants_for_runtime(self) -> dict[str, frozenset[PluginPermission]]:
        return {
            plugin_id: frozenset(PluginPermission(raw) for raw in rows)
            for plugin_id, rows in self.permission_grants.items()
        }

    def settings_for_runtime(self) -> dict[str, Mapping[str, object]]:
        return {
            plugin_id: dict(thaw_value(payload))
            for plugin_id, payload in self.plugin_settings.items()
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "enabled_plugins": list(self.enabled_plugins),
            "disabled_plugins": list(self.disabled_plugins),
            "permission_grants": {
                plugin_id: list(rows)
                for plugin_id, rows in self.permission_grants.items()
            },
            "plugin_settings": thaw_value(self.plugin_settings),
        }


@dataclass(slots=True)
class PluginRuntimeConfigurationStore:
    path: Path | str
    last_warning: str = ""

    def load(self) -> PluginRuntimeConfiguration:
        target = Path(self.path)
        self.last_warning = ""
        if not target.exists():
            return PluginRuntimeConfiguration()
        try:
            payload = json.loads(target.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, Mapping):
                raise PluginConfigurationError("plugin configuration root must be an object")
            schema_version = int(payload.get("schema_version", PLUGIN_CONFIGURATION_SCHEMA_VERSION))
            if schema_version != PLUGIN_CONFIGURATION_SCHEMA_VERSION:
                raise PluginConfigurationError(
                    f"unsupported plugin configuration schema version: {schema_version}"
                )
            return PluginRuntimeConfiguration(
                schema_version=schema_version,
                enabled_plugins=tuple(_string_list(payload.get("enabled_plugins", []))),
                disabled_plugins=tuple(_string_list(payload.get("disabled_plugins", []))),
                permission_grants=_mapping_of_string_lists(payload.get("permission_grants", {})),
                plugin_settings=_mapping_of_mappings(payload.get("plugin_settings", {})),
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self.last_warning = f"plugin configuration was ignored: {exc}"
            return PluginRuntimeConfiguration()

    def save(self, configuration: PluginRuntimeConfiguration) -> None:
        # Reconstruct to ensure caller-provided nested values receive the same
        # credential and type checks before persistence.
        checked = PluginRuntimeConfiguration(
            schema_version=configuration.schema_version,
            enabled_plugins=configuration.enabled_plugins,
            disabled_plugins=configuration.disabled_plugins,
            permission_grants=configuration.permission_grants,
            plugin_settings=configuration.plugin_settings,
        )
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            json.dumps(checked.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)


def _assert_no_inline_credentials(value: object, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _CREDENTIAL_KEYS and str(item).strip():
                raise PluginConfigurationError(
                    f"inline credential is not allowed at {path}.{key}; use a host credential alias"
                )
            _assert_no_inline_credentials(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_inline_credentials(item, path=f"{path}[{index}]")


def _unique_strings(value: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for raw in value:
        item = str(raw).strip()
        if item and item not in result:
            result.append(item)
    return tuple(result)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise PluginConfigurationError("plugin id lists must be arrays")
    return [str(item) for item in value]


def _mapping_of_string_lists(value: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, Mapping):
        raise PluginConfigurationError("permission_grants must be an object")
    result: dict[str, tuple[str, ...]] = {}
    for key, rows in value.items():
        if not isinstance(rows, list):
            raise PluginConfigurationError(f"permission grants for {key} must be an array")
        result[str(key)] = tuple(str(row) for row in rows)
    return result


def _mapping_of_mappings(value: object) -> dict[str, Mapping[str, object]]:
    if not isinstance(value, Mapping):
        raise PluginConfigurationError("plugin_settings must be an object")
    result: dict[str, Mapping[str, object]] = {}
    for key, row in value.items():
        if not isinstance(row, Mapping):
            raise PluginConfigurationError(f"settings for {key} must be an object")
        result[str(key)] = dict(row)
    return result
