# E-Moti

E-Moti is a Windows-first desktop companion pet demo built with Python and PySide6.

The current companion is the original character 星汐. She is moving toward a Spirit/GalGame-like desktop companion presentation with large portrait expressions, dialogue staging, local pet state, inventory items, relationship progress, and short-lived contextual expression. Learning, resting, comforting, and playing are action states, not the product identity.

This project is not a productivity coach, course supervisor, mascot skin, or chatbot-only shell.

## Features

- Control panel mode with status, actions, shop, inventory, relationship, memory, dialogue, and settings views.
- Desktop pet mode with transparent always-on-top presentation and direct companion interaction.
- System tray support for hiding, restoring, entering pet mode, and exiting.
- Character library support for switching bundled or user-imported complete character packs.
- Local state machine for focus, charge, stability, mood, trust, coins, level, inventory, memories, and relationship unlocks.
- Spirit/GalGame portrait renderer using bundled original Xingxi expression assets.
- Sprite atlas renderer kept as the fallback, tray-friendly baseline, and regression-safe renderer.
- Live2D Web renderer path for character packs that provide a safe `.model3.json`; sprite remains the fallback.
- Optional LLM expression adapter that can turn validated local events into character speech, expression cues, motion cues, and read-only interaction intents.
- Optional screen observation, web search, TTS, and ASR integrations behind explicit settings.
- Windows packaging scripts for a frozen app and Inno Setup installer.

## Architecture Boundaries

E-Moti keeps pet growth and AI expression separate.

- The local controller owns state, inventory, relationship, memory, goals, and saves.
- LLM output is parsed through typed events before it reaches the UI.
- Screen observation and web search only enter read-only expression context.
- ASR only becomes player text input.
- TTS only speaks already validated companion speech.
- No API key is bundled in the repository.
- Runtime saves are local files and are ignored by git.

## Requirements

- Python 3.11
- Windows 10/11 recommended
- PowerShell for packaging scripts
- Inno Setup 6 only if you want to build the installer

Core Python dependencies are declared in `pyproject.toml`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install pytest pyinstaller
```

## Run

Control panel:

```powershell
python -m guanghe_companion.app
```

Desktop pet mode:

```powershell
python -m guanghe_companion.app --pet-mode
```

Use demo save data:

```powershell
python -m guanghe_companion.app --demo-save
```

Reset demo save data:

```powershell
python -m guanghe_companion.app --reset-demo-save
```

Script entry points are also available:

```powershell
python run_ui.py
python run_demo.py
```

## Test

```powershell
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
```

Focused UI smoke tests:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py
```

Character pack validation:

```powershell
python tools\validate_character_pack.py assets\companion\original_oc
python tools\review_character_pack_status.py assets\companion\original_oc --json artifacts\character-pack-status-original-oc.json --markdown artifacts\character-pack-status-original-oc.md
```

Generated character draft validation:

```powershell
python tools\create_character_draft.py --brief path\to\brief.json --output-root generated
python tools\validate_character_draft.py path\to\generated\<character_id>
```

Import a complete validated character pack into a user pack root:

```powershell
python tools\import_character_pack.py path\to\complete_pack --target-root "%LOCALAPPDATA%\E-Moti\character_packs"
```

Generated drafts are not import-ready until final art, icons, spritesheet, provenance, and manual QA are complete. Use `--force` only when intentionally replacing an existing local pack with the same `character_id`.
`review_character_pack_status.py` is a read-only release/import review helper for generated drafts and complete runtime packs. It reports validation status, import readiness, manual QA needs, provenance/license files, local fanwork distribution boundaries, and next actions without copying files or changing runtime manifests.

Portrait candidate validation before manifest promotion:

```powershell
python tools\art\prepare_portrait_candidate.py artifacts\portrait-candidate-xingxi-vn-20260607.png --output artifacts\portrait-candidate-xingxi-vn-20260607 --report artifacts\portrait-candidate-xingxi-vn-20260607\candidate-preparation-report.json
python tools\art\review_portrait_candidate.py artifacts\portrait-candidate-xingxi-vn-20260607\portrait_candidate.json --output-dir artifacts\portrait-candidate-xingxi-vn-20260607\review --report artifacts\portrait-candidate-xingxi-vn-20260607\review\portrait-candidate-review.json
python tools\art\clean_portrait_candidate_edges.py artifacts\portrait-candidate-xingxi-vn-20260607\portrait_candidate.json --output artifacts\portrait-candidate-xingxi-vn-20260607-edge-cleaned --report artifacts\portrait-candidate-xingxi-vn-20260607-edge-cleaned\edge-cleanup-report.json
python tools\art\create_portrait_video_source_packs_from_candidate.py artifacts\portrait-candidate-xingxi-vn-20260607\portrait_candidate.json --set-id-prefix xingxi-vn --set-id-suffix 20260608 --character-name "Xingxi" --source-label-prefix "VN expression candidate" --report artifacts\portrait-video-source-create-report.json
python tools\art\create_portrait_video_source_pack.py --source-image artifacts\portrait-candidate-xingxi-vn-20260607\portraits\neutral_open.png --set-id xingxi-vn-neutral-20260608 --character-name "Xingxi" --source-label "VN neutral candidate"
python tools\art\inspect_liveportrait_preflight.py artifacts\portrait-video-source\xingxi-vn-neutral-20260608 --liveportrait-root tmp\liveportrait_research\LivePortrait --driving tmp\liveportrait_research\drivers\blink_driver.mp4 --report artifacts\liveportrait-preflight-xingxi-vn-neutral.json --markdown artifacts\liveportrait-preflight-xingxi-vn-neutral.md
python tools\art\bundle_portrait_video_source_packs.py artifacts\portrait-video-source --output-dir artifacts\portrait-video-handoff --report artifacts\portrait-video-handoff-report.json
python tools\art\inspect_portrait_video_workflow.py artifacts\portrait-video-source --handoff-dir artifacts\portrait-video-handoff --candidate-root artifacts --report artifacts\portrait-video-workflow-report.json --markdown artifacts\portrait-video-workflow-report.md
python tools\art\inspect_portrait_video_source_frames.py artifacts\portrait-video-source --report artifacts\portrait-video-frame-preflight.json
python tools\art\normalize_portrait_video_source_frames.py artifacts\portrait-video-source\xingxi-vn-neutral-20260608 --output-pack-dir artifacts\portrait-video-source\xingxi-vn-neutral-20260608-normalized --report artifacts\portrait-video-frame-normalization.json
python tools\art\batch_process_portrait_video_source_packs.py artifacts\portrait-video-source --report artifacts\portrait-video-source-batch-report.json
python tools\art\process_portrait_video_source_pack.py artifacts\portrait-video-source\xingxi-vn-neutral-20260608 --output-dir artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion
python tools\art\extract_portrait_motion_frames.py --reference-image artifacts\portrait-candidate-xingxi-vn-20260607\portraits\neutral_open.png --frames-dir artifacts\portrait-video-source\frames --output-dir artifacts\portrait-candidate-xingxi-vn-motion --report artifacts\portrait-candidate-xingxi-vn-motion\candidate-motion-frame-report.json --source-tool "AI video" --generation-prompt "Static camera; same character, outfit, pose, and proportions; subtle breathing; one natural blink; slight hair sway; no text."
python tools\art\portrait_candidate_visual_qa.py artifacts\portrait-candidate-xingxi-vn-20260607\portrait_candidate.json --preview artifacts\portrait-candidate-xingxi-vn-20260607\preview\portrait-visual-qa.png --report artifacts\portrait-candidate-xingxi-vn-20260607\portrait-visual-qa-report.json
python tools\art\portrait_candidate_decision_brief.py artifacts\portrait-candidate-xingxi-vn-20260607\portrait_candidate.json --report artifacts\portrait-candidate-xingxi-vn-20260607\portrait-decision-brief.json --markdown artifacts\portrait-candidate-xingxi-vn-20260607\portrait-decision-brief.md
python tools\art\validate_portrait_candidates.py path\to\portrait_candidate.json --runtime-manifest assets\companion\original_oc\portrait_manifest.json --contact-sheet artifacts\portrait-candidate-contact-sheet.png
```

`prepare_portrait_candidate.py`, `review_portrait_candidate.py`, `clean_portrait_candidate_edges.py`, `create_portrait_video_source_packs_from_candidate.py`, `create_portrait_video_source_pack.py`, `inspect_liveportrait_preflight.py`, `bundle_portrait_video_source_packs.py`, `inspect_portrait_video_workflow.py`, `inspect_portrait_video_source_frames.py`, `normalize_portrait_video_source_frames.py`, `batch_process_portrait_video_source_packs.py`, `process_portrait_video_source_pack.py`, `extract_portrait_motion_frames.py`, `portrait_candidate_visual_qa.py`, and `portrait_candidate_decision_brief.py` are for ignored local VN candidate packs only. They create an RGBA cutout, one AI-video source folder per portrait set, LivePortrait local setup preflight reports, handoff zip bundles, next-action workflow reports, frame preflight reports, same-aspect frame normalization clones, cloned edge-cleanup candidates, blink/motion frame candidates from AI video PNG frames, `portrait_candidate.json`, contact sheet, multi-background visual QA preview, alpha/edge metrics, and JSON/Markdown human decision briefs, but they do not update `portrait_manifest.json`.

`clean_portrait_candidate_edges.py` clones a candidate directory and removes bright semi-transparent edge-halo pixels from the clone only, preserving the original candidate for comparison and provenance. `create_portrait_video_source_packs_from_candidate.py` reads `portrait_candidate.json` and creates one source folder for each expression open/static portrait. `create_portrait_video_source_pack.py` writes `artifacts\portrait-video-source\<set_id>\reference`, `gemini_prompt.md`, `provider_prompts.md`, `video`, `frames`, and `source_pack.json` with `reference_size` so Pika, Hailuo, Kling, PixVerse, Runway, Vidu, LivePortrait, or Gemini work can be handed off cleanly. `inspect_liveportrait_preflight.py` checks a local external LivePortrait checkout, required human-mode weight files, driving clip/template signature, FFmpeg, and source-pack reference image, then writes a suggested command without running the model. `bundle_portrait_video_source_packs.py` creates one ignored zip per source pack with only the reference image, prompts, metadata, and handoff README, including the exact required frame size. `inspect_portrait_video_workflow.py` reports each pack's frame preflight source status, handoff zip, frame count, motion candidate status, compatibility `next_action`, split `source_next_action` / `motion_next_action`, compact `attention_reasons`, and suggested local follow-up commands as JSON or Markdown; when a pack is waiting for AI-video frames, it now emits the matching LivePortrait preflight command. `inspect_portrait_video_source_frames.py` opens exported PNG frames before extraction, rejects unreadable frames, flags non-normalizable size mismatches or high body drift for review, and recommends `normalize_frames` for same-aspect lower-resolution frames. `normalize_portrait_video_source_frames.py` clones a source pack and resizes same-aspect provider frames to the reference size without overwriting originals; the normalized clone must still pass frame preflight before processing. `batch_process_portrait_video_source_packs.py` scans those folders and reports `ready`, `ready_with_warnings`, `insufficient_frames`, `waiting_for_frames`, or processed status; add `--process-ready` to process only source packs that passed frame preflight without warnings. `process_portrait_video_source_pack.py` also blocks extraction unless the source pack preflights as `ready`, then turns one source pack into a motion candidate using the saved prompt as provenance. `extract_portrait_motion_frames.py` is the lower-level extractor; it also accepts `--video` when `ffmpeg` is installed locally.

Runtime portrait manifests may include optional top-level `motion_frames` paths under `motion_frames/` plus `animation.idle.enabled=true` and `animation.idle.fps`. The Spirit surface only plays those idle frames for the fallback portrait expression, so neutral AI-video breathing frames do not overwrite other expressions.

Portrait character-pack smoke and strict promotion gate:

```powershell
python tools\portrait_pack_smoke.py path\to\complete_pack --report artifacts\portrait-pack-smoke-report.json --screenshot artifacts\portrait-pack-smoke-window.png
python tools\portrait_promotion_gate.py path\to\complete_pack --report artifacts\portrait-promotion-report.json
```

`portrait_pack_smoke.py` proves that a portrait pack can load through the runtime renderer. `portrait_promotion_gate.py` is stricter: it is for final manifest promotion and requires approved candidate metadata, provenance, transparent tall VN portraits, distinct expressions, and distinct neutral blink frames. `portrait_video_provenance.md` from AI video frame extraction counts as a provenance note only after human review keeps the candidate in the promotion package. Its JSON report can also include non-blocking visual QA warnings such as light-edge halo risk; those warnings do not replace human art approval.

LLM expression smoke with DeepSeek or another OpenAI-compatible provider:

```powershell
python tools\llm_dialogue_smoke.py --provider deepseek --dry-run
$env:DEEPSEEK_API_KEY="<your_deepseek_api_key>"
python tools\llm_dialogue_smoke.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\deepseek-live-smoke.json
python tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\deepseek-expression-cue-probe.json
python tools\review_llm_smoke_report.py artifacts\llm_smoke\deepseek-live-smoke.json --json artifacts\llm_smoke\deepseek-live-smoke-review.json --markdown artifacts\llm_smoke\deepseek-live-smoke-review.md
python tools\review_llm_smoke_report.py artifacts\llm_smoke --json artifacts\llm_smoke\llm-smoke-batch-review.json --markdown artifacts\llm_smoke\llm-smoke-batch-review.md
Remove-Item Env:\DEEPSEEK_API_KEY
```

The dry run prints sanitized provider settings without API calls. The live LLM smoke uses a temporary save directory and can write a UTF-8 JSON report with `--report`. It fails if the provider cannot be called, if fallback is used, if growth state mutates, if expression/motion coverage is too weak, or if speech is empty, too short, or too long for the configured smoke thresholds. `llm_expression_cue_probe.py` sends explicit player-like joy, sadness, sleepy, focused, and surprised cue cases and verifies that the typed expression action includes the expected visible emotion. `review_llm_smoke_report.py` converts an existing dialogue smoke JSON, expression cue probe JSON, or ignored smoke artifact directory into compact JSON/Markdown review output without calling any provider.

Live2D smoke tests require local-only verification dependencies that are not committed:

```text
tmp\live2d_research\CubismWebSamples\Samples\Resources\Haru\Haru.model3.json
tmp\live2d_research\live2dcubismcore.min.js
```

Run them only after those files are present:

```powershell
python tools\live2d_spike\smoke_live2d_web.py --timeout-seconds 45
python tools\live2d_spike\smoke_app_surface.py
python tools\live2d_spike\smoke_character_pack_window.py
```

## Build

Build the frozen Windows app:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
```

If `python` on PATH points to the wrong interpreter, pass a known Python 3.11+ executable:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1 -PythonPath "C:\Path\To\Python311\python.exe"
```

The app executable is written to:

```text
dist\E-Moti\E-Moti.exe
```

Build the installer after the app has been built:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
```

When the installer script needs to build the app first, the same `-PythonPath` argument is forwarded to `tools\build_windows_app.ps1`.

The installer is written to:

```text
dist\installer\E-Moti_Setup_0.1.0.exe
```

If Inno Setup is installed somewhere else, pass `-ISCCPath` to `tools\build_windows_installer.ps1`.

Validate the frozen app bundle and installer artifacts:

```powershell
python tools\validate_windows_build.py --report artifacts\windows-build-validation.json
python tools\release_readiness_report.py --json artifacts\release-readiness.json --markdown artifacts\release-readiness.md
python tools\release_readiness_report.py --llm-report artifacts\llm_smoke\deepseek-expression-cue-probe.json --llm-report artifacts\llm_smoke\deepseek-live-smoke.json --json artifacts\release-readiness-with-llm.json --markdown artifacts\release-readiness-with-llm.md
python tools\release_readiness_report.py --llm-report artifacts\llm_smoke --json artifacts\release-readiness-with-llm-directory.json --markdown artifacts\release-readiness-with-llm-directory.md
python tools\release_readiness_report.py --portrait-candidate-report artifacts\portrait-candidate-xingxi-vn-20260607\portrait-decision-brief.json --json artifacts\release-readiness-with-portrait-candidate.json --markdown artifacts\release-readiness-with-portrait-candidate.md
python tools\release_readiness_report.py --portrait-workflow-report artifacts\portrait-video-workflow-report.json --json artifacts\release-readiness-with-portrait-workflow.json --markdown artifacts\release-readiness-with-portrait-workflow.md
python tools\release_readiness_report.py --liveportrait-preflight-report artifacts\liveportrait-preflight-xingxi-vn-neutral.json --json artifacts\release-readiness-with-liveportrait-preflight.json --markdown artifacts\release-readiness-with-liveportrait-preflight.md
```

The build validator also checks that the frozen bundled `original_oc` character pack includes its manifest, portraits, preview, item icons, provenance note, and pack-level `LICENSE.md`.
`release_readiness_report.py` is a read-only aggregate report that combines the source character-pack status review with frozen Windows build validation. Pass one or more `--llm-report` paths to include existing dialogue smoke or expression cue probe JSON reports without calling a provider. `--llm-report` also accepts an ignored smoke artifact directory and summarizes the batch review, including per-file attention summaries; old-format or failing reports in that directory intentionally make release readiness need attention. Pass `--portrait-candidate-report` to include an existing portrait candidate decision brief so candidate blockers, warnings, and next human decisions are visible before manifest promotion. Pass `--portrait-workflow-report` to include an existing AI-video workflow JSON report so unresolved motion-frame blockers and suggested local follow-up commands stay visible in release notes. Pass `--liveportrait-preflight-report` to include an existing local LivePortrait setup preflight JSON, including missing weights, driving input status, and suggested manual follow-up, without cloning, installing, or running inference.

## Optional AI Capabilities

The demo can run without network services. Optional capabilities must be configured by the user in the app UI:

- LLM expression: OpenAI Responses, OpenAI-compatible cloud providers, or local OpenAI-compatible servers.
- Screen observation: OpenAI-compatible vision endpoint.
- Web search: DuckDuckGo search through `ddgs`.
- TTS: Windows SAPI or a local HTTP Qwen3TTS-compatible service.
- ASR: OpenAI-compatible transcription endpoint or a local Vosk model.

These capabilities are expression helpers. They do not own pet progression or save data.

LLM expression provider presets:

| Provider | Default Base URL | API Key | Notes |
| --- | --- | --- | --- |
| `openai` | `https://api.openai.com/v1/responses` | Required | Uses the Responses API path. |
| `deepseek` | `https://api.deepseek.com` | Required | Uses OpenAI-compatible chat completions. |
| `openrouter` | `https://openrouter.ai/api/v1` | Required | Uses OpenAI-compatible chat completions. |
| `ollama` | `http://127.0.0.1:11434/v1` | Optional | Start Ollama locally, pull a model, then use the model list button or type the model ID. |
| `lmstudio` | `http://127.0.0.1:1234/v1` | Optional | Start the LM Studio local server, load a model, then use the model list button or type the model ID. |
| `custom` | `https://api.openai.com/v1` | Optional | For other OpenAI-compatible services. Fill an API key when that service requires one. |

## Live2D Status

The repository contains the Live2D Web renderer integration and smoke harness. It does not contain a rigged Xingxi Live2D model.

Current verified boundary:

```text
LLM -> typed speech/visual_actions events -> renderer adapter -> Live2D surface
```

Formal Xingxi Live2D production still requires a layered PSD, Cubism Editor rigging, expression/motion export, and a character pack that passes:

```powershell
python tools\validate_character_pack.py character_packs\xingxi_live2d
```

See `docs/live2d_asset_pipeline.md` for the PSD layer checklist, Cubism export checklist, and renderer mapping contract.

## Repository Notes

- `src/guanghe_companion/` contains the application code.
- `assets/companion/original_oc/` contains the bundled original character runtime assets, including portrait expressions and sprite fallback assets.
- `tests/` contains the regression and smoke tests.
- `packaging/` and `tools/` contain Windows build entry points and scripts.
- `data/` contains local runtime saves and is intentionally ignored by git.
- `tmp/live2d_research/`, `artifacts/simulation/`, `node_modules/`, API keys, and third-party Live2D sample assets must stay out of commits.

## Open Source Boundaries

- E-Moti's code is MIT licensed.
- The bundled Xingxi sprite/reference assets in this repository are original project assets.
- Live2D Cubism Core, Live2D official sample models, and third-party character models are not bundled.
- Do not commit copied models, proprietary runtime files, API keys, generated dialogue history, or runtime saves.
- Fanwork or third-party character packs should only be distributed when the author has the right to publish the assets and character setting.

## License

MIT. See `LICENSE`.
