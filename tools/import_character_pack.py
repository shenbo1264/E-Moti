from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.character_pack_import import import_character_pack_dir


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a validated E-Moti character pack into a user pack root.")
    parser.add_argument("source_dir", help="Path to a complete character pack directory.")
    parser.add_argument(
        "--target-root",
        required=True,
        help="Destination character_packs root. The pack is copied into <target-root>/<character_id>.",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing target pack with the same id.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = import_character_pack_dir(
        Path(args.source_dir),
        target_root=Path(args.target_root),
        force=args.force,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
