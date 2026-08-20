from __future__ import annotations

import json
from pathlib import Path

from guanghe_companion.plugin_catalog_view_model import build_plugin_catalog
from guanghe_companion.plugin_configuration import PluginRuntimeConfiguration
from guanghe_companion.plugin_manifest import discover_plugin_candidates
from guanghe_companion.plugin_runtime import PluginRuntime


def _plugin(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "emoti-plugin.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "emoti.catalog",
                "name": "Catalog Plugin",
                "version": "0.1.0",
                "api_version": "1",
                "entrypoint": "plugin.py:activate",
                "default_enabled": False,
                "permissions": ["actions.register", "network.http"],
                "dependencies": [],
                "contributes": {"actions": ["catalog.action"]},
            }
        ),
        encoding="utf-8",
    )
    (root / "plugin.py").write_text("def activate(ctx):\n    pass\n", encoding="utf-8")


def test_catalog_marks_sensitive_permissions_and_current_state(tmp_path: Path) -> None:
    root = tmp_path / "plugin"
    _plugin(root)
    candidates = discover_plugin_candidates([root])
    config = PluginRuntimeConfiguration(enabled_plugins=("emoti.catalog",))
    runtime = PluginRuntime.from_configuration(data_root=tmp_path / "data", configuration=config)

    items = build_plugin_catalog(candidates, runtime=runtime, configuration=config)

    assert len(items) == 1
    item = items[0]
    assert item.plugin_id == "emoti.catalog"
    assert item.enabled is True
    assert item.state == "not_loaded"
    assert item.needs_permission_review is True
    assert item.sensitive_permissions == ("network.http",)
    assert item.contributes["actions"] == ("catalog.action",)
