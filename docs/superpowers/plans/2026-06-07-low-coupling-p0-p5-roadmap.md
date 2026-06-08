# Low-Coupling P0-P5 Roadmap

Date: 2026-06-07

## Current Verified Baseline

- Branch: `codex/demo-worktree-cleanup`
- Latest committed checkpoint before this cue-probe-review package: `abbf46d feat: add llm expression cue probes`
- Use `git log --oneline --decorate -8` for the absolute current HEAD after any later docs-only sync commits.
- Original plan baseline: `c0fd88a test: add portrait asset qa guardrails`
- Dirty workspace expected item: none. `data/companion_save.json` remains ignored and must not be staged if it reappears as local runtime data.
- Latest focused Windows build/package tests run on 2026-06-08:

```powershell
python -m pytest tests\test_repository_hygiene.py tests\test_windows_build_validator.py tests\test_windows_packaging_scripts.py tests\test_packaging_entrypoints.py -q
```

Result: `14 passed`.

Latest focused AI-video workflow tests run on 2026-06-09:

```powershell
python -m pytest tests\test_portrait_video_frame_preflight.py tests\test_portrait_video_workflow_status.py tests\test_portrait_video_frame_normalization.py tests\test_portrait_video_source_batch.py tests\test_portrait_video_source_pack_processing.py tests\test_repository_hygiene.py -q
```

Result: `28 passed`.

Latest focused LLM/review tests run on 2026-06-09:

```powershell
python -m pytest tests\test_ai_expressor.py tests\test_companion_dialogue_policy.py tests\test_expression_clients.py tests\test_expression_diagnostics.py tests\test_expression_event_pipeline.py tests\test_visual_actions.py tests\test_llm_smoke.py tests\test_llm_smoke_review.py tests\test_repository_hygiene.py -q
```

Result: `175 passed`.

Latest focused character-pack/P4 tests run on 2026-06-09:

```powershell
python -m pytest tests\test_character_generation_workflow.py tests\test_character_registry.py tests\test_character_session.py tests\test_character_pack.py tests\test_character_pack_validator_tool.py tests\test_character_draft_validator_tool.py tests\test_character_pack_import_tool.py tests\test_character_pack_status_review_tool.py tests\test_app.py tests\test_repository_hygiene.py -q
```

Result: `146 passed`.

Latest focused release-readiness/report tests run on 2026-06-09:

```powershell
python -m pytest tests\test_release_readiness_report.py tests\test_portrait_video_workflow_status.py tests\test_repository_hygiene.py -q
```

Result: `16 passed`.

Full suite run on 2026-06-09:

```powershell
python -m pytest
```

Result: `693 passed`.

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
  - `.gitignore` now covers `.env`, `.env.*`, `*.key`, `generated/`, `artifacts/llm_smoke/`, `artifacts/portrait-candidate*.png`, and ignored portrait candidate directories.
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
- `P5-frozen-character-license-gate` package:
  - Extends the Windows build validator so the frozen bundled `original_oc` pack must include pack-level `LICENSE.md` along with portrait manifest, portraits, preview, item icons, and provenance.
  - Keeps the existing PyInstaller copy strategy unchanged because the build script already copies the complete source character directory.
  - Verified Windows app build, installer build, `tools/validate_windows_build.py`, frozen control-panel 5-second smoke, and frozen `--pet-mode` 5-second smoke.
  - This is a release validation gate only. It does not change runtime behavior, installer paths, dependencies, renderer behavior, or bundled third-party assets.
- `P0/P5-release-readiness-report` package:
  - Adds `tools/release_readiness_report.py`, a read-only aggregate report over source character-pack status and frozen Windows build validation.
  - The report writes JSON/Markdown under ignored `artifacts/release-readiness*.json` and `artifacts/release-readiness*.md`.
  - This makes release state easier to reproduce and explain without changing runtime behavior, build strategy, UI, provider calls, or assets.
- `P1/P5-release-readiness-llm-reports` package:
  - Extends `tools/release_readiness_report.py` with repeatable `--llm-report` inputs that reuse `tools/review_llm_smoke_report.py`.
  - Current ignored aggregate artifact `artifacts/release-readiness-with-llm.json` passed with source pack ready, frozen build ready, DeepSeek expression cue probe passed, and DeepSeek dialogue smoke passed.
  - This is offline report aggregation only. It does not call providers, change prompts, alter runtime state, touch UI, or change build strategy.
- `P1-speech-quality-gate` package:
  - Adds speech length and emptiness quality metrics to the LLM dialogue smoke report.
  - Keeps this as a smoke/QA gate only; it does not change prompt policy, character state, renderer behavior, or provider clients.
  - Dry-run artifacts remain under ignored `artifacts/llm_smoke/`.
- `P3-video-provider-fallbacks` package:
  - Adds Vidu and LivePortrait to the local AI-video handoff prompts and handoff README.
  - Documents the Gemini-unavailable fallback route in `docs/portrait_video_generation_sop.md`.
  - Keeps this as a source-pack/SOP change only; it does not call providers, generate assets, update runtime manifests, or add dependencies.
- `P3-frame-intake-failure-report` package:
  - Makes `tools/art/inspect_portrait_video_workflow.py` surface failed `candidate-motion-frame-report.json` files as `motion_candidate_status=failed`.
  - Adds next actions `regenerate_ai_video` and `inspect_motion_candidate` so bad AI-video outputs do not look like missing candidates.
  - Current ignored frame-intake artifact found 60 readable frames, all size-mismatched with the 1024x1536 reference, and motion extraction failed with `not enough stable frames after body drift filtering`.
  - This is workflow reporting only. It does not update runtime manifests, loosen art gates, change renderer behavior, or promote generated frames.
- `P3-batch-preflight-guard` package:
  - Makes `tools/art/batch_process_portrait_video_source_packs.py` reuse frame preflight before reporting or processing source packs.
  - Source packs with size warnings now report `ready_with_warnings`, increase `warning_count`, and are skipped by `--process-ready`.
  - This prevents bad AI-video frames from being auto-processed into failed motion candidates. It does not change extraction thresholds, runtime manifests, renderer behavior, or art approval gates.
- `P3-video-prompt-locks` package:
  - Strengthens generated Gemini/provider handoff prompts with same-canvas, no-crop, no-resize, no-reframe, fixed-silhouette, and only-eyelids/breathing/hair-tip motion constraints.
  - Regenerated the ignored `xingxi-vn-neutral-20260608` source pack prompts and handoff zip so the next external AI-video attempt uses the stricter prompt.
  - This is source-pack prompt/SOP work only. It does not call providers, change runtime manifests, change art gates, or accept the current bad video frames.
- `P3-handoff-frame-qa-readme` package:
  - Adds frame preflight and `ready_with_warnings` regeneration guidance directly to `AI_VIDEO_HANDOFF_README.md` inside provider-neutral handoff zips.
  - This keeps manual provider work aligned with the local QA tools before any extraction attempt. It does not change runtime manifests, renderer behavior, prompt policy, or art approval gates.
- `P3-body-drift-preflight` package:
  - Makes `tools/art/inspect_portrait_video_source_frames.py` flag same-size PNG frames with high body drift as `ready_with_warnings`.
  - This catches likely pose/body recomposition before `--process-ready` can process the frames. It does not loosen extraction thresholds, call providers, change runtime manifests, or approve current bad video frames.
- `P3-single-processor-preflight-guard` package:
  - Makes `tools/art/process_portrait_video_source_pack.py` run frame preflight before extraction and block any source pack that is not `ready`.
  - Blocked reports include `preflight_status`, `preflight_warnings`, and the preflight next action so direct `next_command` use cannot silently process warned frames.
  - This is a source-pack tooling guard only. It does not change runtime manifests, renderer behavior, extraction thresholds, provider prompts, or art approval gates.
- `P3-handoff-reference-size` package:
  - Adds `reference_size` to generated `source_pack.json` metadata and shows the exact required frame size in `AI_VIDEO_HANDOFF_README.md`.
  - The current ignored neutral source pack now tells operators to export frames at `1024x1536`, matching the reference portrait instead of the rejected `496x744` video output.
  - This is source-pack metadata/handoff guidance only. It does not call providers, change runtime manifests, process frames, or approve generated assets.
- `P3-video-frame-normalization` package:
  - Adds `tools/art/normalize_portrait_video_source_frames.py` for free/trial providers that export lower-resolution frames with the same portrait aspect ratio.
  - The tool clones a source pack, writes resized frames to a sibling ignored source pack, and leaves the original provider frames untouched.
  - Local simulation on the current `496x744` ignored frames produced a `1024x1536` normalized clone, but frame preflight still reported 60 body-drift warnings and the single-pack processor blocked extraction.
  - The normalized clone must still pass frame preflight before processing. This does not loosen body-drift checks, call providers, change runtime manifests, or approve generated assets.
- `P3-preflight-normalize-next-action` package:
  - Makes frame preflight distinguish same-aspect lower-resolution frames from non-normalizable size mismatch.
  - Adds `normalizable_size_mismatch_count` and `next_action=normalize_frames` to preflight/workflow reports when normalization is the next safe local step.
  - Keeps `ready_with_warnings` as the source status, so batch and single-pack processing still block extraction until the normalized clone passes a fresh preflight.
- `P3-workflow-attention-summary` package:
  - Adds compact `attention_reasons` to portrait AI-video workflow JSON/Markdown reports.
  - The report can now summarize `normalizable_size_mismatch`, `body_drift_warnings`, `failed_motion_extraction`, missing handoff, waiting frames, and insufficient frames without reading long warning lists.
  - This is read-only reporting only. It does not change frame preflight gates, batch processing, extraction thresholds, runtime manifests, renderer behavior, or asset approval.
- `P3-workflow-split-next-actions` package:
  - Adds split `source_next_action` and `motion_next_action` fields to the portrait AI-video workflow report while preserving the compatibility `next_action`.
  - This prevents a stale failed motion extraction from hiding the current source-frame cleanup step, or vice versa, in JSON/Markdown review.
  - This is report shaping only. It does not change preflight decisions, extraction behavior, runtime manifests, renderer behavior, or asset approval.
- `P3/P5-release-readiness-portrait-workflow` package:
  - Extends `tools/release_readiness_report.py` with repeatable `--portrait-workflow-report` inputs.
  - Release readiness can now include existing portrait AI-video workflow blockers such as `normalizable_size_mismatch`, `body_drift_warnings`, and `failed_motion_extraction`.
  - This is offline report aggregation only. It does not process frames, call providers, change runtime manifests, change renderer behavior, or approve generated assets.
- `P1-smoke-batch-review` package:
  - Allows `tools/review_llm_smoke_report.py` to accept either one smoke JSON file or an ignored smoke artifact directory.
  - Directory review skips existing `review` outputs and creates a compact passed/needs-attention/invalid summary.
  - Keeps this as an offline QA/reporting tool only; it does not call providers, persist prompts, or change runtime behavior.
  - Local ignored batch review artifact: `artifacts/llm_smoke/llm-smoke-batch-review-20260609.json`.
  - Current local artifact summary: 10 reviewed smoke JSON files, 0 passed, 10 need attention, 0 invalid. Most are old-format reports missing the newer `speech_quality` field, so they are not current proof of LLM quality.
- `P1-expression-cue-guidance` package:
  - Strengthens the performance prompt so the LLM must choose one visible emotion tag and cannot collapse explicit sad, tired, playful, focused, or surprised cues to `[calm]`.
  - Fixes the cue mapping so `[focused]` owns 专注/学习 and `[calm]` is only the quiet-companion fallback.
  - Initial current-tool DeepSeek live smoke failed with `visual_action_coverage:expressions=3/4,motions=5/3`.
  - Rerun artifact after prompt guidance: `artifacts/llm_smoke/deepseek-speech-quality-live-20260609-rerun.json`, `ok=true`, 10 turns, 4 expressions, 4 motions, 0 fallback, 0 speech quality violations, state guard clean.
  - Targeted sadness cue probe: `artifacts/llm_smoke/deepseek-sadness-cue-live-20260609.json`, `ok=true`, expression `sadness`, motions `SwitchDown` and `TouchHead`, state guard clean.
  - All live artifacts stay ignored under `artifacts/llm_smoke/`; no API key or raw provider transcript is committed.
- `P1-expression-cue-probe-suite` package:
  - Adds `tools/llm_expression_cue_probe.py` and a reusable report path in `src/guanghe_companion/llm_smoke.py`.
  - The probe sends five explicit player-like cue cases for `joy`, `sadness`, `sleepy`, `focused`, and `surprised`, then checks typed `visual_actions.expression` ids, fallback use, speech length gates, and state mutation.
  - First DeepSeek live run hit one transient `provider_error` fallback on the sadness case; rerun artifact `artifacts/llm_smoke/deepseek-expression-cue-probe-20260609-rerun.json` passed with 5/5 cases, no speech quality violations, and clean state guard.
  - This is a QA/probe tool only. It does not change runtime renderer behavior, state ownership, provider clients, assets, or manifests.
- `P1-cue-probe-review` package:
  - Extends `tools/review_llm_smoke_report.py` so the same offline review CLI can read expression cue probe JSON reports as well as dialogue smoke reports.
  - Review output now exposes report type, cue case count, cue failure count, cue-case miss messages, and cue-derived expression/motion coverage.
  - This is offline artifact review only. It does not call providers, change prompt policy, change expression parsing, or alter runtime state.
- `P4-character-pack-status-review` package:
  - Adds `tools/review_character_pack_status.py`, a read-only release/import status review for generated drafts and complete runtime packs.
  - The report summarizes validation status, import readiness, manual QA needs, provenance/license files, local fanwork distribution boundaries, and next actions.
  - Adds a pack-level `assets/companion/original_oc/LICENSE.md` so the bundled original Xingxi runtime pack can be reviewed as distribution-ready alongside `portrait_assets_provenance.md`.
  - Local character-pack status reports stay ignored under `artifacts/character-pack-status*.json` and `artifacts/character-pack-status*.md`.
  - This does not generate characters, copy packs, change active character state, update renderer manifests, or alter runtime behavior.

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
  - After user approval, `tools/art/prepare_portrait_candidate.py` produced an ignored alpha candidate pack under `artifacts/portrait-candidate-xingxi-vn-20260607/`.
  - Prepared candidate validation result: `ok=true`, one `neutral.open` RGBA portrait, transparent corners, and generated contact sheet/report.
  - `tools/art/portrait_candidate_visual_qa.py` produced an ignored multi-background QA preview/report for checker, light, and dark backgrounds.
  - Visual QA finding: the cutout is transparent and usable for review, but dark-background preview exposes light halo around white hair and coat edges.
  - Quantified halo finding: `light_edge_alpha_pixel_count=17703`, `light_edge_alpha_ratio=0.5087`, warning `light_edge_halo_risk`.
  - `tools/art/portrait_candidate_decision_brief.py` summarizes the ignored candidate into JSON/Markdown blockers, warnings, and next human decision text without approving or rejecting the art.
  - `tools/art/review_portrait_candidate.py` runs the candidate validation, contact sheet, visual QA, and decision brief steps together into one ignored review directory.
  - `tools/art/extract_portrait_motion_frames.py` supports the AI-video route by selecting blink and idle candidate frames from exported PNG frame sequences, or from `--video` when local `ffmpeg` is available.
  - `tools/art/create_portrait_video_source_pack.py` and `tools/art/create_portrait_video_source_packs_from_candidate.py` generate ignored source-pack folders under `artifacts/portrait-video-source/`.
  - Source packs now include `gemini_prompt.md`, `provider_prompts.md`, `source_pack.json`, `reference/`, `video/`, and `frames/`, so Pika, Hailuo, Kling, PixVerse, Runway, Vidu, LivePortrait, or Gemini can be used without changing downstream tooling.
  - `tools/art/bundle_portrait_video_source_packs.py` generates ignored handoff zip files under `artifacts/portrait-video-handoff/`, including `AI_VIDEO_HANDOFF_README.md`, the reference image, prompts, and metadata only.
  - `tools/art/inspect_portrait_video_source_frames.py` preflights exported PNG frames before extraction, rejecting unreadable frames and flagging size mismatches for manual review.
  - `tools/art/batch_process_portrait_video_source_packs.py` reports `waiting_for_frames`, `insufficient_frames`, `ready`, and processed states; it only processes packs with at least 3 exported PNG frames.
  - `tools/art/inspect_portrait_video_workflow.py` writes ignored JSON/Markdown workflow reports with frame preflight source status, handoff status, frame count, motion-candidate status, and next action.
  - Current workflow report: `artifacts/portrait-video-workflow-report.md`, `ok=false`, `source_status=ready_with_warnings`, `frame_count=60`, `handoff_status=present`, `motion_candidate_status=failed`, `next_action=regenerate_ai_video`.
  - Current frame preflight also reports the original `496x744` frames as `normalizable_size_mismatch_count=60` with `next_action=normalize_frames`; the normalized sibling still reports `body_drift_warning_count=60` and remains blocked.
  - Current decision brief state: `needs_iteration`, with blockers for unapproved candidate metadata, missing expression set, missing neutral blink frames, and warning `neutral.open: light_edge_halo_risk`.
  - Remaining limitation: this is still one neutral candidate only. It lacks expression variants, exported AI-video frames, blink frames, final provenance approval, edge cleanup, and manifest integration.

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
  - speech quality thresholds and violations;
  - parsed visual actions;
  - fallback reason;
  - state mutation check result.
- Surface this in the existing expression diagnostics path or a compact UI/debug panel.
- Add a live smoke path for OpenAI-compatible providers, especially DeepSeek.
- Add an offline review tool that turns existing smoke JSON into a compact issue summary without calling a provider.
- Support batch review of ignored local smoke artifact folders so multiple provider runs can be compared without new API calls.

Primary files:

- `src/guanghe_companion/expression_diagnostics.py`
- `src/guanghe_companion/expression_clients.py`
- `src/guanghe_companion/llm_smoke.py`
- `tools/llm_dialogue_smoke.py`
- `tools/llm_expression_cue_probe.py`
- `tools/review_llm_smoke_report.py`
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
- `tools/review_character_pack_status.py`
- `tests/test_character_generation_workflow.py`
- `tests/test_character_registry.py`
- `tests/test_character_session.py`
- `tests/test_character_pack_status_review_tool.py`

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

The next high-value packages are:

```text
P3-ai-video-generation: use the ignored handoff zip with Pika/Hailuo/Kling/PixVerse/Runway/Vidu/LivePortrait/Gemini, then place exported PNG frames into the matching frames folder
P3-frame-intake-QA: after frames exist, run frame preflight, batch processing, visual QA, and decision brief without changing the runtime manifest
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
- provenance remains local and ignored until human QA decides whether the candidate survives;
- no third-party IP or reference project assets are copied.
- ignored alpha candidate pack can be regenerated from the approved base artifact with `tools\art\prepare_portrait_candidate.py`;
- ignored all-in-one review directory can be regenerated with `tools\art\review_portrait_candidate.py`;
- ignored AI-video blink/motion frame candidate packs can be regenerated from exported PNG frame sequences with `tools\art\extract_portrait_motion_frames.py`;
- ignored AI-video source packs can be regenerated from a candidate manifest with `tools\art\create_portrait_video_source_packs_from_candidate.py`;
- ignored provider-neutral handoff zips can be regenerated with `tools\art\bundle_portrait_video_source_packs.py`;
- ignored JSON/Markdown next-action reports can be regenerated with `tools\art\inspect_portrait_video_workflow.py`;
- ignored visual QA preview/report can be regenerated with `tools\art\portrait_candidate_visual_qa.py`, including alpha edge metrics and light-edge halo warnings;
- ignored JSON/Markdown decision brief can be regenerated with `tools\art\portrait_candidate_decision_brief.py`;
- candidate directory remains ignored and is not bundled into runtime assets.
- ignored runtime candidate pack smoke remains a separate renderer-loadability check;
- strict promotion gate remains reserved for a complete approved portrait pack. It now reports visual QA warnings such as `light_edge_halo_risk` without auto-failing the pack, because final edge quality still needs human art approval.
- the prepared neutral-only candidate is not promotion-ready because it lacks expression variants, exported AI-video frames, blink frames, final provenance approval, edge cleanup, and manifest integration.

Confirmation needed before execution:

- Changing prompt policy, character personality, or expression parser behavior based on the live smoke result.
- Regenerating, editing, approving, or rejecting the VN portrait candidate beyond the already approved base cutout.
- Creating expression variants, blink frames, or final contact sheets from the candidate.
- Updating default runtime portrait manifests.
