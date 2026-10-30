from __future__ import annotations

"""Measure ordinary-chat memory behaviour through the real controller path.

Everything here is local: no model is called, so persona cases always report
not_run. A case passes only on what is actually in the memory store or recall.
"""

import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_settings import ExpressionSettingsStore
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController

DATASET = ROOT / "tests" / "fixtures" / "companion_acceptance.json"


def load_dataset(path: Path = DATASET) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("kind") != "synthetic_companion_acceptance" or payload.get("version") != 1:
        raise ValueError("unsupported acceptance dataset")
    ids = [case["id"] for case in payload["cases"]]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("acceptance cases must be nonempty with unique ids")
    return payload


def open_controller(root: Path) -> PluginEnabledCompanionController:
    return PluginEnabledCompanionController(
        user_data_root=root, ai_expressor=ShinsekaiAIExpressor(enabled=False),
        expression_settings_store=ExpressionSettingsStore(root / "disabled-expression.json"))


def active_text(controller) -> str:
    memory = controller.story_runtime.memory
    memory.store.expire_memories(now=int(controller.now))
    rows = [row for row in memory.store.load_memories()
            if not row.deleted and row.is_active(now=int(controller.now), scope=row.scope)]
    return "\n".join(f"{row.title} {row.summary}" for row in rows)


def pending_text(controller) -> str:
    album = controller.memory_album_controller.snapshot(now=int(controller.now))
    return "\n".join(row["summary"] for row in album.get("pending_candidates", []))


def run_case(case: dict, root: Path) -> dict:
    if case["category"] == "persona":
        return {"id": case["id"], "category": "persona", "status": "not_run", "rubric": case["rubric"]}
    controller = open_controller(root)
    try:
        controller.now = 100
        for text in case.get("seed", []):
            controller.memory_album_controller.remember_explicit(
                text, now=int(controller.now),
                expected_epoch=controller.story_runtime.memory.store.context_epoch)
        for offset, text in enumerate(case.get("chat", []), 1):
            controller.now = 100 + offset * 100
            controller.submit_dialogue_request(DialogueRequest(text=text, source="acceptance"),
                                               include_ai_expression=False)
        if case.get("reopen"):
            controller.close()
            controller = open_controller(root)
        controller.now = 10000
        stored, pending = active_text(controller), pending_text(controller)
        recalled = ""
        if "query" in case:
            rows = controller.story_runtime.memory.recall(case["query"], now=int(controller.now), top_k=4)
            recalled = "\n".join(row.summary for row in rows)
        missing = [t for t in case.get("stored", []) if t not in stored]
        leaked = [t for t in case.get("not_stored", []) if t in stored or t in pending]
        unrecalled = [t for t in case.get("recalled", []) if t not in recalled]
        return {"id": case["id"], "category": case["category"],
                "status": "pass" if not (missing or leaked or unrecalled) else "fail",
                "missing": missing, "leaked": leaked, "unrecalled": unrecalled,
                "stored": stored, "pending": pending, "recalled": recalled}
    finally:
        controller.close()


def run_all(dataset: dict) -> dict:
    results = []
    for case in dataset["cases"]:
        with tempfile.TemporaryDirectory(prefix="emoti-acceptance-") as temp:
            results.append(run_case(case, Path(temp)))
    summary: dict[str, dict[str, int]] = {}
    for row in results:
        bucket = summary.setdefault(row["category"], {"pass": 0, "fail": 0, "not_run": 0})
        bucket[row["status"]] += 1
    return {"dataset_version": dataset["version"], "model": "not_run", "summary": summary, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_all(load_dataset())
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
