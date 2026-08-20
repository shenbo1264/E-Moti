from __future__ import annotations

import json
from pathlib import Path

import pytest

from guanghe_companion.plugin_api import PluginPermission
from guanghe_companion.plugin_manifest import (
    PluginManifestError,
    discover_plugin_candidates,
    load_plugin_manifest,
)


def _write_manifest(root: Path, **overrides: object) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "schema_version": 1,
        "id": "emoti.test.sample",
        "name": "Sample Plugin",
        "version": "0.1.0",
        "api_version": "1",
        "entrypoint": "plugin.py:activate",
        "description": "test plugin",
        "default_enabled": False,
        "permissions": ["events.subscribe", "actions.register"],
        "dependencies": [],
        "settings": {"greeting": "hello"},
    }
    payload.update(overrides)
    path = root / "emoti-plugin.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "plugin.py").write_text("def activate(ctx):\n    return None\n", encoding="utf-8")
    return path


def test_load_valid_manifest(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "plugin")

    manifest = load_plugin_manifest(path)

    assert manifest.plugin_id == "emoti.test.sample"
    assert manifest.entrypoint_path == "plugin.py"
    assert manifest.entrypoint_callable == "activate"
    assert manifest.settings == {"greeting": "hello"}
    assert PluginPermission.ACTIONS_REGISTER in manifest.permissions


def test_manifest_rejects_entrypoint_path_traversal(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "plugin", entrypoint="../outside.py:activate")

    with pytest.raises(PluginManifestError, match="entrypoint"):
        load_plugin_manifest(path)


def test_manifest_rejects_invalid_plugin_id(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "plugin", id="Bad Plugin ID")

    with pytest.raises(PluginManifestError, match="plugin id"):
        load_plugin_manifest(path)


def test_manifest_rejects_unknown_permission(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "plugin", permissions=["events.subscribe", "computer.takeover"])

    with pytest.raises(PluginManifestError, match="permission"):
        load_plugin_manifest(path)


def test_manifest_rejects_duplicate_dependencies(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path / "plugin",
        dependencies=["emoti.dep.one", {"id": "emoti.dep.one", "optional": True}],
    )

    with pytest.raises(PluginManifestError, match="duplicate dependency"):
        load_plugin_manifest(path)


def test_manifest_rejects_missing_entrypoint_file(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "plugin")
    (path.parent / "plugin.py").unlink()

    with pytest.raises(PluginManifestError, match="does not exist"):
        load_plugin_manifest(path)



def test_manifest_rejects_inline_credentials_in_settings(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path / "plugin", settings={"api_key": "secret-value"})

    with pytest.raises(PluginManifestError, match="credential"):
        load_plugin_manifest(path)

def test_discovery_accepts_plugin_root_and_plugin_collection(tmp_path: Path) -> None:
    direct = tmp_path / "direct"
    collection = tmp_path / "collection"
    _write_manifest(direct, id="emoti.direct")
    _write_manifest(collection / "one", id="emoti.one")
    _write_manifest(collection / "two", id="emoti.two")

    candidates = discover_plugin_candidates([direct, collection])

    assert [candidate.manifest.plugin_id for candidate in candidates] == [
        "emoti.direct",
        "emoti.one",
        "emoti.two",
    ]


def test_discovery_rejects_duplicate_plugin_ids(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    _write_manifest(collection / "one", id="emoti.duplicate")
    _write_manifest(collection / "two", id="emoti.duplicate")

    with pytest.raises(PluginManifestError, match="duplicate plugin id"):
        discover_plugin_candidates([collection])
