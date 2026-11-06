from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import fields, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from guanghe_companion.character_pack import load_default_character_pack
from guanghe_companion.emotional_memory import EmotionalMemoryEntry
from guanghe_companion.expression_clients import MAX_OPENAI_PROMPT_LENGTH
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.persona import build_persona_payload
from tools.eval_ondemand_generation import render_prompt
from tools.eval_ondemand_memory import (
    digest, evidence_representations, git, load_datasets, provider_evidence_payload,
    score_query, source_hashes, summarize,
)

PRESENTATION_VERSION = "current-production-expression-v1"


def json_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_rows(data, story_id):
    result = {}
    for raw in data["memories"]:
        if raw["story_id"] != story_id:
            continue
        values = {key: value for key, value in raw.items() if key not in {"id", "story_id", "state"}}
        values.update(memory_id=raw["id"])
        values.setdefault("owner_id", data["owner_id"])
        values.setdefault("character_id", data["character_id"])
        entry = EmotionalMemoryEntry(**values).normalized()
        entry.validate()
        result[raw["id"]] = {**raw, "_expected_fingerprint": entry.evidence_fingerprint()}
    return result


def common_persona(character_id):
    persona = build_persona_payload(replace(load_default_character_pack(), character_id=character_id))
    request = ExpressionRequest.from_snapshot({"character_name": persona["character_name"], "focus": 50,
        "charge": 50, "stability": 50, "mood": 50, "trust": 50}, context={"persona": persona})
    return request.persona


def normalize_artifact(path, datasets):
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "presentation" in raw:
        raise ValueError("input is already presentation-normalized")
    by_split = {data["split"]: data for data in datasets}
    for split, expected in raw["dataset_sha256"].items():
        if split not in by_split or by_split[split]["dataset_sha256"] != expected:
            raise ValueError("input dataset differs from the frozen retrieval dataset")
    if raw["budget"]["expression_memory_chars"] != 6000 or raw["budget"]["final_provider_prompt_chars"] != MAX_OPENAI_PROMPT_LENGTH:
        raise ValueError("retrieval artifact uses a different expression budget")
    result = deepcopy(raw)
    result["original_retrieval"] = {"path": str(path.resolve()), "sha256": digest(path),
        "summary": deepcopy(raw.get("summary")), "by_split": deepcopy(raw.get("by_split")),
        "by_family": deepcopy(raw.get("by_family"))}
    personas = {split: common_persona(data["character_id"]) for split, data in by_split.items()}
    sources = {(split, story["id"]): source_rows(data, story["id"])
               for split, data in by_split.items() for story in data["stories"]}
    queries = {(split, query["id"]): query for split, data in by_split.items() for query in data["queries"]}
    allowed = {field.name for field in fields(ExpressionRequest)}
    normalized = []
    for old in raw["rows"]:
        split = old["split"]
        data = by_split[split]
        query = queries[(split, old["query_id"])]
        for key, actual in (("story_id", old["story_id"]), ("text", old["query"]),
                            ("gold_ids", old["gold_ids"]), ("forbidden_ids", old["forbidden_ids"])):
            if query[key] != actual:
                raise ValueError("retrieval query does not match the frozen dataset")
        payload = old.get("actual_expression_request")
        if not isinstance(payload, dict) or not payload or set(payload) - allowed:
            raise ValueError("missing or invalid saved ExpressionRequest")
        request = ExpressionRequest(**payload)
        persona = personas[split]
        request = replace(request, persona=deepcopy(persona), character_name=persona["character_name"])
        updated_payload = request.to_prompt_dict()
        started = perf_counter()
        prompt = render_prompt(updated_payload)
        elapsed = (perf_counter() - started) * 1000
        final_payload = provider_evidence_payload(prompt)
        score = score_query(query, final_payload, old["retrieved_ids"], deepcopy(old["trace"]),
                            sources[(split, old["story_id"])], error=old.get("error"))
        original_delivery = {key: deepcopy(old[key]) for key in score if key in old and key != "actual_expression_request"}
        row = {**deepcopy(old), **score, "original_delivery": original_delivery,
            "original_provider_prompt_sha256": hashlib.sha256(old.get("actual_provider_prompt", "").encode()).hexdigest(),
            "actual_expression_request": updated_payload, "actual_provider_prompt": prompt,
            "actual_provider_payload": final_payload, "provider_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "provider_prompt_chars": len(prompt), "presentation_assembly_ms": elapsed,
            "presentation_persona_sha256": json_digest(persona)}
        before_ids = list(dict.fromkeys(mid for rep in evidence_representations(updated_payload) for mid in rep["ids"]))
        row.update(expression_request_delivered_ids=before_ids,
                   provider_lost_evidence_ids=sorted(set(before_ids) - set(score["delivered_ids"])),
                   provider_retrieval_status=final_payload.get("emotional_memory", {}).get("retrieval", {}).get("status"),
                   persona_config_delivered=final_payload.get("persona", {}).get("config_hash") == persona.get("config_hash"),
                   persona_config_unchanged=True)
        allowed_scopes = {"task_experience" if route == "task" else "companion" for route in query["expected_routes"]}
        row["scope_or_owner_ineligible_ids"] = [mid for mid in row["all_context_evidence_ids"]
            if mid in sources[(split, old["story_id"])] and (
                sources[(split, old["story_id"])][mid].get("owner_id", data["owner_id"]) != data["owner_id"]
                or sources[(split, old["story_id"])][mid].get("character_id", data["character_id"]) != data["character_id"]
                or sources[(split, old["story_id"])][mid].get("scope", "companion") not in allowed_scopes)]
        # 旧 tokenizer 数值对应旧 prompt，不能继续作为新展示的测量值。
        if "bge_tokenizer_prompt_tokens" in row:
            row["original_bge_tokenizer_prompt_tokens"] = row.pop("bge_tokenizer_prompt_tokens")
        normalized.append(row)
    result["rows"] = normalized
    result["summary"] = summarize(normalized)
    result["by_split"] = {split: summarize([row for row in normalized if row["split"] == split])
                          for split in sorted({row["split"] for row in normalized})}
    result["by_family"] = {family: summarize([row for row in normalized if row["family"] == family])
                           for family in sorted({row["family"] for row in normalized})}
    result["presentation"] = {"version": PRESENTATION_VERSION, "normalized_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(ROOT), "source_commit": git(ROOT, "rev-parse", "HEAD"), "source_sha256": source_hashes(ROOT),
        "script_sha256": digest(Path(__file__)), "persona_sha256": {split: json_digest(value) for split, value in personas.items()},
        "changed_fields": ["persona", "character_name"], "retrieval_reexecuted": False, "model_requests": 0,
        "evidence_source": "original saved ExpressionRequest; memory and selected IDs unchanged",
        "scoring": "score_query applied to the rebuilt final provider prompt; original metrics retained",
        "timing_note": "retrieval timings remain original; presentation_assembly_ms is measured separately",
        "budget": {"expression_memory_chars": 6000, "final_provider_prompt_chars": MAX_OPENAI_PROMPT_LENGTH}}
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild saved retrieval requests with one current expression presentation, without rerunning retrieval.")
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--splits", nargs="+", choices=("development", "validation", "holdout"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def run(args):
    datasets = load_datasets(args.dataset_dir, args.splits)
    outputs = [args.output_dir / path.name for path in args.input]
    if len({path.resolve() for path in outputs}) != len(outputs):
        raise ValueError("input artifact names collide")
    for path in outputs:
        if path.exists():
            raise FileExistsError(path)
    results = [normalize_artifact(path, datasets) for path in args.input]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path, result in zip(outputs, results):
        with path.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    return outputs


if __name__ == "__main__":
    written = run(parse_args())
    print(json.dumps({"status": "completed", "outputs": [str(path) for path in written]}, ensure_ascii=False))
