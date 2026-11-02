"""Integrated on-demand retrieval over the existing EmotionalMemoryService.

Index, vector and overview objects are disposable projections. The final
transaction still authenticates every selected source against the sole
canonical document and its revocation epoch.
"""
from __future__ import annotations

from dataclasses import replace
import json
import math
import re
from time import perf_counter
from collections.abc import Mapping, Sequence

from .emotional_memory import CoreBondProfile, EmotionalMemoryEntry
from .emotional_memory_retrieval import score_memory
from .memory_fusion import reciprocal_rank_fusion
from .memory_hierarchy import build_layers
from .memory_index import IndexedMemoryQuery
from .retrieval_contract import (EvidenceContextBundle, EvidenceDecision, RetrievalBudget,
                                 RetrievalResult, RetrievalTrace, RetrievalIntent, RetrievalPlan)
from .retrieval_evidence import check_evidence, fact_view, topic_terms
from .retrieval_router import MemoryRetrievalRouter
from .retrieval_literal import mention_candidates


def prepare_retrieval(service, query: str, *, now: int, history: Sequence[object] = (), scope="companion"):
    future = _prepare_semantic(service, query, now=now, history=history, scope=scope)
    if service.evidence_judge is not None:
        return service.evidence_judge.prepare(service, query, now=now, history=history,
            scope=scope, semantic_future=future)
    return future


def _prepare_semantic(service, query: str, *, now: int, history: Sequence[object] = (), scope="companion"):
    plan = service.retrieval_router.plan(query, history=history, scope=scope, now=now)
    retriever = service.semantic_retriever
    semantic_intents = tuple(i for i in plan.intents if (i.route in {"episode", "task", "bounded"}
                             or service.evidence_judge is not None)
                             and i.temporal_mode != "unresolved")
    if retriever is None or not semantic_intents or plan.unresolved_reference:
        return None
    scopes = tuple(dict.fromkeys(s for i in semantic_intents for s in i.scopes))
    if service.evidence_judge is not None:
        scopes = tuple(dict.fromkeys((scope, *scopes)))
    if hasattr(retriever, "prepare_indexed"):
        return retriever.prepare_indexed(query, service.store, now=now, scopes=scopes)
    # Legacy optional adapters still receive a bounded eligible view. They do
    # not cause a full-document/global retrieval in the interactive path.
    if hasattr(retriever, "prepare"):
        snapshot = service.store.read_indexed_snapshot(IndexedMemoryQuery(scopes=scopes, query=query,
            limit=service.retrieval_budget.max_candidates), now=now, include_chapters=False)
        return retriever.prepare(query, snapshot.entries, now=now, scope=scopes[0])
    return None


def _rank(entries, intent, *, query, now, stage, retriever):
    semantic, semantic_status = {}, "disabled"
    if retriever is not None and intent.route in {"episode", "task", "bounded"}:
        try:
            supplied = retriever(query, tuple(entries))
            if isinstance(supplied, Mapping):
                semantic = {key: float(value) for key, value in supplied.items()
                            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)}
            semantic_status = "prepared" if semantic else "no_prepared_scores"
        except Exception:
            semantic_status = "unavailable"
    scores = {m.memory_id: score_memory(m, intent.query, now=now, relationship_stage=stage) for m in entries}
    lexical = sorted((m for m in entries if scores[m.memory_id].relevance > 0),
                     key=lambda m: scores[m.memory_id].total, reverse=True)
    semantic_order = sorted((m for m in entries if m.memory_id in semantic),
                            key=lambda m: semantic[m.memory_id], reverse=True)
    # Independent ranked channels: semantic-only candidates do not receive an
    # extra lexical vote. The legacy implementation remains the frozen control.
    ids = [key for key, _ in reciprocal_rank_fusion([[m.memory_id for m in lexical],
                                                    [m.memory_id for m in semantic_order]])]
    ids += [m.memory_id for m in entries if m.memory_id not in ids]
    by_id = {m.memory_id: m for m in entries}
    ranked = [by_id[key] for key in ids]
    if intent.route == "fact":
        ranked.sort(key=lambda m: (m.valid_from, m.occurred_at, m.created_at), reverse=True)
    elif "第一次" in intent.query:
        ranked.sort(key=lambda m: m.occurred_at)
    return ranked, semantic_status


def _resolve_subjects(store, intent, *, now):
    if not intent.subjects:
        return intent, False, None
    canonical = []
    ambiguous = False
    literals = [subject for subject in intent.subjects if not (subject == "user:self" or subject.startswith(("relation:", "entity:")))]
    # A user-defined entity alias may be followed by an unseen attribute.
    # Resolve only bounded exact prefixes, and retain source fingerprints for
    # the identity link. A shared noun or an embedding is never a binding.
    expandable_relation = any(s.startswith("relation:") and "的" not in s for s in intent.subjects)
    if not literals and ("unresolved_field" in intent.predicates or expandable_relation):
        literals = list(dict.fromkeys((*literals, *mention_candidates(intent.query, intent.subjects))))
    resolution = store.resolve_subject_bindings(literals, now=now, scopes=intent.scopes) if literals else None
    if resolution is not None:
        matches = [s for s in literals if resolution.mapping.get(s)]
        if matches:
            longest = max(map(len, matches))
            chosen = [s for s in matches if len(s) == longest]
            linked = tuple(dict.fromkeys(value for s in chosen for value in resolution.mapping[s]))
            sources = tuple(dict.fromkeys(key for s in chosen for key in resolution.sources_by_input[s]))
            resolution = replace(resolution, mapping={s: resolution.mapping[s] for s in chosen},
                source_ids=sources, source_fingerprints={key: resolution.source_fingerprints[key] for key in sources},
                sources_by_input={s: resolution.sources_by_input[s] for s in chosen})
            return replace(intent, subjects=linked), len(linked) != 1, resolution
    for subject in intent.subjects:
        if subject == "user:self" or subject.startswith(("relation:", "entity:")):
            canonical.append(subject)
            continue
        resolved = resolution.mapping.get(subject, ()) if resolution is not None else ()
        if len(resolved) != 1:
            ambiguous = True
        canonical.extend(resolved)
    return replace(intent, subjects=tuple(dict.fromkeys(canonical))), ambiguous, resolution


def _single_value_conflict(entries: list[EmotionalMemoryEntry], intent: RetrievalIntent) -> bool:
    if intent.route != "fact" or intent.temporal_mode in {"history", "timeline"}:
        return False
    single = {"name", "姓名", "legal_name", "residence", "居住地", "occupation", "职业", "称呼", "nickname"}
    if not single.intersection(intent.predicates):
        return False
    values = {str(fact_view(m).metadata.get("fact_value", "")) for m in entries}
    return len(values - {""}) > 1


def _unique_current_facts(entries, intent):
    """Merge equal current claims in the view, preserving every stored source."""
    if intent.route != "fact" or intent.temporal_mode != "current":
        return entries
    seen, result = set(), []
    for entry in entries:
        meta = fact_view(entry).metadata
        key = tuple(json.dumps(meta.get(name, ""), ensure_ascii=False, sort_keys=True, separators=(",", ":")) for name in
                    ("fact_subject", "entity_id", "fact_predicate", "fact_slot", "fact_domain", "fact_object", "fact_value"))
        if not key[-1] or key not in seen:
            result.append(entry)
            seen.add(key)
    return result


def _task_application(intent, entries):
    if intent.route != "task" or intent.app:
        return intent
    # A literal application immediately before its version is an explicit
    # constraint even when the application has never been remembered.
    versioned = re.search(r"(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_.-]{1,31})\s+v?\d+\.\d+", intent.query)
    if versioned:
        return replace(intent, app=versioned[1])
    names = {str(e.metadata.get("app", "")) for e in entries}
    matches = [name for name in names if name and re.search(r"(?<![A-Za-z0-9_])" + re.escape(name)
        + r"(?![A-Za-z_])", intent.query, re.I)]
    if len(matches) == 1:
        return replace(intent, app=matches[0])
    return intent


def _bound_bundle(bundle, budget, *, chapters=(), layered=True):
    from .memory_prompt_budget import trim_profile, trim_memory_metadata
    while len(json.dumps(bundle.to_prompt_payload(), ensure_ascii=False)) > budget:
        payload = bundle.to_prompt_payload()
        if trim_profile(payload, keep_each=2):
            bundle = replace(bundle, bond_profile=CoreBondProfile.from_dict(payload["bond_profile"]))
        elif bundle.memories:
            memories = bundle.memories[:-1]
            kept = {m.memory_id for m in memories}
            layers = build_layers(memories, chapters=chapters,
                detail=bundle.retrieval.get("evidence_level") == "L2", enabled=layered, budget_chars=budget)
            intents = []
            for state in bundle.retrieval.get("intent_status", []):
                previous = state.get("source_ids", [])
                lost = any(key not in kept for key in previous)
                intents.append({**state, "source_ids": [key for key in previous if key in kept],
                                "status": "insufficient" if lost else state["status"]})
            bindings = tuple(row for row in bundle.resolution_evidence if kept and
                (not row.get("dependent_memory_ids") or kept.intersection(row["dependent_memory_ids"])))
            bundle = replace(bundle, memories=memories, overview=layers.overview,
                overview_source_ids=layers.represented_ids, resolution_evidence=bindings,
                source_spans=tuple(row for row in bundle.source_spans if row["memory_id"] in kept),
                retrieval={**bundle.retrieval, "status": "insufficient", "budget_limited": True,
                           "evidence_level": layers.level, "intent_status": intents})
        elif bundle.external_state:
            states = bundle.external_state[:-1]
            kept_authorities = {state.authority for state in states}
            intents = [{**state, "status": "insufficient"}
                       if state.get("route") == "live" and state.get("authority") not in kept_authorities
                       else state for state in bundle.retrieval.get("intent_status", ())]
            bundle = replace(bundle, external_state=states,
                             retrieval={**bundle.retrieval, "status": "insufficient", "budget_limited": True,
                                        "intent_status": intents})
        elif trim_profile(payload, include_boundaries=True):
            bundle = replace(bundle, bond_profile=CoreBondProfile.from_dict(payload["bond_profile"]))
        elif bundle.resolution_evidence:
            bundle = replace(bundle, resolution_evidence=())
        elif trim_memory_metadata(payload):
            bundle = replace(bundle, retrieval=payload["retrieval"])
        else:
            raise ValueError("required memory identity and status exceed retrieval budget")
    return bundle


def retrieve(service, query: str, *, now: int, history: Sequence[object] = (), scope="companion", top_k=4,
             relationship_stage: str | None = None, layered: bool = True) -> RetrievalResult:
    from .emotional_memory_service import _active_memory_index, _valid_profile, _valid_chapters

    started = perf_counter()
    budget: RetrievalBudget = service.retrieval_budget
    plan = service.retrieval_router.plan(query, history=history, scope=scope, now=now)
    judgment = (service.evidence_judge.prepared(service, query, scope=scope, now=now, history=history)
                if service.evidence_judge is not None else None)
    if judgment is not None:
        plan = judgment.plan
    top_k = min(max(0, int(top_k)), budget.max_source_entries)
    for attempt in range(3):
        timings = {"routing": (perf_counter() - started) * 1000 if attempt == 0 else 0.0}
        calls = rows = candidates = expansions = 0
        decisions = []
        statuses = []
        selected = []
        dependencies = {}
        binding_evidence = {}
        external = []
        chapters = {}
        semantic_status = "not_needed"
        phase = perf_counter()
        base = service.store.read_indexed_snapshot(IndexedMemoryQuery(memory_ids=()), now=now, include_chapters=False)
        timings["database_read"] = (perf_counter() - phase) * 1000
        rows += base.rows_loaded
        epoch, revision = base.context_epoch, base.index_revision
        active = _active_memory_index(base.source_entries, now=now)
        profile = _valid_profile(base.profile, active)
        # Always-visible derived fields need the same final fingerprint fence
        # as retrieved cards, including a zero-hit/chat request.
        dependencies.update((entry.memory_id, entry) for entry in base.source_entries)
        if relationship_stage is not None:
            profile = replace(profile, relationship_stage=relationship_stage)
        stage = profile.relationship_stage
        scope_set = set()
        stale = False
        for intent_index, original_intent in enumerate(plan.intents):
            intent = original_intent
            if intent.route == "chat":
                statuses.append({"route": "chat", "status": "not_needed", "source_ids": []})
                continue
            if intent.route == "live":
                state = None
                reader = service.external_state_readers.get(intent.authority)
                phase = perf_counter()
                if reader is not None:
                    try:
                        state = reader(intent, now)
                        if state is not None and not state.valid_for(authority=intent.authority,
                                character_id=service.character_id, owner_id=service.owner_id, now=now):
                            state = None
                    except Exception:
                        state = None
                timings["external_read"] = timings.get("external_read", 0) + (perf_counter() - phase) * 1000
                if state is not None:
                    external.append(state)
                statuses.append({"route": "live", "authority": intent.authority,
                                 "status": "sufficient" if state is not None else "external_unavailable", "source_ids": []})
                continue
            if plan.unresolved_reference:
                statuses.append({"route": intent.route, "status": "insufficient", "reason": "unresolved_reference", "source_ids": []})
                continue
            if intent.temporal_mode == "unresolved":
                statuses.append({"route": intent.route, "status": "insufficient", "reason": "unresolved_time_basis_or_date", "source_ids": []})
                continue
            phase = perf_counter()
            if judgment is not None:
                from .memory_evidence_judgment import resolve_judged_subjects
                intent, unresolved, resolution = resolve_judged_subjects(service.store, judgment, intent_index, now=now)
            else:
                intent, unresolved, resolution = _resolve_subjects(service.store, intent, now=now)
            timings["entity_resolution"] = timings.get("entity_resolution", 0) + (perf_counter() - phase) * 1000
            if resolution is not None and (resolution.context_epoch, resolution.index_revision, resolution.index_generation) != (epoch, base.index_revision, base.index_generation):
                stale = True
                break
            if unresolved:
                statuses.append({"route": intent.route, "status": "insufficient", "reason": "unresolved_or_ambiguous_entity", "source_ids": []})
                continue
            scope_set.update(intent.scopes)
            phase = perf_counter()
            search_text = " ".join(topic_terms(intent.query)) or intent.query
            open_field = "unresolved_field" in intent.predicates
            structured = intent.route == "fact" and bool(intent.subjects or intent.predicates) and not open_field
            retriever = service.semantic_retriever
            semantic_ids = ()
            if intent.route in {"episode", "task", "bounded"} and hasattr(retriever, "candidate_ids"):
                try:
                    semantic_ids = tuple(dict.fromkeys(key for sc in intent.scopes
                        for key in retriever.candidate_ids(query, limit=budget.max_candidates // 2, scope=sc)))[:budget.max_candidates // 2]
                except Exception:
                    semantic_status = "unavailable"
            request = IndexedMemoryQuery(scopes=intent.scopes, subjects=intent.subjects,
                predicates=() if open_field else intent.predicates, query="" if structured else search_text,
                history=intent.temporal_mode in {"history", "as_of", "timeline"}
                    or (intent.temporal_mode == "planned" and intent.as_of is not None),
                occurred_after=(intent.as_of or 0) if intent.route in {"episode", "task"} and intent.temporal_mode == "as_of" else 0,
                occurred_before=(intent.as_of_end or 0) if intent.route in {"episode", "task"} and intent.temporal_mode == "as_of" else 0,
                limit=budget.max_candidates - len(semantic_ids))
            if judgment is not None:
                request = replace(request, subjects=(), predicates=(), query="",
                    memory_ids=judgment.selections[intent_index], limit=budget.max_candidates)
                semantic_ids = ()
            snapshot = service.store.read_indexed_snapshot(request, now=now, include_chapters=layered and intent.route == "episode")
            calls += 1
            rows += snapshot.rows_loaded
            candidates += snapshot.total_candidates
            revision = max(revision, snapshot.index_revision)
            timings["database_read"] += (perf_counter() - phase) * 1000
            if (snapshot.context_epoch, snapshot.index_revision, snapshot.index_generation) != (epoch, base.index_revision, base.index_generation):
                stale = True
                break
            alias_dependencies = ()
            if resolution is not None and resolution.source_ids:
                # Alias tables may repeat the same binding on thousands of
                # facts. One valid source per exact input suffices; reading all
                # of them would defeat bounded reads and the expansion budget.
                candidate_rows = {e.memory_id: e for e in snapshot.entries}
                by_input = {}
                for alias, ids in resolution.sources_by_input.items():
                    if not ids:
                        continue
                    matching = [key for key in ids if key in candidate_rows and check_evidence(candidate_rows[key], intent,
                        now=now, owner_id=service.owner_id, character_id=service.character_id).accepted]
                    by_input[alias] = ((matching or [key for key in ids if key in candidate_rows] or list(ids))[0],)
                proof_ids = tuple(dict.fromkeys(key for ids in by_input.values() for key in ids))
                resolution = replace(resolution, source_ids=proof_ids,
                    sources_by_input=by_input, source_fingerprints={key: resolution.source_fingerprints[key] for key in proof_ids})
                refs = service.store.read_indexed_snapshot(IndexedMemoryQuery(scopes=intent.scopes,
                    memory_ids=resolution.source_ids, limit=budget.max_source_entries), now=now,
                    include_chapters=False, include_profile_sources=False)
                rows += refs.rows_loaded
                if ((refs.context_epoch, refs.index_revision, refs.index_generation) != (epoch, base.index_revision, base.index_generation)
                        or set(resolution.source_ids) != {e.memory_id for e in refs.entries}
                        or any(e.evidence_fingerprint() != resolution.source_fingerprints.get(e.memory_id) for e in refs.entries)):
                    stale = True
                    break
                alias_dependencies = refs.entries
            current = {m.memory_id: m for m in snapshot.entries}
            for chapter in _valid_chapters(snapshot.chapters, _active_memory_index(snapshot.source_entries + snapshot.entries, now=now)):
                chapters[chapter.chapter_id] = chapter
            # Semantic candidates are only identifiers. Re-read and authorize
            # their current rows; cached text/scores never become evidence.
            if semantic_ids:
                ids = tuple(key for key in semantic_ids if key not in current)
                if ids:
                    phase = perf_counter()
                    extra = service.store.read_indexed_snapshot(replace(request, query="", memory_ids=ids,
                        limit=budget.max_candidates - len(current)),
                        now=now, include_chapters=False, include_profile_sources=False)
                    calls += 1
                    rows += extra.rows_loaded
                    candidates += extra.total_candidates
                    timings["database_read"] += (perf_counter() - phase) * 1000
                    if (extra.context_epoch, extra.index_revision, extra.index_generation) != (epoch, base.index_revision, base.index_generation):
                        stale = True
                        break
                    current.update((m.memory_id, m) for m in extra.entries)
            intent = _task_application(intent, current.values())
            phase = perf_counter()
            accepted = []
            for entry in current.values():
                decision = check_evidence(entry, intent, now=now, owner_id=service.owner_id, character_id=service.character_id)
                if judgment is not None:
                    from .memory_evidence_judgment import hard_eligibility
                    accepted_judgment = (entry.memory_id in judgment.selections[intent_index]
                        and entry.evidence_fingerprint() == judgment.fingerprints.get(entry.memory_id)
                        and hard_eligibility(entry, intent, now=now, owner_id=service.owner_id,
                            character_id=service.character_id))
                    decision = EvidenceDecision(entry.memory_id, accepted_judgment,
                        "source_bound_model_support" if accepted_judgment else "judgment_source_invalid", intent.route)
                decisions.append(decision)
                if decision.accepted:
                    accepted.append(entry)
            timings["eligibility_and_evidence"] = timings.get("eligibility_and_evidence", 0) + (perf_counter() - phase) * 1000
            # A single bounded expansion supports legacy untyped cards and
            # incomplete lexical matches. Never relax entity/field/time gates.
            supported_fields = {field for d in decisions if d.accepted and d.memory_id in {e.memory_id for e in accepted}
                                for field in d.supported_details}
            needs_expansion = not accepted or any(field not in supported_fields for field in intent.details)
            if judgment is None and needs_expansion and expansions < budget.max_expansions and (structured or len(current) < budget.max_candidates):
                phase = perf_counter()
                extra = service.store.read_indexed_snapshot(IndexedMemoryQuery(scopes=intent.scopes, query=search_text,
                    history=request.history, occurred_after=request.occurred_after, occurred_before=request.occurred_before,
                    limit=budget.max_candidates), now=now, include_chapters=False,
                    include_profile_sources=False)
                expansions += 1
                calls += 1
                rows += extra.rows_loaded
                candidates += extra.total_candidates
                timings["database_read"] += (perf_counter() - phase) * 1000
                if (extra.context_epoch, extra.index_revision, extra.index_generation) != (epoch, base.index_revision, base.index_generation):
                    stale = True
                    break
                for entry in extra.entries:
                    if entry.memory_id in current:
                        continue
                    decision = check_evidence(entry, intent, now=now, owner_id=service.owner_id, character_id=service.character_id)
                    decisions.append(decision)
                    if decision.accepted:
                        accepted.append(entry)
            conflict = _single_value_conflict(accepted, intent)
            if conflict:
                decisions.extend(EvidenceDecision(e.memory_id, False, "conflicting_single_value_facts", intent.route) for e in accepted)
                accepted = []
            phase = perf_counter()
            ranked, semantic = _rank(accepted, intent, query=query, now=now, stage=stage, retriever=retriever)
            if semantic != "disabled":
                semantic_status = semantic
            timings["ranking"] = timings.get("ranking", 0) + (perf_counter() - phase) * 1000
            ranked = _unique_current_facts(ranked, intent)[:top_k]
            selected.extend(ranked)
            if ranked:
                # One current source proves each unambiguous alias. Prefer a
                # source already delivered as answer evidence; never send all
                # unrelated facts merely because they repeat the same alias.
                ranked_ids = {m.memory_id for m in ranked}
                proof_ids = set()
                if resolution is not None:
                    for alias, ids in resolution.sources_by_input.items():
                        if ids:
                            proof_ids.add(next((key for key in ids if key in ranked_ids), ids[0]))
                for entry in alias_dependencies:
                    if entry.memory_id not in proof_ids:
                        continue
                    dependencies[entry.memory_id] = entry
                    binding_evidence[entry.memory_id] = {"memory_id": entry.memory_id,
                        "bindings": [{"alias": alias, "subjects": list(values)} for alias, values in resolution.mapping.items()
                                     if entry.memory_id in resolution.sources_by_input.get(alias, ())],
                        "source_fingerprint": entry.evidence_fingerprint(),
                        "source_ids": list(entry.source_ids), "purpose": "entity_resolution",
                        "dependent_memory_ids": list(dict.fromkeys(
                            binding_evidence.get(entry.memory_id, {}).get("dependent_memory_ids", []) +
                            [m.memory_id for m in ranked]))}
            chosen_ids = {e.memory_id for e in ranked}
            covered = {field for decision in decisions if decision.accepted and decision.memory_id in chosen_ids
                       for field in decision.supported_details}
            missing = [field for field in intent.details if field not in covered]
            applicability = ("requires_current_validation" if ranked and intent.route == "task"
                and re.search(r"保证|直接照做|照做.*成功|仍然适用|现在.*(?:适用|还能|步骤|办法|照做)|这次.*(?:适用|成功|按|照|直接)", query)
                else "historical_evidence_only" if intent.route == "task" else "")
            statuses.append({"route": intent.route, "status": "insufficient" if conflict or (ranked and missing)
                             or applicability == "requires_current_validation" else "sufficient" if ranked else "unknown",
                             "source_ids": [e.memory_id for e in ranked], "missing_details": missing,
                             **({"applicability": applicability} if applicability else {})})
            if judgment is not None and judgment.statuses[intent_index] != "sufficient":
                statuses[-1]["status"] = judgment.statuses[intent_index]
        if stale:
            continue
        # Round-robin source allocation gives each intent a chance within the
        # one global prompt budget, rather than allowing the first to consume it.
        by_id = {e.memory_id: e for e in selected}
        chosen = []
        queues = [list(status["source_ids"]) for status in statuses]
        while any(queues) and len(chosen) < top_k:
            for queue in queues:
                if queue:
                    key = queue.pop(0)
                    if key not in {m.memory_id for m in chosen}:
                        chosen.append(by_id[key])
                    if len(chosen) >= top_k:
                        break
        phase = perf_counter()
        memories = service.store.finalize_indexed_recall(tuple(chosen), expected_epoch=epoch, now=now,
            scopes=tuple(scope_set | {scope}), allow_history=any(i.temporal_mode in {"history", "as_of", "timeline"}
                or (i.temporal_mode == "planned" and i.as_of is not None) for i in plan.intents),
            dependency_entries=tuple(dependencies.values()))
        timings["finalize"] = (perf_counter() - phase) * 1000
        if memories is None:
            continue
        phase = perf_counter()
        kept = {m.memory_id for m in memories}
        for status in statuses:
            if status["status"] == "sufficient" and any(key not in kept for key in status["source_ids"]):
                status["status"] = "insufficient"
        states = [s["status"] for s in statuses if s["status"] != "not_needed"]
        status = ("not_needed" if not states else "sufficient" if all(s == "sufficient" for s in states)
                  else "external_unavailable" if all(s == "external_unavailable" for s in states)
                  else "unknown" if all(s == "unknown" for s in states) else "insufficient")
        layers = build_layers(memories, chapters=tuple(chapters.values()),
            detail=any(i.detail for i in plan.intents if i.route == "episode"), enabled=layered, budget_chars=budget.max_context_chars)
        temporal_modes = tuple(dict.fromkeys(i.temporal_mode for i in plan.intents if i.route not in {"chat", "live"}))
        prompt_policy = {"status": status, "routes": list(plan.routes), "temporal_mode": temporal_modes[0] if len(temporal_modes) == 1 else "mixed",
            "intent_status": [{"route": s["route"], "status": s["status"], "source_ids": s["source_ids"],
                               "missing_details": s.get("missing_details", []),
                               **({"applicability": s["applicability"]} if "applicability" in s else {}),
                               **({"reason": s["reason"]} if "reason" in s else {}),
                               **({"authority": s["authority"]} if "authority" in s else {})} for s in statuses],
            "evidence_level": layers.level,
            "instruction": "只依据有效来源回答具体事实；未知时自然说明没有可靠记录；部分有据时只回答有据部分；实时接口不可用不等于任务未完成。任务经验只证明当时结果，当前版本与前提未经确认时不保证照做成功。"}
        bundle = EvidenceContextBundle(profile, memories, None, epoch, retrieval=prompt_policy,
            overview=layers.overview, external_state=tuple(external), overview_source_ids=layers.represented_ids,
            resolution_evidence=tuple(binding_evidence.values()))
        # Character budgets are deterministic; tokenizer-dependent counts are
        # measured separately by the evaluator, never mislabeled as tokens.
        bundle = _bound_bundle(bundle, budget.max_context_chars, chapters=tuple(chapters.values()), layered=layered)
        status = bundle.retrieval["status"]
        context_chars = len(json.dumps(bundle.to_prompt_payload(), ensure_ascii=False))
        timings["context_assembly"] = (perf_counter() - phase) * 1000
        timings["total"] = (perf_counter() - started) * 1000
        trace = RetrievalTrace(plan.routes, plan.reason, status, calls, rows, candidates, expansions,
            tuple(m.memory_id for m in bundle.memories), timings,
            tuple(bundle.retrieval.get("intent_status", ())), tuple(decisions), revision, epoch,
            semantic_status=semantic_status, retries=attempt,
            evidence_level=bundle.retrieval.get("evidence_level", layers.level), context_chars=context_chars)
        return RetrievalResult(bundle, plan, trace)
    epoch = service.store.current_context_epoch(now=now)
    bundle = EvidenceContextBundle(CoreBondProfile(service.character_id, service.owner_id), context_epoch=epoch,
        retrieval={"status": "unavailable", "reason": "concurrent_source_changes", "instruction": "记忆正在更新，本轮不能确认旧信息。"})
    trace = RetrievalTrace(plan.routes, plan.reason, "unavailable", context_epoch=epoch, retries=3,
                           stage_ms={"total": (perf_counter() - started) * 1000})
    return RetrievalResult(bundle, plan, trace)


def expand_sources(service, source_fingerprints: Mapping[str, str], *, expected_epoch: int,
                   now: int, scope: str = "companion") -> RetrievalResult:
    """Bounded L2 read for a detail button; the caller's L1 view is not evidence.

    Fingerprints are required even if a legacy writer failed to bump the epoch.
    A caller may not expand revoked/expired material by labeling it historical.
    """
    from .emotional_memory_service import _active_memory_index, _valid_profile
    from .memory_source_spans import resolve_source_spans

    started = perf_counter()
    if (not isinstance(source_fingerprints, Mapping) or not source_fingerprints
            or len(source_fingerprints) > service.retrieval_budget.max_source_entries
            or any(not isinstance(k, str) or not isinstance(v, str) or not k or not v
                   for k, v in source_fingerprints.items())):
        raise ValueError("source expansion requires bounded source IDs and fingerprints")
    spans = resolve_source_spans(service.store, source_fingerprints, expected_epoch=expected_epoch,
        now=now, scope=scope, max_sources=service.retrieval_budget.max_source_entries)
    plan = RetrievalPlan((RetrievalIntent("source_expansion", "", scopes=(scope,), detail=True,
                                         reason="explicit_source_expansion"),))
    snapshot = service.store.read_indexed_snapshot(IndexedMemoryQuery(scopes=(scope,),
        memory_ids=tuple(source_fingerprints), limit=service.retrieval_budget.max_source_entries), now=now,
        include_chapters=False)
    memories = tuple(e for e in snapshot.entries if e.is_active(now=now, scope=scope)
                     and e.evidence_fingerprint() == source_fingerprints.get(e.memory_id))
    status = "sufficient" if len(memories) == len(source_fingerprints) else "insufficient" if memories else "unknown"
    profile = _valid_profile(snapshot.profile, _active_memory_index(snapshot.source_entries, now=now))
    if snapshot.context_epoch != expected_epoch:
        memories, status = (), "unavailable"
    else:
        verified = service.store.finalize_indexed_recall(memories, expected_epoch=expected_epoch,
            now=now, scopes=(scope,), dependency_entries=snapshot.source_entries)
        if verified is None:
            memories, status = (), "unavailable"
        else:
            memories = verified
    if status == "unavailable":
        profile = CoreBondProfile(service.character_id, service.owner_id)
    policy = {"status": status, "routes": ["source_expansion"], "evidence_level": "L2",
              "reason": "stale_projection" if status == "unavailable" else "verified_source_read",
              "source_span_status": spans["status"], "unavailable_sources": spans.get("unavailable_sources", {})}
    allowed_ids = {entry.memory_id for entry in memories}
    bundle = EvidenceContextBundle(profile, memories, None, snapshot.context_epoch, retrieval=policy,
        source_spans=tuple(row for row in spans["spans"] if row["memory_id"] in allowed_ids) if status != "unavailable" else ())
    bundle = _bound_bundle(bundle, service.retrieval_budget.max_context_chars, layered=False)
    status = bundle.retrieval["status"]
    trace = RetrievalTrace(plan.routes, plan.reason, status, retrieval_calls=1, rows_loaded=snapshot.rows_loaded,
        selected_memory_ids=tuple(e.memory_id for e in bundle.memories), context_epoch=snapshot.context_epoch,
        index_revision=snapshot.index_revision, evidence_level="L2",
        context_chars=len(json.dumps(bundle.to_prompt_payload(), ensure_ascii=False)),
        stage_ms={"total": (perf_counter() - started) * 1000})
    return RetrievalResult(bundle, plan, trace)
