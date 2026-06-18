from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize a pixel-pet sequence draft run.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    payload = build_status(run_dir)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ok"] else 1


def build_status(run_dir: Path) -> dict[str, Any]:
    if not run_dir.is_dir():
        return {
            "ok": False,
            "status": "missing_run_dir",
            "run_dir": str(run_dir),
            "candidate_pack_count": 0,
            "candidate_packs": [],
        }
    candidate_root = run_dir / "character_packs_drafts"
    candidate_packs = sorted(path for path in candidate_root.glob("*") if path.is_dir()) if candidate_root.is_dir() else []
    status = "has_candidate_pack" if candidate_packs else "needs_candidate_pack"
    return {
        "ok": bool(candidate_packs),
        "status": status,
        "run_dir": str(run_dir),
        "candidate_pack_count": len(candidate_packs),
        "candidate_packs": [str(path) for path in candidate_packs],
    }


if __name__ == "__main__":
    raise SystemExit(main())
