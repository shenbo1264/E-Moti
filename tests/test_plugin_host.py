from __future__ import annotations

import json
from pathlib import Path

from guanghe_companion.plugin_api import PluginPermission
from guanghe_companion.plugin_host import PluginHost, PluginPaths


def _plugin(
    root: Path,
    plugin_id: str,
    *,
    default_enabled: bool,
    permissions: tuple[str, ...] = (),
    source: str = "def activate(ctx):\n    pass\n",
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "emoti-plugin.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": plugin_id,
                "name": plugin_id,
                "version": "0.1.0",
                "api_version": "1",
                "entrypoint": "plugin.py:activate",
                "description": "host test",
                "default_enabled": default_enabled,
                "permissions": list(permissions),
                "dependencies": [],
                "settings": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "plugin.py").write_text(source, encoding="utf-8")


def _paths(tmp_path: Path) -> PluginPaths:
    return PluginPaths(
        bundled_root=tmp_path / "app" / "plugins",
        installed_root=tmp_path / "user" / "plugins" / "installed",
        data_root=tmp_path / "user" / "plugins" / "data",
        configuration_path=tmp_path / "user" / "plugins" / "config.json",
    )


def test_host_loads_bundled_defaults_but_keeps_installed_defaults_opt_in(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _plugin(paths.bundled_root / "core", "emoti.bundled.core", default_enabled=True)
    _plugin(paths.installed_root / "third-party", "emoti.community.third-party", default_enabled=True)

    host = PluginHost(paths)
    report = host.start()

    assert report.discovered_plugin_ids == (
        "emoti.bundled.core",
        "emoti.community.third-party",
    )
    assert report.loaded_plugin_ids == ("emoti.bundled.core",)
    assert host.runtime.loaded_plugin_ids == ("emoti.bundled.core",)


def test_host_can_enable_installed_plugin_and_reload_from_disk(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _plugin(paths.installed_root / "hello", "emoti.community.hello", default_enabled=False)
    host = PluginHost(paths)

    first = host.start()
    assert first.loaded_plugin_ids == ()

    host.set_enabled("emoti.community.hello", True)
    second = host.reload_from_disk()

    assert second.loaded_plugin_ids == ("emoti.community.hello",)
    persisted = json.loads(paths.configuration_path.read_text(encoding="utf-8"))
    assert persisted["enabled_plugins"] == ["emoti.community.hello"]


def test_host_permission_grant_is_persisted_and_used(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _plugin(
        paths.installed_root / "network",
        "emoti.community.network",
        default_enabled=False,
        permissions=("network.http",),
        source="def activate(ctx):\n    ctx.require('network.http')\n",
    )
    host = PluginHost(paths)
    host.start()
    host.set_enabled("emoti.community.network", True)
    host.set_permission_grants(
        "emoti.community.network", {PluginPermission.NETWORK_HTTP}
    )

    report = host.reload_from_disk()

    assert report.loaded_plugin_ids == ("emoti.community.network",)
    catalog = {item.plugin_id: item for item in host.catalog()}
    assert catalog["emoti.community.network"].needs_permission_review is False


def test_host_shutdown_reverses_contributions(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _plugin(
        paths.bundled_root / "action",
        "emoti.bundled.action",
        default_enabled=True,
        permissions=("actions.register",),
        source="""
from guanghe_companion.plugin_api import ActionDefinition, ActionResult

def activate(ctx):
    ctx.register_action(ActionDefinition(
        action_id='host.wave',
        label='挥手',
        handler=lambda request: ActionResult(speech='挥了挥手。'),
    ))
""",
    )
    host = PluginHost(paths)
    host.start()
    assert [item.action_id for item in host.runtime.list_actions()] == ["host.wave"]

    host.shutdown()

    assert host.runtime.list_actions() == ()


def test_host_clear_plugin_data_removes_local_state(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _plugin(
        paths.bundled_root / "storage",
        "emoti.bundled.storage",
        default_enabled=True,
        permissions=("storage.local",),
        source="def activate(ctx):\n    ctx.storage.set('count', 3)\n",
    )
    host = PluginHost(paths)
    host.start()
    assert host.runtime.plugin_storage("emoti.bundled.storage").get("count") == 3

    host.clear_plugin_data("emoti.bundled.storage")

    assert host.runtime.plugin_storage("emoti.bundled.storage").snapshot() == {}


def test_host_isolates_invalid_installed_manifest_and_loads_valid_bundled_plugin(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _plugin(paths.bundled_root / "core", "emoti.bundled.core", default_enabled=True)
    bad = paths.installed_root / "broken-manifest"
    bad.mkdir(parents=True)
    (bad / "emoti-plugin.json").write_text("{broken", encoding="utf-8")

    host = PluginHost(paths)
    report = host.start()

    assert report.loaded_plugin_ids == ("emoti.bundled.core",)
    assert any(failure.stage == "discovery" for failure in report.failures)


def test_host_isolates_failed_plugin_activation_and_keeps_unrelated_plugin_loaded(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _plugin(paths.bundled_root / "good", "emoti.bundled.good", default_enabled=True)
    _plugin(
        paths.bundled_root / "bad",
        "emoti.bundled.bad",
        default_enabled=True,
        source="def activate(ctx):\n    raise RuntimeError('broken activation')\n",
    )

    host = PluginHost(paths)
    report = host.start()

    assert host.runtime.loaded_plugin_ids == ("emoti.bundled.good",)
    assert any(
        failure.plugin_id == "emoti.bundled.bad" and failure.stage == "activation"
        for failure in report.failures
    )
