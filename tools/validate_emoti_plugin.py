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

from guanghe_companion.plugin_api import SENSITIVE_PLUGIN_PERMISSIONS  # noqa: E402
from guanghe_companion.plugin_manifest import (  # noqa: E402
    PLUGIN_MANIFEST_NAME,
    PluginManifestError,
    discover_plugin_candidates,
    load_plugin_manifest,
)
from guanghe_companion.plugin_runtime import PluginRuntime, PluginRuntimeError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an E-Moti plugin package.")
    parser.add_argument("plugin", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Import and activate the plugin in a temporary runtime. Only use for trusted source.",
    )
    args = parser.parse_args()

    plugin_root = args.plugin.resolve()
    manifest_path = plugin_root if plugin_root.name == PLUGIN_MANIFEST_NAME else plugin_root / PLUGIN_MANIFEST_NAME
    report: dict[str, object] = {
        "ok": False,
        "plugin_root": str(plugin_root),
        "manifest": str(manifest_path),
        "activated": False,
        "errors": [],
    }
    try:
        manifest = load_plugin_manifest(manifest_path)
        report.update(
            {
                "plugin_id": manifest.plugin_id,
                "name": manifest.name,
                "version": manifest.version,
                "api_version": manifest.api_version,
                "permissions": sorted(permission.value for permission in manifest.permissions),
                "dependencies": [
                    {"id": dep.plugin_id, "optional": dep.optional}
                    for dep in manifest.dependencies
                ],
            }
        )
        if args.activate:
            # Validate the target together with its required sibling dependencies.
            # A plugin such as ``local_expression_fallback`` depends on the bundled
            # capability-contract plugin and should activate successfully when the
            # complete plugin directory is available.
            discovery_root = plugin_root.parent if plugin_root.is_dir() else plugin_root.parent.parent
            candidates = discover_plugin_candidates([discovery_root])
            by_id = {candidate.manifest.plugin_id: candidate for candidate in candidates}
            target_candidate = by_id.get(manifest.plugin_id)
            if target_candidate is None:
                # A standalone package outside a plugin collection remains valid.
                standalone = discover_plugin_candidates([plugin_root])
                if not standalone:
                    raise PluginManifestError(f"plugin candidate was not discovered: {plugin_root}")
                target_candidate = standalone[0]
                candidates = tuple(standalone)
                by_id = {target_candidate.manifest.plugin_id: target_candidate}

            required_ids: set[str] = {manifest.plugin_id}

            def include_dependencies(plugin_id: str) -> None:
                candidate = by_id.get(plugin_id)
                if candidate is None:
                    raise PluginRuntimeError(f"required plugin dependency was not discovered: {plugin_id}")
                for dependency in candidate.manifest.dependencies:
                    if dependency.optional:
                        continue
                    if dependency.plugin_id not in required_ids:
                        required_ids.add(dependency.plugin_id)
                        include_dependencies(dependency.plugin_id)

            include_dependencies(manifest.plugin_id)
            relevant = tuple(candidate for candidate in candidates if candidate.manifest.plugin_id in required_ids)
            grants = {
                candidate.manifest.plugin_id: candidate.manifest.permissions.intersection(
                    SENSITIVE_PLUGIN_PERMISSIONS
                )
                for candidate in relevant
            }
            with tempfile.TemporaryDirectory(prefix="emoti-plugin-validate-") as temporary:
                runtime = PluginRuntime(data_root=Path(temporary), permission_grants=grants)
                load_order = runtime.load_all(relevant, enabled_ids={manifest.plugin_id})
                report["activated"] = True
                report["load_order"] = list(load_order)
                report["contributions"] = {
                    "actions": [item.action_id for item in runtime.list_actions()],
                    "skills": [item.skill_id for item in runtime.list_skills()],
                    "ui_panels": [item.panel_id for item in runtime.list_ui_panels()],
                }
                runtime.shutdown()
        report["ok"] = True
    except (PluginManifestError, PluginRuntimeError, OSError, ValueError) as exc:
        report["errors"] = [f"{type(exc).__name__}: {exc}"]

    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
