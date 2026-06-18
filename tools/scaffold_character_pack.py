from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.character_session import is_safe_character_id


ALLOWED_BOUNDARIES = ("shareable_after_review", "local_ugc_only", "private_local_fanwork")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local character-pack scaffold.")
    parser.add_argument("--character-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--distribution-boundary", choices=ALLOWED_BOUNDARIES, default="private_local_fanwork")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    if not is_safe_character_id(args.character_id):
        parser.error("unsafe character id")

    pack_dir = Path(args.output_root) / args.character_id
    pack_dir.mkdir(parents=True, exist_ok=False)
    (pack_dir / "preview").mkdir()
    (pack_dir / "item_icons").mkdir()

    _write_json(
        pack_dir / "character.json",
        {
            "character_id": args.character_id,
            "name": args.name,
            "title": args.title,
            "description": "Local character-pack scaffold. Replace placeholder art before import.",
            "spritesheet": "spritesheet.png",
            "motion_manifest": "motion_manifest.json",
            "renderer": {"backend": "sprite", "motion_map": {}, "expression_map": {}},
            "default_mode": "Calm",
            "modes": ["Calm"],
            "mode_descriptions": {"Calm": "Stable local test mode."},
            "motion_labels": {"Default": "Idle"},
            "distribution_boundary": args.distribution_boundary,
            "relationship_decorations": [],
        },
    )
    _write_json(
        pack_dir / "dialogue_style.json",
        {
            "voice": "local test companion",
            "tone": "gentle",
            "taboos": ["Do not claim bundled distribution rights."],
        },
    )
    _write_json(
        pack_dir / "motion_manifest.json",
        {
            "sheet_columns": 1,
            "sheet_rows": 9,
            "frame_width": 192,
            "frame_height": 208,
            "background": "transparent",
            "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
        },
    )
    _write_json(pack_dir / "shop_items.json", [])
    (pack_dir / "provenance.md").write_text(
        "# Provenance\n\nGenerated as a local scaffold. Replace placeholder metadata before distribution review.\n",
        encoding="utf-8",
    )
    (pack_dir / "LICENSE.md").write_text(
        "# License\n\nLocal scaffold only. Add rights information before distribution.\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "path": str(pack_dir)}, ensure_ascii=False))
    return 0


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
