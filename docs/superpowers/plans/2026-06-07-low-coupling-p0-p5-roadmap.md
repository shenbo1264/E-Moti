# Low-Coupling P0-P5 Roadmap

Date: 2026-06-07

## Current Verified Baseline

- Branch: `codex/demo-worktree-cleanup`
- Latest verified non-doc checkpoint: `34328c0 test: add windows build artifact validator`
- Docs-only sync commits may be newer than this checkpoint; use `git log --oneline --decorate -8` for the absolute current HEAD.
- Original plan baseline: `c0fd88a test: add portrait asset qa guardrails`
- Dirty workspace expected item: none. `data/companion_save.json` remains ignored and must not be staged if it reappears as local runtime data.
- Latest focused Windows build/package tests run on 2026-06-08:

```powershell
python -m pytest tests\test_repository_hygiene.py tests\test_windows_build_validator.py tests\test_windows_packaging_scripts.py tests\test_packaging_entrypoints.py -q
```

Result: `13 passed`.

Full suite run on 2026-06-08:

```powershell
python -m pytest
```

Result: `604 passed`.

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
- `b9f73cb feat: show character pack distribution metadata`
  - Adds read-only character pack distribution metadata to the character library details view.
  - `CharacterPackSummary` now reports provenance and license files without changing import validation or save state.
  - Keeps `provenance.md`, `portrait_assets_provenance.md`, `LICENSE`, and `LICENSE.md` visible for open-source / character-pack review.
- `265aafa feat: require character pack import review`
  - Adds a local confirmation step before copying an importable character pack into the user pack root.
  - The confirmation text shows character id, name/title, source, provenance, and license status.
  - Canceling the review leaves the source pack untouched and copies nothing.
  - Invalid packs still use the existing validation failure path and do not show the confirmation dialog.
- `cbe4a71 test: guard local artifact ignores`
  - Adds repository hygiene coverage for local secrets, generated character drafts, LLM smoke artifacts, and portrait candidate artifacts.
  - `.gitignore` now covers `.env`, `.env.*`, `*.key`, `generated/`, `artifacts/llm_smoke/`, and `artifacts/portrait-candidate*.png`.
  - `git check-ignore` was verified for representative local secret, draft, LLM smoke, and portrait candidate paths.
- `cbcd7d3 test: tighten portrait candidate gates`
  - Tightens `tools/art/validate_portrait_candidates.py` for Spirit/VN portrait candidates.
  - Candidate images must be RGBA, include visible opaque pixels, include transparent alpha pixels, and be taller than wide.
  - The ignored VN candidate artifact is now rejected by the gate because it is RGB and not runtime-ready.
  - This does not change default runtime manifests, committed art assets, state, TTS/ASR, or renderer behavior.
- `6b56c6d test: gate draft portraits with asset validator`
  - Makes `tools/validate_character_draft.py` reuse the portrait candidate asset gate before a draft can become `import_ready`.
  - A draft marked `approved` and `runtime_manifest_safe` now still fails if its portrait PNGs violate the RGBA, transparent-alpha, visible-pixel, or tall portrait requirements.
  - This keeps P4 character-pack personalization aligned with the P2 portrait gate without changing runtime character switching, saves, manifests, or renderer behavior.
- `c056e1b test: ignore local character packs`
  - Adds `character_packs/` to `.gitignore` and repository hygiene coverage.
  - Prevents local user packs, private fanwork packs, and generated character-pack experiments from being swept into open-source commits.
  - This preserves the character-switching/user-pack route without changing runtime loading, import confirmation, manifests, or assets.
- `3a5496e test: guard runtime artifact ignores`
  - Expands repository hygiene coverage for runtime saves, local dialogue history, simulation artifacts, and Live2D research scratch space.
  - Required ignore patterns now include `data/companion_save.json`, `data/companion_demo_save.json`, `data/dialogue_history.json`, `artifacts/simulation/`, and `tmp/live2d_research/`.
  - `data/companion_save.json` is still a tracked working-tree file in this checkout; removing it from the git index is a separate confirmation boundary.
  - This does not change runtime save behavior, app logic, packaging, or release artifacts.
- `03a4fb5 chore: stop tracking runtime save`
  - Removes `data/companion_save.json` from the git index while preserving the local file.
  - Keeps runtime save data ignored and out of release commits.
- `d1bc197 feat: tune llm companion performance prompts`
  - Adds compact performance guidance so LLM output reads more like a visual-novel desktop companion and less like a task bot.
  - DeepSeek live smoke was written only to ignored `artifacts/llm_smoke/`.
  - State mutation guard stayed clean.
- `c2d9e73 test: add portrait pack smoke check`
  - Adds `tools/portrait_pack_smoke.py` to verify that a complete portrait character pack loads through the existing runtime renderer.
  - Reports backend, spirit surface visibility, sprite fallback state, blink sequence, and optional screenshot path.
  - This is a runtime-loadability check, not art approval.
- `bfbfea1 fix: load cjk fonts for desktop smoke`
  - Explicitly loads Windows CJK font files for PySide6 offscreen smoke so Chinese UI text renders in screenshots.
  - Does not change renderer behavior, assets, LLM, or state.
- `d5e65ef test: add portrait promotion gate`
  - Adds `tools/portrait_promotion_gate.py` as a stricter final-art gate before official manifest promotion.
  - Requires approved candidate metadata, provenance, transparent tall VN portraits, distinct expression open frames, and distinct neutral blink frames.
  - The current ignored runtime candidate pack fails this gate, so it remains smoke-only and is not promotion-ready.
- `399de6b fix: harden windows packaging python and assets`
  - Adds `-PythonPath` support and Python 3.11+ probing to the Windows app build script.
  - Makes the installer script forward `-PythonPath` when it builds the app.
  - Copies the complete validated `assets/companion/original_oc` pack into the frozen app, including portrait manifest, portrait PNGs, preview, provenance, and item icons.
  - Verified Windows app build, installer build, frozen control-panel smoke, and frozen `--pet-mode` smoke.
- `34328c0 test: add windows build artifact validator`
  - Adds `tools/validate_windows_build.py` to verify the frozen app executable, installer executable, and bundled frozen character pack.
  - Validates that the frozen `original_oc` pack contains `portrait_manifest.json`, `portraits/`, `preview/`, `item_icons/`, and `portrait_assets_provenance.md`.
  - Adds ignored `artifacts/windows-build-validation*.json` QA reports.

Latest confirmation-gated packages completed after user approval:

- `P1-live` DeepSeek smoke, artifact only:
  - User confirmed real DeepSeek/OpenAI-compatible live smoke and allowed writing ignored artifact output.
  - Dry-run artifact: `artifacts/llm_smoke/deepseek-dry-run-20260607.json`.
  - Live artifact: `artifacts/llm_smoke/deepseek-live-20260607.json`.
  - Both artifacts are ignored by git.
  - Result: `ok=true`, `reason=""`, provider `deepseek`, model `deepseek-v4-flash`.
  - Coverage: 10 turns, 7 expression ids, 7 motion ids, no fallback reason.
  - State guard: `ok=true`, `changed_fields=[]`.
  - No API key or raw provider transcript was committed.
- `P3-art-candidate` base VN portrait candidate, artifact only:
  - User confirmed formal Spirit/VN candidate generation with no manifest change.
  - Candidate artifact: `artifacts/portrait-candidate-xingxi-vn-20260607.png`.
  - Artifact is ignored by git.
  - Image check: `RGB`, `1024x1536`.
  - Visual self-audit: high-body/full-body visual-novel direction, not the previous square chibi smoke baseline.
  - Limitation: not transparent, not an expression set, not runtime-ready, and not referenced by `portrait_manifest.json`.

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
- Keep local provider credentials, live smoke outputs, generated drafts, and portrait candidate artifacts ignored unless intentionally curated for release.
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
python tools\portrait_promotion_gate.py path\to\complete_pack --report artifacts\portrait-promotion-report.json
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
python tools\portrait_promotion_gate.py path\to\approved_pack --report artifacts\portrait-promotion-report.json
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
- Keep character-pack provenance, license, and source status visible in the library before users switch or review imported packs.
- Require a local import confirmation before copying valid user packs, so provenance and license status are reviewed before a pack enters the user library.
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
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1 -PythonPath "C:\Path\To\Python311\python.exe"
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\windows-build-validation.json
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

The next high-value packages still cross explicit confirmation boundaries:

```text
P1-quality-tuning: tune prompt/personality/expression quality after reviewing live smoke output
P3-visual-QA: approve, reject, or iterate the generated VN portrait candidate
```

Do not change without confirmation:

- renderer behavior;
- character save state;
- art assets;
- TTS/ASR behavior;
- packaging.

Completed deliverables for `P1-live`:

- real provider result is printed as sanitized terminal output or written only to an ignored local artifact;
- no API key or provider transcript is committed;
- state mutation checks remain explicit;
- failure modes are classified as provider/settings/parse/coverage/state-guard.

Completed deliverables for `P3-art-candidate`:

- candidate art is generated as an artifact only;
- default `portrait_manifest.json` is not changed until human visual QA approves;
- provenance is currently limited to this plan note and ignored artifact path until human QA decides whether the candidate survives;
- no third-party IP or reference project assets are copied.
- ignored runtime candidate pack smoke now passes through `tools\portrait_pack_smoke.py`;
- strict promotion gate now rejects the same ignored runtime candidate because it lacks `portrait_candidate.json`, lacks provenance, and still uses duplicate placeholder expression images.

Confirmation needed before execution:

- Changing prompt policy, character personality, or expression parser behavior based on the live smoke result.
- Regenerating, editing, approving, or rejecting the VN portrait candidate.
- Creating expression variants, blink frames, transparent cutouts, or contact sheets from the candidate.
- Updating default runtime portrait manifests.
