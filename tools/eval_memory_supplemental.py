from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from guanghe_companion.emotional_memory import EmotionalMemoryEntry, EmotionalMemoryStore, CoreBondProfile, MemoryContextBundle
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_hierarchy import build_layers
from guanghe_companion.memory_source_spans import source_span_metadata
from guanghe_companion.retrieval_contract import RetrievalBudget


def stamp(value):
    return int(datetime.fromisoformat(value).timestamp())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def configure_judge(service, config):
    if config is None:
        return
    from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge
    service.evidence_judge = MemoryEvidenceJudge(config["client"])
    if config["model_cache"]:
        from guanghe_companion.semantic_memory import SemanticMemoryRetriever
        service.semantic_retriever = SemanticMemoryRetriever(cache_dir=config["model_cache"],
            character_id=service.character_id, owner_id=service.owner_id, local_files_only=True)
        service.semantic_retriever.warmup().result(timeout=180)


def close_service(service):
    service.close()
    if service.semantic_retriever is not None:
        service.semantic_retriever.close()


def recorded_requests(config, start):
    if config is None:
        return []
    from tools.eval_ondemand_generation import redact
    return redact(config["meter"].records[start:], config["secret"])


def prepare_query(service, text, now):
    started = perf_counter()
    prepared = service.prepare_retrieval(text, now=now)
    if prepared is not None:
        prepared.result(timeout=180)
    return {"prepare_latency_ms": (perf_counter() - started) * 1000,
            "judge_status": service.evidence_judge.status if service.evidence_judge is not None else "not_run"}


def entry(row, now, *, shared=False):
    event = "event_id" in row or shared
    meta = {}
    if event:
        meta = {"event_status": "planned" if row.get("source_kind") == "plan" else "completed",
                "participants": ["user:self", "character:self"]}
        meta.update({key: row[key] for key in ("event_id", "user_accepted") if key in row})
    created = row.get("created_at", now)
    return EmotionalMemoryEntry(row["id"], "sealed_supplemental", "local_user",
        "共同经历" if event else "用户事实", row["text"][:36], row["text"],
        row.get("source_kind", "explicit_user_request"), row.get("occurred_at", created), created, created,
        source_ids=("supplemental:" + row["id"],), user_confirmed=True, metadata=meta,
        valid_from=stamp(row["valid_from_iso"]) if row.get("valid_from_iso") else 0,
        valid_until=stamp(row["valid_until_iso"]) if row.get("valid_until_iso") else 0)


def run_scenario(spec, root, config=None):
    now = spec.get("now", 500 if spec["time_basis"] == "logical" else stamp("2026-11-01T12:00:00+08:00"))
    seed = [entry(row, now, shared=spec["scenario_id"] == "v3_legacy_time_not_calendar") for row in spec.get("seed", ())]
    legacy = spec["scenario_id"] == "v3_legacy_time_not_calendar"
    legacy_payload = None
    if legacy:
        store = EmotionalMemoryStore(root, "sealed_supplemental")
        legacy_payload = {"schema_version": 1, "entries": [row.to_dict() for row in seed]}
        write(store.memories_path, legacy_payload)
    service = EmotionalMemoryService(root=root, character_id="sealed_supplemental",
        time_basis=spec["time_basis"], timezone_name=spec.get("timezone"))
    configure_judge(service, config)
    if not legacy:
        service.store.save_memories(seed)
    original = {row.memory_id: row for row in seed}
    aliases = {row.memory_id: row.memory_id for row in seed}
    latest = next(iter(aliases), None)
    initial_epoch = service.store.context_epoch
    records = []
    for number, operation in enumerate(spec["operations"]):
        if operation.get("now_iso"):
            now = stamp(operation["now_iso"])
        op = operation["op"]
        checks, unsupported = {}, []
        actual, payload = {}, {}
        request_start = len(config["meter"].records) if config else 0
        before = [row.to_dict() for row in service.store.load_memories()]
        try:
            if op == "save_both_claims":
                for claim in spec["claims"]:
                    assert spec["source_text"][claim["start"]:claim["end"]] == claim["text"]
                    metadata = {"fact_subject": claim["subject"], "fact_predicate": claim["predicate"],
                        "fact_slot": claim["predicate"], "fact_domain": claim["predicate"], "fact_value": claim["value"],
                        "message_id": "source:two-claims", "original_quote": spec["source_text"],
                        **source_span_metadata(spec["source_text"], claim["text"], start=claim["start"])}
                    saved = service.remember(kind="用户事实", title=claim["text"], summary=claim["text"],
                        source="explicit_user_request", source_ids=("source:" + claim["id"],), metadata=metadata, now=now)
                    aliases[claim["id"]] = saved.memory_id
                    original[claim["id"]] = saved
                initial_epoch = service.store.context_epoch
            elif op == "forget":
                service.forget(aliases[operation["target_id"]], now=now)
            elif op in {"expand_source", "stale_expand"}:
                target = original[operation["target_id"]]
                result = service.expand_sources({target.memory_id: target.evidence_fingerprint()}, now=now,
                    expected_epoch=initial_epoch if op == "stale_expand" else service.store.context_epoch)
                payload = result.bundle.to_prompt_payload()
                actual["trace"] = asdict(result.trace)
            elif op == "query":
                actual.update(prepare_query(service, operation["text"], now))
                result = service.retrieve(operation["text"], now=now)
                payload = result.bundle.to_prompt_payload()
                actual.update(trace=asdict(result.trace), plan=asdict(result.plan), model_answer_status="not_run")
            elif op == "restart":
                close_service(service)
                service = EmotionalMemoryService(root=root, character_id="sealed_supplemental")
                configure_judge(service, config)
            elif op == "change":
                target = aliases[operation["target_id"]]
                saved = service.change(target, title="用户更新", summary=operation["text"], now=now,
                    effective_at=stamp(operation["effective_at_iso"]))
                latest = saved.memory_id
            elif op == "correct":
                saved = service.correct(latest, title="用户更正", summary=operation["text"], now=now)
                latest = saved.memory_id
            elif op == "expire":
                service.store.expire_memories(now=now)
            elif op == "migrate_copy":
                actual["legacy_input_unchanged"] = json.loads(service.store.memories_path.read_text(encoding="utf-8")) == legacy_payload
            elif op == "physical_delete":
                actual["purged_ids"] = list(service.purge(aliases[operation["target_id"]], now=now))
                replay = service.store.upsert_memory(original[operation["target_id"]])
                actual["replayed_entry_deleted"] = replay.deleted
            elif op == "forget_subject_field":
                matches = [row for row in service.store.load_memories() if not row.deleted
                    and row.metadata.get("fact_subject") == operation["subject"]
                    and row.metadata.get("fact_predicate") == operation["predicate"]]
                actual["matched_ids"] = [row.memory_id for row in matches]
                for row in matches:
                    service.forget(row.memory_id, now=now)
                checks["subject_field_resolved"] = bool(matches)
            elif op in {"consolidate", "forget_event"}:
                if op == "consolidate":
                    actual["consolidation"] = str(service.consolidate(now=now, shared_only=True))
                else:
                    for row in service.store.load_memories():
                        if row.metadata.get("event_id") == operation["event_id"]:
                            service.forget(row.memory_id, now=now)
            else:
                raise ValueError("unsupported operation: " + op)
            rows = service.store.load_memories()
            active = [row for row in rows if row.is_active(now=now)]
            if not payload:
                payload = MemoryContextBundle(CoreBondProfile(service.character_id, service.owner_id),
                    tuple(active), context_epoch=service.store.context_epoch).to_prompt_payload()
            expected = operation.get("expected", {})
            visible = json.dumps(payload, ensure_ascii=False)
            active_ids = {next((alias for alias, key in aliases.items() if key == row.memory_id), row.memory_id) for row in active}
            selected = {row["memory_id"] for row in payload.get("shared_memories", ())}
            selected.update(row["source_memory_id"] for row in payload.get("memory_overview", {}).get("claims", ()))
            for key, value in expected.items():
                if key == "active_ids": checks[key] = active_ids == set(value)
                elif key in {"required_literals", "forbidden_literals"}:
                    checks[key] = all((literal in visible) == (key == "required_literals") for literal in value)
                elif key == "current_literal": checks[key] = value in visible
                elif key == "retained_ids": checks[key] = set(value) <= active_ids
                elif key == "not_current": checks[key] = not set(value).intersection(active_ids)
                elif key == "required_source_ids": checks[key] = {aliases.get(item, item) for item in value} <= selected
                elif key == "status": checks[key] = payload.get("retrieval", {}).get("status") == value
                elif key == "old_history_allowed": checks[key] = any(row.memory_id == aliases["collect_old"] and not row.deleted for row in rows)
                elif key == "history_allowed": checks[key] = bool(selected)
                elif key == "original_logical_times_preserved": checks[key] = all((row.occurred_at, row.created_at) == (300, 310) for row in rows)
                elif key == "unix_occurred_at": checks[key] = service.time_basis == "logical" and all(row.metadata.get("time_basis", "logical") == "logical" for row in rows)
                elif key == "must_not_emit_entire_original_quote": checks[key] = spec["source_text"] not in visible
                elif key == "must_not_resurrect_corrected_value": checks[key] = all(row.deleted for row in rows if "浮桥柜" in row.summary)
                elif key == "no_authoritative_body": checks[key] = aliases[operation["target_id"]] not in {row.memory_id for row in rows}
                elif key == "revocation_not_rolled_back": checks[key] = actual["replayed_entry_deleted"]
                elif key == "no_claim_of_secure_backup_erasure": actual[key] = "only_authoritative_payload_and_derived_projection_removed; secure_erasure_not_claimed"
                elif key == "calendar_fact_must_not_be_invented":
                    checks["no_unix_conversion"] = service.time_basis == "logical"
                    unsupported.append("generated_answer_calendar_hallucination:not_run_without_model")
                elif key in {"unique_accepted_event_count", "do_not_count_as_accepted", "all_related_claims_invalid"}:
                    layers = build_layers(tuple(active))
                    actual["layers"] = layers.overview
                    if key == "unique_accepted_event_count": checks[key] = layers.overview.get("catalog", {}).get("event_count", 0) == value
                    elif key == "do_not_count_as_accepted": checks[key] = not set(value).intersection(layers.represented_ids)
                    else: checks[key] = not any(row.metadata.get("event_id") == operation["event_id"] for row in active)
                else: unsupported.append(key)
            actual.update(payload=payload, active_ids=sorted(active_ids), after=[row.to_dict() for row in rows],
                          context_epoch=service.store.context_epoch, time_basis=service.time_basis)
            status = "failed" if not all(checks.values()) else "partial" if unsupported else "passed"
        except Exception as exc:
            status = "error"
            actual["error"] = f"{type(exc).__name__}: {exc}"
        actual["evidence_provider_requests"] = recorded_requests(config, request_start)
        records.append({"step": number, "operation": operation, "before": before,
                        "actual": actual, "checks": checks, "unsupported": unsupported, "status": status})
    close_service(service)
    return records


def budget_scenario(spec, root, dataset_path, config=None):
    from guanghe_companion.character_pack import load_default_character_pack
    from guanghe_companion.persona import build_persona_payload
    from guanghe_companion.expression_request import ExpressionRequest
    from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
    from tools.eval_ondemand_memory import make_entries, provider_evidence_payload
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    inputs = [row for row in dataset["memories"] if row["story_id"] == spec["dataset_story"]]
    question = next(row for row in dataset["queries"] if row["id"] == spec["dataset_query"])
    write(root / "authorized-projection.json", {"memories": inputs, "query": question})
    persona = build_persona_payload(load_default_character_pack())
    records = []
    for index, variant in enumerate(spec["variants"]):
        budget = RetrievalBudget(max_context_chars=variant["max_context_chars"], max_source_entries=variant["max_source_entries"])
        service = EmotionalMemoryService(root=root / str(index), character_id=dataset["character_id"],
            owner_id=dataset["owner_id"], time_basis="unix", retrieval_budget=budget)
        configure_judge(service, config)
        service.store.save_memories(make_entries(dataset, spec["dataset_story"], len(inputs), EmotionalMemoryEntry, input_rows=inputs))
        request_start = len(config["meter"].records) if config else 0
        preparation = prepare_query(service, question["text"], dataset["now"])
        result = service.retrieve(question["text"], now=dataset["now"], top_k=4)
        payload = result.bundle.to_prompt_payload()
        request = ExpressionRequest.from_snapshot({"character_name": persona["character_name"],
            "focus": 50, "charge": 50, "stability": 50, "mood": 50, "trust": 50, "player_message": question["text"]},
            context={"memory_v2_authoritative": True, "emotional_memory": payload, "persona": persona})
        with ShinsekaiAIExpressor() as expressor:
            prompt = expressor.build_prompt(request)
        final = provider_evidence_payload(prompt)
        selected = {row.memory_id for row in result.bundle.memories}
        checks = {}
        if "required_source_ids" in variant: checks["required_source_ids"] = set(variant["required_source_ids"]) <= selected
        if "expected_status" in variant: checks["expected_status"] = result.trace.status == variant["expected_status"]
        if variant.get("forbidden_partial_claims"):
            source = {row.memory_id: row for row in service.store.load_memories()}
            delivered = final.get("emotional_memory", {}).get("shared_memories", [])
            if delivered:
                checks["whole_claims"] = all(row["summary"] == source[row["memory_id"]].summary for row in delivered)
                checks["current_fingerprints"] = all(row.get("evidence_fingerprint") == source[row["memory_id"]].evidence_fingerprint() for row in delivered)
        if variant.get("persona_core_must_remain"):
            checks["persona_core_fields"] = all(final.get("persona", {}).get(key) == persona[key]
                for key in ("character_name", "description", "speech_style", "traits", "boundaries"))
        if variant.get("must_not_claim_all_four_answered"):
            checks["not_complete"] = result.trace.status != "sufficient"
        records.append({"variant": variant, "status": "passed" if all(checks.values()) else "failed", "checks": checks,
            "actual": {"trace": asdict(result.trace), "payload": payload, "provider_prompt": prompt,
                       "provider_payload": final, "answer_quality": "not_run", "persona_behavior": "not_run",
                       **preparation, "evidence_provider_requests": recorded_requests(config, request_start),
                       "claim_atomicity_measurement": "measured" if selected else "not_run_no_delivered_claims"}})
        close_service(service)
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario-id")
    parser.add_argument("--evidence-settings", type=Path)
    parser.add_argument("--model-cache", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("first-run evidence directory already exists")
    specs = json.loads(args.spec.read_text(encoding="utf-8"))
    config = None
    if args.evidence_settings:
        from tools.eval_ondemand_generation import recorded_app_client
        client, meter, metadata, secret = recorded_app_client(args.evidence_settings, max_requests=48, max_output_tokens=4096)
        config = {"client": client, "meter": meter, "metadata": metadata, "secret": secret, "model_cache": args.model_cache}
    report = {"source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "model_validation": "evidence_judgment_real_http" if config else "not_run",
        "answer_generation": "not_run", "provider": config["metadata"] if config else None,
        "bge": "real_local_cpu" if config and args.model_cache else "disabled",
        "assumptions": ["Unspecified unix now is 2026-11-01T12:00:00+08:00; logical now is 500.",
        "Seed free text is stored as a confirmed note; missing typed field/value metadata is not inferred from expected answers.",
        "Completed shared-event seed text maps to event_status and participants; source_kind/user_accepted/event_id come from the specification.",
        "Operations evaluate retrieved prompt evidence and real storage transitions; no generated answer is claimed."], "scenarios": []}
    for spec in specs["scenarios"]:
        if args.scenario_id and spec["scenario_id"] != args.scenario_id:
            continue
        root = args.output / spec["scenario_id"]
        steps = (budget_scenario(spec, root, args.dataset, config) if "variants" in spec else run_scenario(spec, root / "archive", config))
        write(root / "steps.json", steps)
        report["scenarios"].append({"scenario_id": spec["scenario_id"], "steps": len(steps),
            "passed": sum(row["status"] == "passed" for row in steps),
            "failed": sum(row["status"] in {"failed", "error"} for row in steps),
            "partial": sum(row["status"] == "partial" for row in steps)})
    write(args.output / "summary.json", report)
    write(args.output / "provider-requests.json", recorded_requests(config, 0))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
