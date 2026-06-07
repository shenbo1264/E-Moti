# Low-Coupling P0-P5 Roadmap

Date: 2026-06-07

## Current Verified Baseline

- Branch: `codex/demo-worktree-cleanup`
- Current checked head: `1023635 feat: gate draft character pack import`
- Original plan baseline: `c0fd88a test: add portrait asset qa guardrails`
- Dirty workspace expected item: `data/companion_save.json` only; do not stage it.
- Latest focused import/character/UI route tests run on 2026-06-07:

```powershell
python -m pytest tests\test_character_pack_import_tool.py tests\test_character_draft_validator_tool.py tests\test_character_pack_validator_tool.py tests\test_character_registry.py tests\test_app.py -q
python -m pytest tests\test_desktop_pet_smoke.py -q
```

Result: `115 passed`; `6 passed`.

Full suite run on 2026-06-07:

```powershell
python -m pytest
```

Result: `580 passed`.

Latest non-confirmation packages completed after the original plan:

- `cdf2caf feat: add character draft creation tool`
  - Added a local CLI for `CharacterGenerationWorkflow`.
  - Does not generate images, import packs, call networks, or write app state.
- `d2c020a test: guard llm smoke state mutations`
  - Expanded LLM smoke state guard beyond numeric growth fields to identity, inventory, relationship, memory, and motion surfaces.
  - No live provider call was made.
- `fdc65b7 test: gate draft portrait approval flags`
  - Requires `approval_required=false` and `runtime_manifest_safe=true` before a draft can report `import_ready=true`.
- `1023635 feat: gate draft character pack import`
  - Prevents a complete-looking generated draft with unsafe `portrait_candidate.json` metadata from being imported as a user pack.
  - Ordinary complete pack import remains supported.

## Product Rule

AI is the core performance layer, not the state owner.

Allowed:

- LLM chooses companion speech through validated typed events.
- LLM chooses presentational expression, motion hints, and read-only interaction intents through typed `visual_actions`.
- Screen observation and search can enrich read-only expression context.
- TTS consumes validated companion speech.
- ASR creates player text and must flow through `DialogueRequest`.

Forbidden:

- LLM, screen observation, search, TTS, or ASR mutate growth state, inventory, relationship, memory, goals, coins, or save files.
- Renderer modules write state or schedule OS-level control.
- Unapproved art assets are referenced by default manifests.

## Low-Coupling Slices

### P0: Baseline And Guardrails

Goal: Keep the project demonstrable while the AI and art routes evolve.

Scope:

- Preserve sprite fallback, portrait renderer fallback, tray behavior, character switching, LLM smoke route, and packaging scripts.
- Keep `data/companion_save.json` uncommitted.
- Keep the current placeholder portrait assets marked as smoke baseline only.
- Keep the route guardrail that default packs cannot enable blink unless structured blink frames exist.

Primary files:

- `tests/test_spirit_stage.py`
- `tests/test_character_registry.py`
- `assets/companion/original_oc/portrait_assets_provenance.md`

Acceptance:

```powershell
python -m json.tool assets\companion\original_oc\portrait_manifest.json
python tools\validate_character_pack.py assets\companion\original_oc
python -m pytest tests\test_spirit_stage.py tests\test_character_registry.py tests\test_character_pack.py -q
python -m pytest
```

Stop for confirmation:

- Before deleting, rewriting, or replacing committed art.
- Before rewriting git history after a push.

### P1: AI Performance Debug Loop

Goal: Make LLM behavior observable, testable, and tunable before adding more art.

Scope:

- Add a small expression debug report object or service that exposes:
  - provider/settings stage;
  - prompt preview;
  - raw provider outcome category;
  - parsed speech;
  - parsed visual actions;
  - fallback reason;
  - state mutation check result.
- Surface this in the existing expression diagnostics path or a compact UI/debug panel.
- Add a live smoke path for OpenAI-compatible providers, especially DeepSeek.

Primary files:

- `src/guanghe_companion/expression_diagnostics.py`
- `src/guanghe_companion/expression_clients.py`
- `src/guanghe_companion/llm_smoke.py`
- `tools/llm_dialogue_smoke.py`
- `tests/test_llm_smoke.py`
- `tests/test_expression_diagnostics.py`
- `tests/test_expression_event_pipeline.py`

External reference:

- DeepSeek officially exposes an OpenAI-compatible `chat/completions` route with base URL `https://api.deepseek.com`, and newer model names include `deepseek-v4-flash` / `deepseek-v4-pro`: [DeepSeek first API call](https://api-docs.deepseek.com/), [DeepSeek API updates](https://api-docs.deepseek.com/updates/).

Acceptance:

```powershell
python -m pytest tests\test_ai_expressor.py tests\test_expression_clients.py tests\test_expression_diagnostics.py tests\test_expression_event_pipeline.py tests\test_visual_actions.py tests\test_llm_smoke.py -q
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
```

Stop for confirmation:

- Before using a real paid API key.
- Before persisting provider responses or prompts outside existing debug/test outputs.
- Before changing prompt policy or character personality.

### P2: Portrait Asset Gate

Goal: Prevent bad generated assets from reaching default runtime manifests.

Scope:

- Add project-local tools for portrait candidate validation:
  - image contract validation;
  - contact sheet generation;
  - manifest reference verification;
  - candidate status tracking: `candidate`, `rejected`, `approved`.
- Keep visual judgment human-gated. Automation checks only hard constraints.

Primary files:

- `tools/art/`
- `tests/test_art_tools.py`
- `tests/test_character_registry.py`
- `assets/companion/original_oc/portrait_assets_provenance.md`

Acceptance:

```powershell
python -m pytest tests\test_art_tools.py tests\test_character_registry.py tests\test_spirit_stage.py -q
python tools\validate_character_pack.py assets\companion\original_oc
python -m pytest
```

Stop for confirmation:

- Before committing any new final art.
- Before updating `portrait_manifest.json` to point at new art.
- Before using generated assets for public-facing screenshots.

### P3: Approved VN Portrait Candidate

Goal: Produce a high-body VN portrait candidate without coupling generation to runtime.

Scope:

- Generate one base standing portrait candidate first.
- Show it as an artifact only.
- After human approval, generate or edit a small expression set.
- Produce contact sheet and QA notes.
- Only after approval, update `portrait_manifest.json`.

Primary files after approval only:

- `assets/companion/original_oc/portraits/<approved-set>/`
- `assets/companion/original_oc/preview/<approved-contact-sheet>.png`
- `assets/companion/original_oc/portrait_manifest.json`
- `assets/companion/original_oc/portrait_assets_provenance.md`

Acceptance after manifest integration:

```powershell
python -m json.tool assets\companion\original_oc\portrait_manifest.json
python tools\validate_character_pack.py assets\companion\original_oc
python -m pytest tests\test_spirit_stage.py tests\test_character_registry.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
```

Stop for confirmation:

- After the first base portrait candidate.
- After the expression/contact sheet candidate.
- Before changing the default runtime manifest.

### P4: Character Pack Personalization

Goal: Let users create or switch character packs without binding the product to Xingxi only.

Scope:

- Strengthen `CharacterGenerationWorkflow` from draft metadata into a gated pack workflow.
- Keep every character isolated:
  - art assets;
  - `character.json`;
  - `dialogue_style.json`;
  - renderer manifest;
  - memory/save namespace;
  - provenance and QA checklist.
- Keep fanwork/private packs out of the open-source default assets.

Primary files:

- `src/guanghe_companion/character_generation_workflow.py`
- `src/guanghe_companion/character_registry.py`
- `src/guanghe_companion/character_session.py`
- `tests/test_character_generation_workflow.py`
- `tests/test_character_registry.py`
- `tests/test_character_session.py`

Acceptance:

```powershell
python -m pytest tests\test_character_generation_workflow.py tests\test_character_registry.py tests\test_character_session.py tests\test_app.py -q
python -m pytest
```

Stop for confirmation:

- Before adding online character search or fanwork reconstruction.
- Before including any third-party-inspired art, prompt, source text, or setting.
- Before changing save namespace behavior.

### P5: Rigged Renderer And Release Gate

Goal: Keep Live2D/Inochi2D as a later renderer path, not a blocker for the Spirit route.

Scope:

- Evaluate runtime feasibility only after P1/P2 are stable.
- Keep renderer adapters consuming the same typed `visual_actions`.
- Do not mix Live2D/Inochi2D runtime work with art generation, LLM prompt work, or packaging changes.
- Preserve current app/installer release checks for any package that changes UI/assets/runtime.

External references:

- Live2D Cubism SDK for Web is the official route for using Cubism models programmatically; `.model3.json` references model-related runtime files, and motion/expression data uses `.motion3.json` / `.exp3.json` paths: [Cubism SDK for Web](https://docs.live2d.com/en/cubism-sdk-manual/cubism-sdk-for-web/), [About Models Web](https://docs.live2d.com/en/cubism-sdk-manual/model-web/), [About Expression Motion](https://docs.live2d.com/en/cubism-sdk-manual/expression/).
- Inochi2D is an open-source real-time 2D puppet animation specification and tooling stack: [Inochi2D documentation](https://docs.inochi2d.com/en/latest/index.html), [About Inochi2D](https://docs.inochi2d.com/en/latest/inochi2d/about.html).

Primary files:

- `src/guanghe_companion/live2d_web.py`
- `src/guanghe_companion/presentation_renderer.py`
- `tests/test_live2d_web.py`
- `tests/test_presentation_renderer.py`
- packaging scripts only if release behavior changes.

Acceptance:

```powershell
python -m pytest tests\test_live2d_web.py tests\test_presentation_renderer.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
```

Packaging acceptance if runtime or installer behavior changes:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
```

Stop for confirmation:

- Before adding dependencies.
- Before bundling third-party models.
- Before changing packaging or installer behavior.
- Before choosing Live2D proprietary runtime versus Inochi2D open-source runtime as the committed route.

## Recommended Execution Order

1. P1 first: AI performance debug loop and real provider smoke.
2. P2 second: portrait asset gate.
3. P3 third: one approved VN candidate, then manifest integration.
4. P4 fourth: character pack personalization.
5. P5 last: rigged renderer feasibility and release packaging.

Rationale:

- P1 proves the AI core works before spending more time on art.
- P2 prevents another bad asset from entering default runtime.
- P3 becomes safer after P2 exists.
- P4 depends on the same asset and renderer contracts.
- P5 needs real rigged assets and should not block the lower-risk Spirit route.

## Next Recommended Package

The remaining high-value packages now cross explicit confirmation boundaries:

```text
P1-live: run a real DeepSeek/OpenAI-compatible LLM smoke
P3-art-candidate: produce a formal Spirit/VN portrait candidate artifact
```

Do not change without confirmation:

- renderer behavior;
- character save state;
- art assets;
- TTS/ASR behavior;
- packaging.

Expected deliverables for `P1-live`:

- real provider result is printed as sanitized terminal output or written only to an ignored local artifact;
- no API key or provider transcript is committed;
- state mutation checks remain explicit;
- failure modes are classified as provider/settings/parse/coverage/state-guard.

Expected deliverables for `P3-art-candidate`:

- candidate art and contact sheet are generated as artifacts only;
- default `portrait_manifest.json` is not changed until human visual QA approves;
- provenance records model/tool/date and rejection notes;
- no third-party IP or reference project assets are copied.

Confirmation needed before execution:

- Use of a real paid API key for live smoke.
- Whether to store any live smoke transcript as an ignored local artifact, or print only sanitized terminal output.
- Creating or committing any formal visual asset candidate.
- Updating default runtime portrait manifests.
