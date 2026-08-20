from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.plugin_manifest import load_plugin_manifest  # noqa: E402


PLUGIN_SOURCE = '''from __future__ import annotations

from guanghe_companion.plugin_api import ActionDefinition, ActionResult


def activate(ctx):
    """Register this plugin's contributions and return optional cleanup."""

    ctx.register_action(
        ActionDefinition(
            action_id="{action_id}",
            label="{action_label}",
            description="A small local interaction contributed by {plugin_id}.",
            handler=lambda request: ActionResult(
                speech="星汐朝你挥了挥手。",
                motion="Default",
                payload={{"plugin_id": ctx.plugin_id}},
            ),
        )
    )
'''

README = '''# {name}

Plugin id: `{plugin_id}`

This directory follows the E-Moti plugin contract:

- `emoti-plugin.json` declares identity, compatibility, permissions, and entrypoint.
- `plugin.py` registers reversible contributions through `PluginContext`.
- The host keeps authority over game state, saves, credentials, and external side effects.

Validate locally:

```bash
python tools/validate_emoti_plugin.py {target}
```
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a minimal E-Moti plugin skeleton.")
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--id", required=True, dest="plugin_id")
    parser.add_argument("--name", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    target = args.target.resolve()
    if target.exists() and any(target.iterdir()) and not args.force:
        parser.error(f"target is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)

    action_suffix = re.sub(r"[^a-z0-9]+", ".", args.plugin_id.lower()).strip(".")
    action_id = f"{action_suffix}.hello"
    manifest = {
        "schema_version": 1,
        "id": args.plugin_id,
        "name": args.name,
        "version": "0.1.0",
        "api_version": "1",
        "entrypoint": "plugin.py:activate",
        "description": "A community E-Moti plugin.",
        "default_enabled": False,
        "permissions": ["actions.register"],
        "dependencies": [],
        "settings": {},
        "contributes": {"actions": [action_id]},
    }
    (target / "emoti-plugin.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "plugin.py").write_text(
        PLUGIN_SOURCE.format(
            action_id=action_id,
            action_label="打个招呼",
            plugin_id=args.plugin_id,
        ),
        encoding="utf-8",
    )
    (target / "README.md").write_text(
        README.format(name=args.name, plugin_id=args.plugin_id, target=target.name),
        encoding="utf-8",
    )
    load_plugin_manifest(target / "emoti-plugin.json")
    print(json.dumps({"ok": True, "target": str(target), "plugin_id": args.plugin_id}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
