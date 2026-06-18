from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.character_registry import validate_character_pack_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an E-Moti character pack.")
    parser.add_argument("pack_dir", help="Path to the character pack directory.")
    parser.add_argument("--source", default="local", help="Report source label.")
    args = parser.parse_args(argv)

    report = validate_character_pack_dir(Path(args.pack_dir), source=args.source)
    print(
        json.dumps(
            {
                "ok": report.ok,
                "character_id": report.character_id,
                "path": str(report.path),
                "source": report.source,
                "errors": list(report.errors),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
