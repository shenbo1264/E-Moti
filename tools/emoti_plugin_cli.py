from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from guanghe_companion.plugin_center_controller import PluginCenterController
from guanghe_companion.plugin_subsystem import PluginSubsystem


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage E-Moti local plugins without opening the GUI.")
    parser.add_argument("--app-root", type=Path, default=Path.cwd())
    parser.add_argument("--user-data-root", type=Path, default=Path.cwd() / "data")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    for name in ("enable", "disable", "clear-data", "clear-quarantine", "uninstall"):
        cmd = sub.add_parser(name); cmd.add_argument("plugin_id")
    install = sub.add_parser("install"); install.add_argument("archive", type=Path)
    settings = sub.add_parser("settings"); settings.add_argument("plugin_id"); settings.add_argument("json_object")
    args = parser.parse_args(argv)

    subsystem = PluginSubsystem(application_root=args.app_root, user_data_root=args.user_data_root)
    subsystem.start()
    center = PluginCenterController(subsystem)
    try:
        if args.command == "list":
            result = center.snapshot()
            ok = True
        elif args.command == "enable":
            result = center.set_enabled(args.plugin_id, True).to_dict(); ok = bool(result["ok"])
        elif args.command == "disable":
            result = center.set_enabled(args.plugin_id, False).to_dict(); ok = bool(result["ok"])
        elif args.command == "clear-data":
            result = center.clear_data(args.plugin_id).to_dict(); ok = bool(result["ok"])
        elif args.command == "clear-quarantine":
            result = center.clear_quarantine(args.plugin_id).to_dict(); ok = bool(result["ok"])
        elif args.command == "uninstall":
            result = center.uninstall(args.plugin_id).to_dict(); ok = bool(result["ok"])
        elif args.command == "install":
            result = center.install(args.archive).to_dict(); ok = bool(result["ok"])
        else:
            payload = json.loads(args.json_object)
            if not isinstance(payload, dict):
                raise ValueError("settings must be a JSON object")
            result = center.set_settings(args.plugin_id, payload).to_dict(); ok = bool(result["ok"])
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if ok else 3
    finally:
        subsystem.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
