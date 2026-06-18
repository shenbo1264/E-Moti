# P12-P17 Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current P11-ready desktop pet demo into a stronger AI-first companion demo whose LLM path is reliably usable, whose gameplay loop feels playable, and whose open-source release remains reproducible.

**Architecture:** Keep pet growth state local and deterministic. LLM, ASR, TTS, screen observation, and search may improve expression, speech, emotion, motion, and read-only interaction intent, but must not own inventory, relationship, memory, goals, coins, or saves. Character packs remain renderer-facing presentation units with explicit provenance, license, QA, and save namespace boundaries.

**Tech Stack:** Python 3.11, PySide6, pytest, Pillow, existing typed events/snapshot contracts, existing Windows packaging scripts, existing pixel-pet validation and release-readiness tools.

---

## Current Status Verified On 2026-06-18

### Runtime And Playability

The project can currently run as an offline Windows desktop pet demo:

- Control panel and desktop pet smoke tests passed.
- Source full regression suite passed.
- Frozen Windows app and installer artifacts are present and validated.
- Default character remains `original_oc`.
- `xingxi_pixel_pet` is an optional bundled candidate, not the default pack.
- Character switching, tray behavior, renderer fallback, local state, shop, inventory, relationship, memory, and dialogue paths are covered by automated tests.

Verification commands run on 2026-06-18:

```powershell
git status --short --untracked-files=all
git log --oneline --decorate -12
git branch --show-current
python -m json.tool assets\companion\original_oc\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-20260618\current-xingxi-pixel-pack-validation.json
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\route-scan-20260618\current-xingxi-pixel-visual-qa.json --preview artifacts\route-scan-20260618\current-xingxi-pixel-visual-qa-preview.png --fail-on-warnings
python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-20260618\current-xingxi-pixel-emote-mapping.json --markdown artifacts\route-scan-20260618\current-xingxi-pixel-emote-mapping.md
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
python tools\validate_windows_build.py --report artifacts\route-scan-20260618\current-windows-build-validation.json
```

Observed results:

- Branch: `codex/demo-worktree-cleanup`.
- Latest implementation commit before this document: `e023953 docs: record final release gate`.
- `git status --short --untracked-files=all`: `M AGENTS.md`.
- `python -m pytest`: `843 passed`.
- UI smoke: `96 passed`.
- `assets\companion\original_oc\shop_items.json`: valid JSON.
- `assets\companion\original_oc`: character pack validation `ok=true`.
- `assets\companion\xingxi_pixel_pet`: character pack validation `ok=true`.
- `assets\companion\xingxi_pixel_pet`: pixel-pet pack validation `ok=true`, distribution boundary `official_candidate`.
- Pixel-pet visual QA: `ok=true`, `status=ready`, `warnings=[]`, suspicious edge halo ratio `0.008811`.
- Pixel-pet emote mapping: `ok=true`, `status=ready`, `missing_motion_ids=[]`.
- Windows build validation: `ok=true`, app executable and installer path found.

### Current LLM Reality

The LLM integration exists, is guarded by typed events, and does not mutate growth state, but the current live provider call is not passing.

Commands run on 2026-06-18:

```powershell
python tools\llm_provider_diagnostics.py --provider deepseek --timeout-seconds 45 --report artifacts\llm_smoke\current-provider-diagnostics.json
python tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\current-deepseek-expression-cue-probe.json
python tools\release_readiness_report.py --character-pack assets\companion\xingxi_pixel_pet --llm-report artifacts\llm_smoke\current-deepseek-expression-cue-probe.json --pixel-pet-emote-mapping-report artifacts\route-scan-20260618\current-xingxi-pixel-emote-mapping.json --pixel-pet-visual-qa-report artifacts\route-scan-20260618\current-xingxi-pixel-visual-qa.json --json artifacts\route-scan-20260618\current-release-readiness-with-live-llm-failure.json --markdown artifacts\route-scan-20260618\current-release-readiness-with-live-llm-failure.md
```

Observed results:

- Provider settings diagnostic reported `ok=true`, `status=ready`, because it only checks configuration shape and key presence.
- Live DeepSeek cue probe failed with `diagnostic:provider_error`.
- A direct minimal `/chat/completions` probe returned HTTP `401` with an invalid API key message.
- State mutation guard still passed: changed fields `[]`.
- Release readiness with the current live failed LLM report is `needs_attention`: 4 ready checks, 1 attention check.

Conclusion:

- The offline pet demo is runnable and playable.
- The project currently satisfies a P11 baseline for "可演示、可复现、可解释".
- If the课题口径强调 "AI 是核心", the project should not be called finished until P12 restores live LLM verification and makes provider failures visible in the app and CLI.

---

## Requirement Fit

### Meets Current Demo Requirements

- Windows-first desktop pet: yes.
- Control panel and desktop pet modes: yes.
- Tray-friendly baseline: yes.
- Local养成状态机: yes.
- Character pack switching and validation: yes.
- Optional pixel-pet candidate pack: yes.
- LLM expression boundary through typed events: structurally yes.
- ASR/TTS/screen/search boundaries: implemented behind settings and tests.
- Reproducible QA gates: yes.
- Open-source distribution boundary: documented.

### Does Not Yet Meet The Desired AI-First Bar

- Live provider reliability is not good enough because the current DeepSeek call fails with invalid credentials.
- Provider diagnostics are too optimistic because they report ready when a key is present, even if the actual provider rejects it.
- The app needs clearer user-facing LLM test results: missing key, invalid key, quota, timeout, invalid response, unsafe event, and fallback should be distinguishable.
- AI expression still feels like a presentation layer on top of the pet loop; the next phase should make it the main source of character performance while preserving state ownership boundaries.
- The gameplay loop needs more authored moments and AI-stageable reactions so users have reasons to keep interacting beyond smoke-test actions.
- `xingxi_pixel_pet` is validated but not manually promoted as the default route; that is still a separate product decision.

---

## Recommended Execution Order

```text
P12.1 -> P12.2 -> P12.3 -> P13.1 -> P13.2 -> P14.1 -> P14.2 -> P15.1 -> P15.2 -> P16.1 -> P16.2 -> P17.1 -> P17.2
```

Do P12 first. The project should not spend more time polishing art or gameplay while the live LLM path cannot be truthfully verified.

---

## P12: LLM Reliability And Truthful Diagnostics

**Purpose:** Make live LLM usage operationally reliable and debuggable. A user should know whether the provider is missing, invalid, out of quota, timed out, returning invalid JSON, or being rejected by event validation.

**Out of scope:** LLM state ownership, autonomous control, wake word, background listening, mouse/keyboard/clipboard/window control.

### Task P12.1: Preserve Redacted Provider Error Causes

**Files:**

- Modify: `src/guanghe_companion/expression_clients.py`
- Modify: `src/guanghe_companion/expression_diagnostics.py`
- Modify: `tests/test_expression_clients.py`
- Modify: `tests/test_expression_diagnostics.py`

- [ ] Add a failing test in `tests/test_expression_clients.py` that injects an HTTP 401 response through a fake transport and asserts the raised `LLMProviderError` includes a redacted reason such as `http_401` or `authentication_error`, without including the API key.
- [ ] Add a failing test in `tests/test_expression_diagnostics.py` where the expressor raises that provider error, and assert `test_provider()` returns `stage="provider_call"` and `reason="http_401"` or `reason="authentication_error"`.
- [ ] Implement a small `LLMProviderError` shape or helper that can carry a public reason while preserving the existing string behavior for old tests.
- [ ] Update `OpenAIResponsesClient`, `OpenAICompatibleChatClient`, and `fetch_provider_model_ids` to classify HTTP status codes into public reasons: `http_401`, `http_403`, `http_429`, `timeout`, `network_error`, `provider_error`.
- [ ] Ensure provider response bodies are never copied into public reports unless sanitized and size-limited.
- [ ] Run:

```powershell
python -m pytest tests\test_expression_clients.py tests\test_expression_diagnostics.py -q
python -m pytest tests\test_llm_smoke.py tests\test_expression_event_pipeline.py tests\test_visual_actions.py -q
python -m pytest
```

Acceptance:

- Invalid-key failures are reported as authentication or HTTP 401, not generic `provider_error`.
- No API key appears in test output, JSON reports, or git-tracked files.
- State mutation guard remains unchanged and passing.

### Task P12.2: Add A Live Provider Matrix Smoke

**Files:**

- Create: `tools/llm_provider_matrix.py`
- Create: `tests/test_llm_provider_matrix_tool.py`
- Modify: `docs/llm_expression_operations.md`
- Modify: `README.md`

- [ ] Add tests for a provider matrix report that can mark each provider as `ready`, `missing_api_key`, `auth_failed`, `quota_or_rate_limited`, `timeout`, `invalid_response`, or `not_configured`.
- [ ] Implement a CLI that can run dry-run checks for `deepseek`, `openrouter`, `ollama`, `lmstudio`, and `custom`.
- [ ] For network providers, only perform live calls when the relevant env var is present.
- [ ] For local providers, probe `/models` with short timeout and no API key.
- [ ] Write JSON and Markdown reports under ignored `artifacts\llm_smoke\`.
- [ ] Document the recommended dev matrix:

```text
DeepSeek for low-cost cloud smoke
OpenRouter as alternate cloud smoke
Ollama or LM Studio as local no-key fallback
```

- [ ] Run:

```powershell
python -m pytest tests\test_llm_provider_matrix_tool.py -q
python tools\llm_provider_matrix.py --dry-run --report artifacts\llm_smoke\provider-matrix-dry-run.json --markdown artifacts\llm_smoke\provider-matrix-dry-run.md
python -m pytest
```

Acceptance:

- A failed cloud key no longer blocks local-provider verification.
- Release notes can say exactly which providers were live-tested and which were not configured.

### Task P12.3: Make The App's Provider Test Action Explain Failures

**Files:**

- Modify: `src/guanghe_companion/app.py`
- Modify: `src/guanghe_companion/expression_diagnostic_view.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_expression_diagnostic_view.py`

- [ ] Add tests that render diagnostic messages for `missing_api_key`, `http_401`, `http_429`, `timeout`, `invalid_response_json`, `unsafe_event`, and `state_mutated`.
- [ ] Update the provider test UI text so users see a direct action: set API key, check quota, change model, increase timeout, or review unsafe event output.
- [ ] Keep API keys out of labels, logs, screenshots, and report JSON.
- [ ] Run:

```powershell
python -m pytest tests\test_expression_diagnostic_view.py tests\test_app.py -q
python -m pytest tests\test_desktop_pet_smoke.py -q
python -m pytest
```

Acceptance:

- A user can diagnose why LLM is not active without reading terminal output.
- The UI still does not allow LLM to mutate growth state.

---

## P13: AI Character Performance Layer

**Purpose:** Make AI expression central to the companion feeling: concise Chinese speech, emotional mirroring, expression/motion cue choice, and safe read-only interaction intent.

**Out of scope:** Memory writes by LLM, autonomous task execution, hidden system narration, state mutation.

### Task P13.1: Character Performance Profiles

**Files:**

- Create: `src/guanghe_companion/character_performance_profile.py`
- Modify: `src/guanghe_companion/companion_dialogue_policy.py`
- Modify: `src/guanghe_companion/expression_expressor.py`
- Modify: `tests/test_companion_dialogue_policy.py`
- Modify: `tests/test_ai_expressor.py`

- [ ] Add a pure loader that derives speech style, allowed expression ids, preferred motion families, and forbidden claims from the active character pack.
- [ ] Keep `original_oc` and `xingxi_pixel_pet` behavior compatible with the current prompt contract.
- [ ] Add tests proving profile data is prompt-visible but cannot inject state mutation instructions.
- [ ] Run:

```powershell
python -m pytest tests\test_companion_dialogue_policy.py tests\test_ai_expressor.py -q
python -m pytest tests\test_expression_event_pipeline.py tests\test_visual_actions.py -q
python -m pytest
```

Acceptance:

- AI output is guided by the selected character pack.
- The prompt still says LLM cannot modify state, inventory, relationship, memory, goals, coins, or saves.

### Task P13.2: Player-Like Conversation Evaluation Set

**Files:**

- Create: `tests/fixtures/llm_conversation_scenarios.json`
- Modify: `src/guanghe_companion/llm_smoke.py`
- Modify: `tests/test_llm_smoke.py`
- Modify: `docs/llm_expression_operations.md`

- [ ] Replace purely mechanical smoke prompts with a versioned scenario fixture covering comfort, celebration, boredom, focus, tiredness, gift, shop, character switch, and confused user input.
- [ ] Keep deterministic offline tests for fixture loading and report shape.
- [ ] Extend live smoke review to count expression coverage, motion coverage, fallback count, unsafe event count, and speech length violations.
- [ ] Run:

```powershell
python -m pytest tests\test_llm_smoke.py tests\test_llm_smoke_review.py -q
python tools\llm_dialogue_smoke.py --provider deepseek --dry-run --report artifacts\llm_smoke\dialogue-smoke-dry-run.json
python -m pytest
```

Acceptance:

- Smoke reports reflect actual player-like usage rather than synthetic "turn N" prompts.
- Live smoke remains optional when no valid provider credential is available.

---

## P14: Playable Companion Loop

**Purpose:** Improve the game feel so the demo is not just a settings panel plus animated sprite.

**Out of scope:** Changing the product into a productivity coach, course supervisor, or autonomous agent.

### Task P14.1: Daily Moment And Reaction System

**Files:**

- Create: `src/guanghe_companion/companion_moments.py`
- Modify: `src/guanghe_companion/controller.py`
- Modify: `src/guanghe_companion/events.py`
- Modify: `tests/test_controller.py`
- Create: `tests/test_companion_moments.py`

- [ ] Add deterministic local moment candidates such as morning greeting, low charge, high trust, return after idle, and post-gift reaction.
- [ ] Emit typed events only; do not write direct LLM state.
- [ ] Allow LLM to phrase or stage the moment when enabled, while the controller still owns state transitions.
- [ ] Run:

```powershell
python -m pytest tests\test_companion_moments.py tests\test_controller.py tests\test_events.py -q
python -m pytest tests\test_expression_event_pipeline.py -q
python -m pytest
```

Acceptance:

- The pet has more spontaneous-feeling reactions without background privacy escalation.
- Moment triggering is deterministic and testable.

### Task P14.2: Short-Term Play Session Goals

**Files:**

- Create: `src/guanghe_companion/session_goals.py`
- Modify: `src/guanghe_companion/snapshot.py`
- Modify: `src/guanghe_companion/controller.py`
- Modify: `tests/test_snapshot.py`
- Modify: `tests/test_controller.py`

- [ ] Add lightweight session goals such as "interact twice", "give a gift", "rest once", or "switch expression route".
- [ ] Keep rewards controlled by the local controller.
- [ ] Expose current goal and next suggested safe action in the typed snapshot.
- [ ] Run:

```powershell
python -m pytest tests\test_snapshot.py tests\test_controller.py -q
python -m pytest
```

Acceptance:

- A user has a visible reason to keep playing for several minutes.
- LLM may comment on a session goal but cannot complete it by itself.

---

## P15: Character Independence And UGC Workflow

**Purpose:** Make character switching feel like a real multi-character system rather than a skin picker.

**Out of scope:** Bundling third-party fanwork packs without rights clearance.

### Task P15.1: Save Namespace Review And Hardening

**Files:**

- Modify: `src/guanghe_companion/character_session.py`
- Modify: `src/guanghe_companion/storage.py`
- Modify: `tests/test_character_session.py`
- Modify: `tests/test_storage.py`

- [ ] Add tests proving each character has isolated save data, dialogue history, local memory, and pack metadata.
- [ ] Add migration behavior only if current saves can collide; otherwise document that current isolation is already sufficient.
- [ ] Run:

```powershell
python -m pytest tests\test_character_session.py tests\test_storage.py -q
python -m pytest
```

Acceptance:

- Switching characters cannot leak another character's memory or progression.
- `data\companion_save.json` remains untracked.

### Task P15.2: Character Library UX Polish

**Files:**

- Modify: `src/guanghe_companion/app.py`
- Modify: `src/guanghe_companion/character_library_view_model.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_character_library_view_model.py`
- Modify: `tests/test_desktop_pet_smoke.py`

- [ ] Make the character library distinguish default official, optional official candidate, local UGC, and private fanwork.
- [ ] Add visible readiness labels for provenance, license, visual QA, and manual QA status.
- [ ] Keep the UI compact and utilitarian; avoid landing-page styling.
- [ ] Run:

```powershell
python -m pytest tests\test_character_library_view_model.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
```

Acceptance:

- A user can safely select a character without confusing bundled original assets with local fanwork.

---

## P16: Pixel-Pet Art And Motion Expansion

**Purpose:** Improve the visual liveliness of the active sprite route while avoiding unreviewed asset churn.

**Out of scope:** Live2D production, AI-video motion extraction, default promotion without explicit approval.

### Task P16.1: Add One New Motion Row Through The Existing QA Loop

**Files:**

- Modify only after QA: `assets/companion/xingxi_pixel_pet/spritesheet.png`
- Modify only after QA: `assets/companion/xingxi_pixel_pet/motion_manifest.json`
- Modify only after QA: `assets/companion/xingxi_pixel_pet/provenance.md`
- Use ignored artifacts first: `artifacts/pixel-pet-sequence-drafts/`

- [ ] Generate or draw one row only, such as blink-breathing, shy, confused, or happy hop.
- [ ] Produce contact sheet and visual QA report under ignored artifacts.
- [ ] Reject or repair the row if geometry, alpha, frame count, or edge halo fails.
- [ ] Promote the row into `assets\companion\xingxi_pixel_pet` only after human visual approval.
- [ ] Run after promotion:

```powershell
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-20260618\p16-xingxi-pixel-pack-validation.json
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\route-scan-20260618\p16-xingxi-pixel-visual-qa.json --preview artifacts\route-scan-20260618\p16-xingxi-pixel-visual-qa-preview.png --fail-on-warnings
python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-20260618\p16-xingxi-pixel-emote-mapping.json --markdown artifacts\route-scan-20260618\p16-xingxi-pixel-emote-mapping.md
python -m pytest tests\test_pixel_pet_pack_validator_tool.py tests\test_pixel_pet_visual_qa.py tests\test_pixel_pet_emote_mapping.py -q
python -m pytest
```

Acceptance:

- One new row improves perceived liveliness and passes every gate.
- No unapproved Ikaros or Nairong asset is committed.

### Task P16.2: Default Promotion Decision Package

**Files:**

- Modify only if approved: `src/guanghe_companion/character_pack.py`
- Modify only if approved: `README.md`
- Create: `docs/default_character_decision_2026-07.md`
- Modify: packaging validation artifacts after rebuild

- [ ] Stop for explicit approval before changing the default from `original_oc`.
- [ ] If approved, update the default character constant and all docs that describe the runtime default.
- [ ] Run source, UI, build, installer, and frozen app validation:

```powershell
python -m pytest tests\test_character_pack.py tests\test_character_registry.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --character-id xingxi_pixel_pet --report artifacts\windows-build-validation-xingxi-pixel-pet.json
```

Acceptance:

- Default promotion is intentional, documented, packaged, and reversible by commit.

---

## P17: Final Public Release Package

**Purpose:** Produce a public-ready repository state with current docs, passing tests, no secrets, and rebuilt release artifacts when required.

### Task P17.1: Public Documentation And Hygiene Pass

**Files:**

- Modify: `README.md`
- Modify: `docs/open_source_release_checklist.md`
- Modify: `docs/final_release_gate_2026-06.md` or create a new dated final gate document
- Modify: `tests/test_repository_hygiene.py`

- [ ] Remove or quarantine old route docs only if they contradict the active route and are not needed as historical records.
- [ ] Keep docs clear that `original_oc` is default unless P16.2 changed it.
- [ ] Add hygiene tests for any new ignored artifact class.
- [ ] Run:

```powershell
git status --short --untracked-files=all
git grep -n -E "sk-[A-Za-z0-9_-]{16,}|api[_-]?key" -- . ":!artifacts" ":!dist"
python -m pytest tests\test_repository_hygiene.py -q
python -m pytest
```

Acceptance:

- The repository can be opened by an external developer without private context.
- API keys, runtime saves, and local fanwork assets are not tracked.

### Task P17.2: Final Release Gate

**Files:**

- Create: `docs/final_release_gate_2026-07.md`
- Write ignored reports under: `artifacts/route-scan-202607/`

- [ ] Run final source and asset gates:

```powershell
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-202607\final-xingxi-pixel-pack-validation.json
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\route-scan-202607\final-xingxi-pixel-visual-qa.json --preview artifacts\route-scan-202607\final-xingxi-pixel-visual-qa-preview.png --fail-on-warnings
python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-202607\final-xingxi-pixel-emote-mapping.json --markdown artifacts\route-scan-202607\final-xingxi-pixel-emote-mapping.md
```

- [ ] Run live LLM gate only with a currently valid provider key or local provider:

```powershell
python tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\final-deepseek-expression-cue-probe.json
```

- [ ] Run UI and release gates:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python tools\release_readiness_report.py --character-pack assets\companion\xingxi_pixel_pet --llm-report artifacts\llm_smoke\final-deepseek-expression-cue-probe.json --pixel-pet-emote-mapping-report artifacts\route-scan-202607\final-xingxi-pixel-emote-mapping.json --pixel-pet-visual-qa-report artifacts\route-scan-202607\final-xingxi-pixel-visual-qa.json --json artifacts\route-scan-202607\final-release-readiness.json --markdown artifacts\route-scan-202607\final-release-readiness.md
```

- [ ] Rebuild packaging if P16.2 changed default assets, packaging scripts, installer behavior, dependencies, or bundled assets:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\route-scan-202607\windows-build-validation.json
```

Acceptance:

- Release readiness is `ready`.
- Live LLM report is current and passing, or the final gate explicitly says "offline demo only; AI provider not verified".
- Final document lists exact commands, exact results, known limitations, and distribution boundaries.

---

## Hard Stops

Stop for explicit user confirmation before:

- Promoting `xingxi_pixel_pet` or any other pack to default.
- Bundling Ikaros, Nairong, or any third-party/fanwork assets.
- Adding mouse, keyboard, clipboard, window control, wake word, background listening, startup persistence, elevated install, or system-level automation.
- Changing installer behavior, install path, privileges, or auto-start policy.
- Adding a new runtime dependency that affects packaging.
- Publishing, pushing, opening a PR, merging branches, or changing remotes.

## Definition Of Done For The Next Goal

- P12 live LLM diagnostic is truthful and actionable.
- At least one live or local provider path passes current cue probe.
- AI expression remains typed-event-only and state-safe.
- The pet has a stronger short-session play loop.
- Character switching preserves independent state and distribution boundaries.
- Any new art row passes visual QA before entering `assets\companion`.
- Final full `python -m pytest` passes.
- UI smoke tests pass after any UI or renderer change.
- Packaging is rebuilt after any default asset, dependency, or installer behavior change.
- `git status --short --untracked-files=all` is understood.
- `data\companion_save.json`, API keys, local fanwork, and ignored smoke artifacts are not committed.
