#!/usr/bin/env python3
"""Preflight benchmark sources through the real Entry schema, without queries.

python validate_fixture.py --source-root /path/to/E-Moti \
  --dataset-dir /path/to/fixtures --output /path/to/preflight.json
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_root / "src"))
    from guanghe_companion.emotional_memory import EmotionalMemoryEntry
    report = {"status": "passed", "source_root": str(args.source_root), "rows": [],
              "dataset_hashes": {}, "retrieval_queries_executed": 0, "generation_requests": 0}
    for path in sorted(args.dataset_dir.glob("ondemand_memory_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "memories" not in data:
            continue
        report["dataset_hashes"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        for raw in data["memories"]:
            fields = {k: v for k, v in raw.items() if k not in {"id", "story_id", "state"}}
            fields.update(memory_id=raw["id"])
            fields.setdefault("owner_id", data["owner_id"])
            fields.setdefault("character_id", data["character_id"])
            row = {"memory_id": raw["id"], "split": data["split"], "status": "passed"}
            try:
                entry = EmotionalMemoryEntry(**fields).normalized()
                entry.validate()
                if raw.get("state") == "forgotten":
                    probes = (0, entry.valid_from, data["now"], 4_000_000_000)
                    if any(entry.is_active(now=t, scope=entry.scope) for t in probes):
                        raise ValueError("forgotten source became eligible at a time probe")
                    row["forgotten_ineligible_time_probes"] = list(probes)
            except (TypeError, ValueError) as exc:
                row.update(status="failed", reason=str(exc),
                           valid_from=raw.get("valid_from"), valid_until=raw.get("valid_until"))
                report["status"] = "failed"
            report["rows"].append(row)
    report["source_count"] = len(report["rows"])
    report["failed_count"] = sum(row["status"] == "failed" for row in report["rows"])
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "source_count", "failed_count", "retrieval_queries_executed")}))
    return report["status"] != "passed"


if __name__ == "__main__":
    sys.exit(main())
