"""Deterministic memory contract benchmark (no network, no model inference).

Run this same file against an archived baseline with ``--repo /path/to/repo``.
All characters, memories, and conversations below are synthetic and temporary.
Missing features are failures, never successful skips. The report separates
retrieval from final prompt delivery so a disconnected memory pipeline cannot
claim zero leakage as success.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass, replace
from datetime import datetime, timezone
import hashlib
import importlib
import inspect
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "tests" / "fixtures" / "memory_benchmark.json"


def _load_api(repo: Path) -> dict[str, object]:
    source = (repo / "src").resolve()
    if not source.is_dir():
        raise ValueError(f"repository src directory not found: {source}")
    if any(name.startswith("guanghe_companion") for name in sys.modules):
        raise RuntimeError("run each repository in a fresh process to avoid mixed imports")
    sys.path.insert(0, str(source))
    modules = {
        "service": "emotional_memory_service",
        "controller": "plugin_enabled_controller",
        "request": "expression_request",
        "migration": "legacy_memory_migration",
        "dialogue": "dialogue",
        "history": "dialogue_history",
        "story": "companion_story_runtime",
    }
    return {key: importlib.import_module(f"guanghe_companion.{name}") for key, name in modules.items()}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _supported_kwargs(function, kwargs: dict[str, object], missing: list[str]) -> dict[str, object]:
    parameters = inspect.signature(function).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
        return kwargs
    for key in kwargs:
        if key not in parameters:
            missing.append(f"{function.__qualname__}.{key}")
    return {key: value for key, value in kwargs.items() if key in parameters}


def _persona_hash(controller) -> str:
    """Only configuration identity, explicitly not model behavior/personality."""
    pack_dir = Path(controller.resources.asset_dir)
    payload = {
        name: (pack_dir / name).read_text(encoding="utf-8-sig")
        for name in ("character.json", "dialogue_style.json")
        if (pack_dir / name).is_file()
    }
    # Include the actual connected profile when the host exposes one.
    policy = getattr(controller.ai_expressor, "dialogue_policy", None)
    profile = getattr(policy, "performance_profile", None)
    if profile is not None:
        payload["connected_performance_profile"] = asdict(profile) if is_dataclass(profile) else repr(profile)
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


class CaseHarness:
    def __init__(self, api: dict[str, object], root: Path) -> None:
        self.api = api
        self.root = root
        self.actors: dict[str, object] = {}
        self.memories: dict[str, object] = {}
        self.pending: dict[str, str] = {}
        self.missing: list[str] = []
        self.notes: list[str] = []
        self.observed: dict[str, object] = {}
        self.reader = "default"
        self.add_actor("default", "xingxi_pixel_pet", "local_user")

    def add_actor(self, name: str, character_id: str, owner_id: str) -> None:
        controller = self.api["controller"].PluginEnabledCompanionController(
            user_data_root=self.root, auto_load=False, character_id=character_id,
        )
        controller.ai_expressor.enabled = False
        controller.ai_expressor.llm_client = None
        if owner_id != "local_user":
            # Owner scoping is a service contract; the desktop UI is currently single-user.
            controller.story_runtime.memory = self.api["service"].EmotionalMemoryService(
                root=self.root, character_id=character_id, owner_id=owner_id,
            )
        self.actors[name] = controller

    def close(self) -> None:
        for controller in self.actors.values():
            controller.close()

    def operation(self, row: dict[str, object]) -> None:
        kind = row["op"]
        actor = str(row.get("actor", "default"))
        controller = self.actors[actor]
        service = controller.story_runtime.memory
        now = int(row.get("now", 100))
        if kind == "remember":
            kwargs = {
                "kind": "玩家希望被记住", "title": "用户明确陈述", "summary": "",
                "source": "explicit_user_request", "now": now,
                "importance": 0.85, "tags": ("关于你",),
                **dict(row.get("args", {})),
            }
            if "tags" in kwargs:
                kwargs["tags"] = tuple(kwargs["tags"])
            kwargs = _supported_kwargs(service.remember, kwargs, self.missing)
            try:
                memory = service.remember(**kwargs)
            except ValueError as exc:
                if not row.get("expect_rejected", False):
                    raise
                self.observed["write_rejected"] = True
                self.notes.append(f"rejected_write:{type(exc).__name__}")
                return
            self.memories[str(row["id"])] = memory
            if row.get("expect_rejected", False):
                self.observed["write_rejected"] = False
        elif kind == "correct":
            old = self.memories[str(row["id"])]
            kwargs = {"title": str(row.get("title", old.title)), "summary": str(row["summary"]), "now": now}
            method = getattr(service, "correct", None)
            if callable(method):
                new = method(old.memory_id, **kwargs)
            else:
                # This is exactly how the baseline album implements correction.
                self.notes.append("baseline_compat:remember(supersedes=old_id)")
                new = service.remember(
                    kind=old.kind, source="user_correction", supersedes=old.memory_id,
                    importance=old.importance, tags=old.tags, pinned=old.pinned,
                    user_confirmed=True, metadata=old.metadata, **kwargs,
                )
            self.memories[str(row.get("new_id", str(row["id"]) + "_new"))] = new
        elif kind == "forget":
            service.forget(self.memories[str(row["id"])].memory_id, now=now)
        elif kind == "consolidate":
            service.consolidate(now=now)
        elif kind == "profile":
            kwargs = {"now": now, **dict(row.get("args", {}))}
            if row.get("sources"):
                kwargs["source_memory_ids"] = tuple(self.memories[name].memory_id for name in row["sources"])
            service.update_bond_profile(**_supported_kwargs(service.update_bond_profile, kwargs, self.missing))
        elif kind == "rewrite_source":
            old = self.memories[str(row["id"])]
            service.store.update_memory(replace(old, title=str(row.get("title", old.title)), summary=str(row["summary"]), updated_at=now))
        elif kind == "replay":
            try:
                service.store.upsert_memory(self.memories[str(row["id"])])
            except ValueError:
                self.notes.append("retired_replay_rejected")
        elif kind == "reopen":
            old = controller.story_runtime.memory
            owner, character = old.owner_id, old.character_id
            controller.close()
            self.add_actor(actor, character, owner)
        elif kind == "actor":
            self.add_actor(str(row["name"]), str(row.get("character", "xingxi_pixel_pet")), str(row.get("owner", "local_user")))
        elif kind == "read_as":
            self.reader = str(row["name"])
        elif kind == "migrate":
            report = self.api["migration"].migrate_legacy_entries(service, row["rows"], now=now)
            if row.get("id") and report.migrated_ids:
                found = {memory.memory_id: memory for memory in service.store.load_memories()}
                self.memories[str(row["id"])] = found[report.migrated_ids[0]]
        elif kind == "propose":
            pending_id = service.propose_explicit_user_memory(str(row["text"]), now=now)
            if pending_id is None:
                raise ValueError("explicit memory candidate was unexpectedly rejected")
            self.pending[str(row["id"])] = pending_id
            if row.get("confirm", False):
                self.memories[str(row["id"])] = service.confirm_candidate(pending_id, now=now + 1)
        elif kind == "record_event":
            memory = service.record_event(row["event"], now=now)
            if memory is not None and row.get("id"):
                self.memories[str(row["id"])] = memory
        elif kind == "history":
            controller.dialogue_history = self.api["history"].append_dialogue_exchange(
                controller.dialogue_history, user_text=str(row["user"]),
                assistant_name=controller.state.character_name, assistant_text=str(row.get("assistant", "记下了。")),
            )
            controller.dialogue_history_store.save(controller.dialogue_history)
        elif kind == "recent_log":
            controller.state.memory_log.insert(0, {"at": now, "kind": "共同日常", "summary": str(row["summary"]), "motion": "Default"})
        elif kind == "chat":
            controller.submit_dialogue_request(self.api["dialogue"].DialogueRequest(text=str(row["text"])), include_ai_expression=False)
        elif kind == "capture_persona":
            self.observed["persona_before"] = _persona_hash(controller)
        elif kind == "switch":
            original = self.api["story"].CompanionStoryRuntime.build_expression_context
            mixed: list[dict[str, str]] = []
            def capture(story, *args, **kwargs):
                result = original(story, *args, **kwargs)
                bundle = result[1]
                mixed.append({"state": controller.state.character_id, "memory": bundle.bond_profile.character_id})
                return result
            replace_expressor = controller._replace_ai_expressor
            def offline_expressor(next_expressor):
                next_expressor.enabled = False
                next_expressor.llm_client = None
                return replace_expressor(next_expressor)
            with patch.object(self.api["story"].CompanionStoryRuntime, "build_expression_context", capture), patch.object(controller, "_replace_ai_expressor", offline_expressor):
                controller.switch_character(str(row["character"]), include_ai_expression=bool(row.get("expression", False)))
            self.observed["scope_mismatch"] = any(item["state"] != item["memory"] for item in mixed)
            self.observed["switch_contexts"] = mixed
        else:
            raise ValueError(f"unknown benchmark operation: {kind}")

    def probe(self, case: dict[str, object]) -> dict[str, object]:
        controller = self.actors[self.reader]
        service = controller.story_runtime.memory
        now = int(case.get("now", 1000))
        query = str(case.get("query", ""))
        # Probe the retrieval API and the real controller -> request -> prompt route separately.
        recalled = service.recall(query, now=now, top_k=4)
        controller._current_player_message = query
        controller.now = now
        start = time.perf_counter_ns()
        try:
            context = controller.get_expression_context()
            request = self.api["request"].ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=context)
            prompt = controller.ai_expressor.build_prompt(request)
        finally:
            controller._current_player_message = ""
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        active = tuple(memory for memory in service.store.load_memories() if not memory.deleted)
        observed = {
            **self.observed,
            "retrieved_ids": [memory.memory_id for memory in recalled],
            "retrieved": [{"id": memory.memory_id, "title": memory.title, "summary": memory.summary} for memory in recalled],
            "active_count": len(active),
            "pending_count": len(service.pending_candidates),
            "context": context,
            "prompt": prompt,
            "persona_after": _persona_hash(controller),
            "context_chars": len(_json(context)),
            "prompt_chars": len(prompt),
            "prompt_utf8_bytes": len(prompt.encode("utf-8")),
            "estimated_prompt_tokens": math.ceil(len(prompt.encode("utf-8")) / 4),
            "context_and_prompt_latency_ms": elapsed_ms,
            "loaded_service_file": str(Path(self.api["service"].__file__).resolve()),
        }
        expected = dict(case.get("expect", {}))
        checks: list[dict[str, object]] = []
        def check(name: str, passed: bool, **details) -> None:
            checks.append({"name": name, "passed": bool(passed), **details})
        for alias in expected.get("recalled", []):
            memory = self.memories.get(alias)
            check("correct_recall", memory is not None and memory.memory_id in observed["retrieved_ids"], alias=alias)
        for alias in expected.get("not_recalled", []):
            memory = self.memories.get(alias)
            check("excluded_recall", memory is not None and memory.memory_id not in observed["retrieved_ids"], alias=alias)
        if expected.get("empty_recall", False):
            check("empty_recall", not recalled)
        for channel in ("context", "prompt"):
            text = _json(context) if channel == "context" else prompt
            for fragment in expected.get(f"{channel}_contains", []):
                check(f"{channel}_delivery", fragment in text, fragment=fragment)
            for fragment in expected.get(f"{channel}_absent", []):
                check(f"{channel}_no_leak", fragment not in text, fragment=fragment)
        for field in ("active_count", "pending_count", "write_rejected", "scope_mismatch"):
            if field in expected:
                check(field, observed.get(field) == expected[field], expected=expected[field], actual=observed.get(field))
        if expected.get("chapter_absent", False):
            emotional = context.get("emotional_memory", {})
            check("derived_chapter_invalidated", not emotional.get("relationship_chapter"))
        if expected.get("persona_unchanged", False):
            check("persona_configuration_unchanged", bool(observed.get("persona_before")) and observed["persona_before"] == observed["persona_after"])
        for capability in dict.fromkeys(self.missing):
            check("missing_capability", False, capability=capability)
        if not checks:
            raise ValueError("benchmark case has no assertions")
        return {
            "id": case["id"], "category": case["category"], "description": case.get("description", ""),
            "passed": all(item["passed"] for item in checks), "checks": checks,
            "compatibility_notes": self.notes, "missing_capabilities": list(dict.fromkeys(self.missing)),
            "observed": observed,
        }


def _rate(checks: list[dict[str, object]], name: str, *, failure: bool = False) -> dict[str, object]:
    rows = [item for item in checks if item["name"] == name]
    successes = sum(bool(item["passed"]) for item in rows)
    numerator = len(rows) - successes if failure else successes
    return {"numerator": numerator, "denominator": len(rows), "rate": numerator / len(rows) if rows else None}


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    checks = [check for row in rows for check in row.get("checks", [])]
    category = {}
    for row in rows:
        group = category.setdefault(row["category"], {"cases": 0, "passed": 0})
        group["cases"] += 1
        group["passed"] += bool(row["passed"])
    latencies = [row["observed"]["context_and_prompt_latency_ms"] for row in rows if "observed" in row]
    token_counts = [row["observed"]["estimated_prompt_tokens"] for row in rows if "observed" in row]
    def grouped_negative(categories: set[str]) -> dict[str, object]:
        selected = [row for row in rows if row["category"] in categories]
        failed = sum(any(not check["passed"] for check in row.get("checks", []) if check["name"] in {"context_no_leak", "prompt_no_leak", "empty_recall", "excluded_recall", "scope_mismatch"}) for row in selected)
        return {"numerator": failed, "denominator": len(selected), "rate": failed / len(selected) if selected else None,
                "note": "content assertions only; inspect missing_capability failures separately"}
    return {
        "cases": len(rows), "passed": sum(row["passed"] for row in rows),
        "failed": sum(not row["passed"] for row in rows), "categories": category,
        "missing_capability_cases": sum(bool(row.get("missing_capabilities")) for row in rows),
        "execution_error_cases": sum("error" in row for row in rows),
        "correct_recall": _rate(checks, "correct_recall"),
        "final_prompt_delivery": _rate(checks, "prompt_delivery"),
        "irrelevant_recall": grouped_negative({"irrelevant"}),
        "outdated_fact_reference": grouped_negative({"correction", "temporal"}),
        "forgotten_information_leak": grouped_negative({"forgetting", "derived", "migration"}),
        "cross_role_owner_scene_contamination": grouped_negative({"isolation"}),
        "persona_configuration_stability": _rate(checks, "persona_configuration_unchanged"),
        "fabricated_event_write_acceptance": {
            "numerator": sum(row.get("observed", {}).get("active_count", 0) > 0 for row in rows if row["category"] == "fabrication"),
            "denominator": sum(row["category"] == "fabrication" for row in rows),
            "note": "deterministic ingestion policy only; generated narrative factuality not run",
        },
        "context_and_prompt_latency_ms": {
            "samples": len(latencies), "median": statistics.median(latencies) if latencies else None,
            "p95_nearest_rank": sorted(latencies)[max(0, math.ceil(.95 * len(latencies)) - 1)] if latencies else None,
            "includes": "controller context assembly, snapshot, typed request, prompt formatting; local disk included",
            "excludes": "seeding, retrieval API pre-probe, model inference, network, UI paint, ASR and TTS",
        },
        "estimated_prompt_tokens": {
            "median": statistics.median(token_counts) if token_counts else None,
            "maximum": max(token_counts) if token_counts else None,
            "estimator": "ceil(UTF-8 byte length / 4); heuristic, NOT provider tokenizer usage",
        },
        "model_persona_behavior": "not_run",
        "model_fabricated_shared_experience": "not_run",
        "model_response_latency": "not_run",
        "model_actual_token_usage": "not_run",
    }


def run(repo: Path, dataset: Path, case_ids: list[str] | None = None) -> dict[str, object]:
    payload = json.loads(dataset.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if not cases or len({row["id"] for row in cases}) != len(cases):
        raise ValueError("dataset must contain nonempty, uniquely identified cases")
    if case_ids:
        requested = set(case_ids)
        missing = requested - {row["id"] for row in cases}
        if missing:
            raise ValueError(f"unknown case ids: {', '.join(sorted(missing))}")
        cases = [row for row in cases if row["id"] in requested]
    api = _load_api(repo)
    rows = []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="emoti-memory-benchmark-") as directory:
            harness = None
            try:
                harness = CaseHarness(api, Path(directory))
                for operation in case["ops"]:
                    harness.operation(operation)
                rows.append(harness.probe(case))
            except Exception as exc:
                rows.append({"id": case["id"], "category": case["category"], "passed": False,
                             "error": {"type": type(exc).__name__, "message": str(exc)},
                             "checks": [{"name": "execution_error", "passed": False}]})
            finally:
                if harness is not None:
                    harness.close()
    revision = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    source_hash = hashlib.sha256()
    source_files = sorted((repo / "src").rglob("*.py"))
    for path in source_files:
        source_hash.update(path.relative_to(repo).as_posix().encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(repo.resolve()), "git_revision": revision.stdout.strip() if revision.returncode == 0 else "archive_without_git_metadata",
        "source_tree_sha256": source_hash.hexdigest(), "source_python_files": len(source_files),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "dataset": str(dataset.resolve()), "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "dataset_version": payload.get("version", 1), "summary": summarize(rows), "results": rows,
        "limitations": [
            "All data is synthetic; the finite cases are contract probes, not estimates of real user accuracy.",
            "No live model, embedding service, network call, Windows UI, microphone, speaker or camera is used.",
            "A low leak rate without positive final_prompt_delivery is not a successful memory system.",
            "Unavailable capabilities and exceptions are failures; they are not silently skipped.",
            "Logical forgetting checks prompt exposure, not physical erasure of backups or remote provider logs.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT, help="Repository under test; modules loaded from its src only")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", dest="case_ids")
    args = parser.parse_args()
    try:
        report = run(args.repo.resolve(), args.dataset.resolve(), args.case_ids)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
