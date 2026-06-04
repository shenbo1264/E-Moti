# AI Companion P0-P4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Xingxi feel like a real LLM-centered AI desktop companion while keeping local growth state, inventory, unlocks, saves, and relationship settlement authoritative.

**Architecture:** LLM and perception services generate only validated expression context and speech events. Local Python services own all state mutation: growth stats, inventory, memories, relationship unlocks, proactive policy, and persistence. Each implementation package must include tests proving LLM/perception/search/TTS/ASR cannot mutate growth state unless a local deterministic service explicitly does so.

**Tech Stack:** Python 3.11, PySide6, pytest, local JSON stores, OpenAI-compatible chat completions, OpenAI responses API, Ollama/LM Studio compatible endpoints.

---

## Current Evidence Baseline

- Branch: `codex/demo-worktree-cleanup`.
- Latest local feature commits before this plan: `ba4bd83 feat: support local llm expression providers`, `70d7130 feat: use llm expression for dialogue submits`.
- Dirty runtime file: `data/companion_save.json`. Do not stage or commit it.
- Current LLM boundary: `src/guanghe_companion/ai_expressor.py` accepts only expression request fields and returns validated speech events.
- Current dialogue boundary: `src/guanghe_companion/controller.py` stores dialogue history but does not mutate stats, inventory, relationship stage, unlocks, or memory log on normal dialogue submit.

## External Demand Signals

Forum research suggests users want long-term continuity, stable personality, proactive but non-intrusive companionship, and visible relationship growth. Users are skeptical of black-box autonomy that silently changes relationship, memory, personality, inventory, or rewards. Product direction: AI should be more expressive and contextual, but state changes must remain inspectable, reversible where appropriate, and locally governed.

## Cross-Cutting Rules

- Never write or log API keys in source, docs, tests, fixtures, screenshots, or command history artifacts.
- Never stage `data/companion_save.json`.
- LLM output schema remains expression-only: `type`, `speech`, `effect`, `motion_hint`.
- LLM must not write `CompanionState`, inventory, relationship unlocks, memory stores, goals, or save files.
- ASR text must enter through `DialogueRequest`.
- TTS may consume only typed validated Xingxi speech events.
- Screen observation, web search, and future desktop sensing may enter only read-only expression context.
- No mouse, keyboard, clipboard, or window control in this plan.
- Each package ends with targeted tests and `python -m pytest`.

---

## Package P0: LLM Usability and Diagnostics

**Owner:** Main thread first; subagent review after implementation.

**Files:**
- Modify: `src/guanghe_companion/ai_expressor.py`
- Modify: `src/guanghe_companion/controller.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_ai_expressor.py`
- Test: `tests/test_controller.py`
- Test: `tests/test_app.py`

**Implementation:**

- [ ] Add a structured diagnostic result that never contains API keys:
  - `ok: bool`
  - `stage: settings | model_list | prompt | provider_call | provider_parse | event_validation`
  - `reason: missing_api_key | disabled | timeout | provider_error | invalid_response_json | invalid_response_text | invalid_event | local_fallback`
  - `provider`, `model`, `base_url`, `timeout_seconds`
  - `speech`, `effect`
- [ ] Keep `CompanionController.test_expression_provider()` non-mutating and return the diagnostic fields.
- [ ] Update UI test status text so users see the exact failed stage and reason.
- [ ] Preserve current success path for DeepSeek/OpenAI-compatible/local providers.
- [ ] Add tests for missing key, provider exception, invalid JSON, unsafe event, local fallback, and success.
- [ ] Run:
  - `python -m pytest tests/test_ai_expressor.py tests/test_controller.py tests/test_app.py`
  - `python -m pytest`
  - `python -m json.tool assets\companion\original_oc\shop_items.json`
  - repository key scan with the real key pattern excluded from output.

**Acceptance:**

- LLM settings page can test model/provider and report a useful failure reason.
- Dialogue submit uses enabled LLM expression and still does not mutate growth state.
- A real DeepSeek smoke may be run with an environment variable or transient in-memory settings only.

## Package P1: Local Long-Term Memory

**Owner:** Worker agent with exclusive write scope over memory/runtime/snapshot/expressor tests, then main-thread integration.

**Files:**
- Modify: `src/guanghe_companion/memory.py`
- Modify: `src/guanghe_companion/runtime_paths.py`
- Modify: `src/guanghe_companion/controller.py`
- Modify: `src/guanghe_companion/snapshot.py`
- Modify: `src/guanghe_companion/ai_expressor.py`
- Test: `tests/test_memory.py`
- Test: `tests/test_runtime_paths.py`
- Test: `tests/test_controller.py`
- Test: `tests/test_snapshot.py`
- Test: `tests/test_ai_expressor.py`

**Implementation:**

- [ ] Add `LongTermMemoryEntry` with `key`, `category`, `summary`, `source`, `created_at`, `updated_at`.
- [ ] Add `LongTermMemoryStore` JSON round-trip with bad-file fallback to empty.
- [ ] Add deterministic `LongTermMemoryService.upsert()` with max 50 entries and key-based replacement.
- [ ] Add runtime path `long_term_memory_path()`.
- [ ] Load long-term memory in controller startup.
- [ ] Write long-term memory only from deterministic local events, initially relationship unlocks and explicit local APIs.
- [ ] Expose bounded read-only summaries in typed snapshot and `ExpressionRequest`.
- [ ] Reject or ignore any LLM returned fields named `memory`, `state`, `coins`, `inventory`, `relationship`, `goal`, or `save`.

**Acceptance:**

- Long-term memory can be viewed through snapshot and used by prompt context.
- Normal dialogue and LLM speech do not write long-term memory.
- Local deterministic unlock events can upsert memory.
- Bad memory JSON does not crash startup.

## Package P2: Low-Frequency Proactive Companionship

**Owner:** Worker agent with exclusive write scope over proactive settings/service/controller tests, then main-thread integration.

**Files:**
- Modify: `src/guanghe_companion/capability_settings.py`
- Create or modify: `src/guanghe_companion/proactive_companion.py`
- Modify: `src/guanghe_companion/controller.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_capability_settings.py`
- Create or modify: `tests/test_proactive_companion.py`
- Modify: `tests/test_controller.py`
- Modify: `tests/test_app.py`

**Implementation:**

- [ ] Add `ProactiveCompanionSettings`:
  - `enabled=False`
  - `interval_seconds=900`
  - `global_cooldown_seconds=1800`
  - `daily_limit=8`
  - `quiet_hours_enabled=False`
  - `quiet_start="23:00"`
  - `quiet_end="08:00"`
  - `allow_context_topic=True`
- [ ] Gate existing proactive feedback behind the new settings without changing default behavior for tests unless explicitly enabled.
- [ ] Add cooldown, daily cap, and quiet-hour checks.
- [ ] Add optional context-topic trigger from read-only `perception_summary` / `tool_results`.
- [ ] Prove proactive code never calls `apply_action()`.
- [ ] Add UI controls in capability/privacy area.

**Acceptance:**

- Defaults do not surprise users.
- When enabled, proactive messages are rare, bounded, and visible.
- No stats, coins, inventory, unlocks, or `last_interaction_at` are changed by proactive speech itself.

## Package P3: Light Desktop Sensing

**Owner:** Same worker as P2 only if no file conflict; otherwise separate follow-up after P2 merge.

**Files:**
- Modify: `src/guanghe_companion/screen_observation.py`
- Modify: `src/guanghe_companion/expression_context.py`
- Modify: `src/guanghe_companion/capability_settings.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_screen_observation.py`
- Test: `tests/test_expression_context.py`
- Test: `tests/test_capability_settings.py`
- Test: `tests/test_app.py`

**Implementation:**

- [ ] Keep automatic screenshot disabled by default.
- [ ] Add explicit wording and diagnostics for manual observation.
- [ ] Preserve read-only expression context flow.
- [ ] If app/window metadata is added later, store only bounded summaries and user-visible toggles.
- [ ] No keyboard/mouse/clipboard/window control.

**Acceptance:**

- Sensing improves LLM expression context but never mutates growth state.
- User can tell when sensing is off, manual, or automatic.

## Package P4: Visible Growth Changes

**Owner:** Worker agent with exclusive write scope over relationship presentation/snapshot/UI tests, then main-thread integration.

**Files:**
- Modify: `src/guanghe_companion/models.py`
- Modify: `src/guanghe_companion/relationship.py`
- Modify: `src/guanghe_companion/snapshot.py`
- Modify: `src/guanghe_companion/app.py`
- Modify: `assets/companion/original_oc/character.json`
- Test: `tests/test_relationship.py`
- Test: `tests/test_snapshot.py`
- Test: `tests/test_app.py`
- Test: `tests/test_character_pack.py`

**Implementation:**

- [ ] Add deterministic player alias field or local profile structure.
- [ ] Add local-only alias setter; do not route alias setting through LLM output.
- [ ] Add `RelationshipPresentation` derived from state:
  - `address_line`
  - `tone_label`
  - `micro_motion`
  - `unlocked_decorations`
- [ ] Use existing item icons as decoration badges; do not modify spritesheet in this package.
- [ ] Expose relationship presentation in snapshot and UI.
- [ ] Feed bounded presentation labels to LLM as read-only style context.

**Acceptance:**

- Users can see that Xingxi remembers a name or address.
- Tone and small motion labels change by relationship stage.
- LLM cannot change alias or presentation unlocks.

---

## Subagent Dispatch Plan

- Main thread: P0 implementation and integration.
- Worker A: P1 long-term memory implementation. Avoid UI edits except snapshot exposure tests.
- Worker B: P2 proactive settings and policy implementation. Avoid screen observation internals unless P2 is complete.
- Worker C: P4 relationship presentation implementation. Avoid long-term memory files and proactive settings.
- Review agents: after each worker returns, run spec compliance review then code quality review before merging.

## Verification Gate

Run after every merged package:

```powershell
git status --short --untracked-files=all
python -m pytest tests/test_ai_expressor.py tests/test_controller.py
python -m pytest tests/test_app.py tests/test_desktop_pet_smoke.py
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
rg -n "sk-[A-Za-z0-9_-]{16,}|api[_-]?key\\s*[:=]\\s*['\\\"]" --glob "!data/companion_save.json" .
```

Commit each package separately and never include `data/companion_save.json`.
