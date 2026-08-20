from __future__ import annotations

import json
from pathlib import Path

import pytest

from guanghe_companion.plugin_configuration import (
    PluginConfigurationError,
    PluginRuntimeConfiguration,
    PluginRuntimeConfigurationStore,
)
from guanghe_companion.plugin_manifest import discover_plugin_candidates
from guanghe_companion.plugin_runtime import PluginRuntime


def _plugin(root: Path, plugin_id: str, *, default_enabled: bool, permissions: list[str] | None = None) -> None:
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
                "default_enabled": default_enabled,
                "permissions": permissions or ["storage.local"],
                "dependencies": [],
                "settings": {"copy": "default", "nested": {"x": 1}},
            }
        ),
        encoding="utf-8",
    )
    (root / "plugin.py").write_text(
        "def activate(ctx):\n    ctx.storage.set('settings', dict(ctx.settings))\n",
        encoding="utf-8",
    )


def test_configuration_roundtrip_and_effective_enabled(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    store = PluginRuntimeConfigurationStore(path)
    config = PluginRuntimeConfiguration(
        enabled_plugins=("emoti.optin",),
        disabled_plugins=("emoti.default",),
        permission_grants={"emoti.net": ("network.http",)},
        plugin_settings={"emoti.optin": {"copy": "override"}},
    )

    store.save(config)
    loaded = store.load()

    assert loaded.enabled_plugins == ("emoti.optin",)
    assert loaded.disabled_plugins == ("emoti.default",)
    assert loaded.permission_grants["emoti.net"] == ("network.http",)
    assert loaded.plugin_settings["emoti.optin"]["copy"] == "override"


def test_configuration_rejects_inline_credentials(tmp_path: Path) -> None:
    store = PluginRuntimeConfigurationStore(tmp_path / "plugins.json")

    with pytest.raises(PluginConfigurationError, match="credential"):
        store.save(
            PluginRuntimeConfiguration(
                plugin_settings={"emoti.bad": {"api_key": "secret-value"}}
            )
        )


def test_runtime_load_configured_respects_opt_in_opt_out_and_settings_override(tmp_path: Path) -> None:
    collection = tmp_path / "plugins"
    _plugin(collection / "default", "emoti.default", default_enabled=True)
    _plugin(collection / "optin", "emoti.optin", default_enabled=False)
    candidates = discover_plugin_candidates([collection])
    config = PluginRuntimeConfiguration(
        enabled_plugins=("emoti.optin",),
        disabled_plugins=("emoti.default",),
        plugin_settings={"emoti.optin": {"copy": "override", "nested": {"y": 2}}},
    )
    runtime = PluginRuntime.from_configuration(data_root=tmp_path / "data", configuration=config)

    loaded = runtime.load_configured(candidates, configuration=config)

    assert loaded == ("emoti.optin",)
    settings = runtime.plugin_storage("emoti.optin").get("settings")
    assert settings["copy"] == "override"
    assert settings["nested"] == {"y": 2}


def test_configuration_invalid_json_falls_back_to_empty_with_warning(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    path.write_text("{broken", encoding="utf-8")
    store = PluginRuntimeConfigurationStore(path)

    config = store.load()

    assert config == PluginRuntimeConfiguration()
    assert store.last_warning
