from __future__ import annotations

"""Manifest loading and filesystem-safe discovery for E-Moti plugins."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re

from .plugin_api import (
    PLUGIN_MANIFEST_SCHEMA_VERSION,
    PluginDependency,
    PluginManifest,
    PluginPermission,
)

PLUGIN_MANIFEST_NAME = "emoti-plugin.json"
_PLUGIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9._-]+)?$")
_CALLABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PluginManifestError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PluginCandidate:
    root: Path
    manifest_path: Path
    manifest: PluginManifest


def load_plugin_manifest(path: Path | str) -> PluginManifest:
    manifest_path = Path(path).resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise PluginManifestError(f"plugin manifest does not exist: {manifest_path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PluginManifestError(f"plugin manifest is not valid UTF-8 JSON: {manifest_path}") from exc
    if not isinstance(payload, Mapping):
        raise PluginManifestError("plugin manifest root must be an object")

    schema_version = _integer(payload.get("schema_version"), "schema_version")
    if schema_version != PLUGIN_MANIFEST_SCHEMA_VERSION:
        raise PluginManifestError(
            f"unsupported plugin manifest schema version: {schema_version}; "
            f"expected {PLUGIN_MANIFEST_SCHEMA_VERSION}"
        )

    plugin_id = _text(payload.get("id"), "plugin id", 80)
    if not _PLUGIN_ID_RE.fullmatch(plugin_id):
        raise PluginManifestError(
            "plugin id must use lowercase letters, digits, dot, underscore, or dash"
        )

    name = _text(payload.get("name"), "plugin name", 120)
    version = _text(payload.get("version"), "plugin version", 40)
    if not _VERSION_RE.fullmatch(version):
        raise PluginManifestError("plugin version must use semantic version form, for example 0.1.0")
    api_version = _text(payload.get("api_version"), "plugin api_version", 20)

    entrypoint_path, entrypoint_callable = _parse_entrypoint(payload.get("entrypoint"))
    root = manifest_path.parent
    resolved_entrypoint = (root / entrypoint_path).resolve()
    if root != resolved_entrypoint and root not in resolved_entrypoint.parents:
        raise PluginManifestError("plugin entrypoint escapes its plugin directory")
    if not resolved_entrypoint.is_file():
        raise PluginManifestError(f"plugin entrypoint does not exist: {entrypoint_path}")

    permissions = _permissions(payload.get("permissions", []))
    dependencies = _dependencies(payload.get("dependencies", []), plugin_id=plugin_id)
    settings = payload.get("settings", {})
    contributes = payload.get("contributes", {})
    if not isinstance(settings, Mapping):
        raise PluginManifestError("plugin settings must be an object")
    _assert_no_inline_credentials(settings, path="settings")
    if not isinstance(contributes, Mapping):
        raise PluginManifestError("plugin contributes must be an object")

    return PluginManifest(
        schema_version=schema_version,
        plugin_id=plugin_id,
        name=name,
        version=version,
        api_version=api_version,
        entrypoint_path=entrypoint_path,
        entrypoint_callable=entrypoint_callable,
        description=_optional_text(payload.get("description"), 500),
        default_enabled=bool(payload.get("default_enabled", False)),
        permissions=frozenset(permissions),
        dependencies=dependencies,
        settings=dict(settings),
        contributes=dict(contributes),
    )


def discover_plugin_candidates(roots: Iterable[Path | str]) -> tuple[PluginCandidate, ...]:
    found: list[PluginCandidate] = []
    ids: dict[str, Path] = {}
    for raw_root in roots:
        root = Path(raw_root).resolve()
        if not root.exists():
            continue
        manifest_paths: list[Path]
        if root.is_file() and root.name == PLUGIN_MANIFEST_NAME:
            manifest_paths = [root]
        elif (root / PLUGIN_MANIFEST_NAME).is_file():
            manifest_paths = [root / PLUGIN_MANIFEST_NAME]
        elif root.is_dir():
            manifest_paths = sorted(
                child / PLUGIN_MANIFEST_NAME
                for child in root.iterdir()
                if child.is_dir() and (child / PLUGIN_MANIFEST_NAME).is_file()
            )
        else:
            manifest_paths = []

        for manifest_path in manifest_paths:
            manifest = load_plugin_manifest(manifest_path)
            previous = ids.get(manifest.plugin_id)
            if previous is not None:
                raise PluginManifestError(
                    f"duplicate plugin id {manifest.plugin_id}: {previous} and {manifest_path}"
                )
            ids[manifest.plugin_id] = manifest_path
            found.append(
                PluginCandidate(
                    root=manifest_path.parent.resolve(),
                    manifest_path=manifest_path.resolve(),
                    manifest=manifest,
                )
            )
    return tuple(sorted(found, key=lambda item: item.manifest.plugin_id))


def _parse_entrypoint(value: object) -> tuple[str, str]:
    raw = _text(value, "plugin entrypoint", 240)
    if ":" in raw:
        path_part, callable_part = raw.rsplit(":", 1)
    else:
        path_part, callable_part = raw, "activate"
    path_part = path_part.replace("\\", "/").strip()
    callable_part = callable_part.strip()
    pure = PurePosixPath(path_part)
    if (
        not path_part
        or pure.is_absolute()
        or ".." in pure.parts
        or pure.suffix != ".py"
        or any(part in {"", "."} for part in pure.parts)
    ):
        raise PluginManifestError("plugin entrypoint must be a relative .py path inside the plugin")
    if not _CALLABLE_RE.fullmatch(callable_part):
        raise PluginManifestError("plugin entrypoint callable is invalid")
    return pure.as_posix(), callable_part


def _permissions(value: object) -> tuple[PluginPermission, ...]:
    if not isinstance(value, list):
        raise PluginManifestError("plugin permissions must be an array")
    result: list[PluginPermission] = []
    seen: set[PluginPermission] = set()
    for raw in value:
        try:
            permission = PluginPermission(str(raw))
        except ValueError as exc:
            raise PluginManifestError(f"unknown plugin permission: {raw}") from exc
        if permission in seen:
            continue
        seen.add(permission)
        result.append(permission)
    return tuple(result)


def _dependencies(value: object, *, plugin_id: str) -> tuple[PluginDependency, ...]:
    if not isinstance(value, list):
        raise PluginManifestError("plugin dependencies must be an array")
    result: list[PluginDependency] = []
    seen: set[str] = set()
    for raw in value:
        if isinstance(raw, str):
            dependency_id = raw.strip()
            optional = False
        elif isinstance(raw, Mapping):
            dependency_id = _text(raw.get("id"), "dependency id", 80)
            optional = bool(raw.get("optional", False))
        else:
            raise PluginManifestError("plugin dependency must be a string or object")
        if not _PLUGIN_ID_RE.fullmatch(dependency_id):
            raise PluginManifestError(f"invalid dependency id: {dependency_id}")
        if dependency_id == plugin_id:
            raise PluginManifestError("plugin cannot depend on itself")
        if dependency_id in seen:
            raise PluginManifestError(f"duplicate dependency: {dependency_id}")
        seen.add(dependency_id)
        result.append(PluginDependency(dependency_id, optional=optional))
    return tuple(result)


def _text(value: object, label: str, limit: int) -> str:
    if not isinstance(value, str):
        raise PluginManifestError(f"{label} must be a string")
    cleaned = " ".join(value.strip().split())[:limit]
    if not cleaned:
        raise PluginManifestError(f"{label} is required")
    return cleaned


def _optional_text(value: object, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise PluginManifestError("plugin description must be a string")
    return " ".join(value.strip().split())[:limit]


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise PluginManifestError(f"{label} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise PluginManifestError(f"{label} must be an integer") from exc


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


def _assert_no_inline_credentials(value: object, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _CREDENTIAL_KEYS and str(item).strip():
                raise PluginManifestError(
                    f"inline credential is not allowed at {path}.{key}; use a host credential alias"
                )
            _assert_no_inline_credentials(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_inline_credentials(item, path=f"{path}[{index}]")
