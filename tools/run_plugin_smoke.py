from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.companion_story_runtime import CompanionStoryRuntime  # noqa: E402
from guanghe_companion.plugin_api import ActionRequest  # noqa: E402
from guanghe_companion.plugin_configuration import (  # noqa: E402
    PluginRuntimeConfiguration,
    PluginRuntimeConfigurationStore,
)
from guanghe_companion.plugin_host import PluginHost, PluginPaths  # noqa: E402
from guanghe_companion.plugin_story_bridge import PluginStoryBridge  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bundled E-Moti plugin host smoke test.")
    parser.add_argument(
        "--plugin-root",
        type=Path,
        default=REPO_ROOT / "plugins",
        help="Bundled plugin collection or one plugin root.",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="emoti-plugin-smoke-") as temporary:
        root = Path(temporary)
        paths = PluginPaths(
            bundled_root=args.plugin_root,
            installed_root=root / "user-data" / "plugins" / "installed",
            data_root=root / "user-data" / "plugins" / "data",
            configuration_path=root / "user-data" / "plugins" / "config.json",
        )
        PluginRuntimeConfigurationStore(paths.configuration_path).save(
            PluginRuntimeConfiguration(
                enabled_plugins=("emoti.bundled.stargazing",),
            )
        )
        host = PluginHost(paths)
        boot = host.start()
        runtime = host.runtime
        story = CompanionStoryRuntime.create(
            user_data_root=root / "user-data",
            character_id="xingxi",
        )
        bridge = PluginStoryBridge(story=story, plugins=runtime, character_id="xingxi")

        first = bridge.execute_action(
            ActionRequest(action_id="stargazing.watch", character_id="xingxi", now=100)
        )
        second = bridge.execute_action(
            ActionRequest(action_id="stargazing.watch", character_id="xingxi", now=200)
        )
        context, _bundle, assembly = bridge.build_expression_context(
            {"pet": {"mood": 70, "trust": 8}},
            query="今晚想看星星",
            now=300,
            relationship_stage="初识",
            state_snapshot={"coins": 20, "inventory": {}},
        )
        panel = runtime.build_ui_panel_model("stargazing.panel", character_id="xingxi")
        memories = story.memory.store.load_memories()
        service_ids = {row.service_id for row in runtime.list_service_definitions()}
        catalog = {row.plugin_id: row for row in host.catalog()}
        before_unload = {
            "actions": [item.action_id for item in runtime.list_actions()],
            "panels": [item.panel_id for item in runtime.list_ui_panels()],
            "services": sorted(service_ids),
        }
        host.shutdown()
        after_unload = {
            "actions": [item.action_id for item in runtime.list_actions()],
            "panels": [item.panel_id for item in runtime.list_ui_panels()],
            "services": [item.service_id for item in runtime.list_service_definitions()],
        }

        expected_services = {
            "emoti.llm.expression",
            "emoti.voice.tts",
            "emoti.voice.asr",
            "emoti.context.screen-summary",
            "emoti.context.web-search",
        }
        checks = {
            "host_discovered_plugins": set(boot.discovered_plugin_ids)
            == {"emoti.core.capability-contracts", "emoti.bundled.stargazing", "emoti.bundled.local-expression-fallback"},
            "host_loaded_plugins": set(boot.loaded_plugin_ids)
            == {"emoti.core.capability-contracts", "emoti.bundled.stargazing", "emoti.bundled.local-expression-fallback"},
            "first_action_count": first.execution.payload.get("count") == 1,
            "first_memory_created": len(first.memory_ids) == 1,
            "second_action_count": second.execution.payload.get("count") == 2,
            "duplicate_memory_avoided": second.memory_ids == (),
            "memory_title": len(memories) == 1 and memories[0].title == "第一次一起看星星",
            "context_namespaced": (
                context.get("plugin_context", {})
                .get("emoti.bundled.stargazing:stargazing.status", {})
                .get("times")
                == 2
            ),
            "context_failures": not assembly.failures,
            "ui_panel_model": panel.get("times") == 2,
            "service_contracts_registered": service_ids == expected_services,
            "catalog_available": set(catalog)
            == {"emoti.core.capability-contracts", "emoti.bundled.stargazing", "emoti.bundled.local-expression-fallback"},
            "catalog_needs_no_sensitive_review": all(
                not row.needs_permission_review for row in catalog.values()
            ),
            "reversible_before_unload": before_unload == {
                "actions": ["stargazing.watch"],
                "panels": ["stargazing.panel"],
                "services": sorted(expected_services),
            },
            "reversible_after_unload": after_unload
            == {"actions": [], "panels": [], "services": []},
        }
        report = {
            "ok": all(checks.values()),
            "plugin_api_version": "1",
            "boot": boot.to_dict(),
            "checks": checks,
            "first_execution": {
                "speech": first.execution.speech,
                "memory_ids": list(first.memory_ids),
            },
            "second_execution": {
                "speech": second.execution.speech,
                "memory_ids": list(second.memory_ids),
            },
            "memory_count": len(memories),
            "context_section_ids": list(assembly.sections),
            "panel": dict(panel),
            "service_ids": sorted(service_ids),
            "catalog": [row.to_dict() for row in catalog.values()],
            "private_data_in_report": False,
        }

    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
