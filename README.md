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

Portrait candidate validation before manifest promotion:

```powershell
python tools\art\prepare_portrait_candidate.py artifacts\portrait-candidate-xingxi-vn-20260607.png --output artifacts\portrait-candidate-xingxi-vn-20260607 --report artifacts\portrait-candidate-xingxi-vn-20260607\candidate-preparation-report.json
python tools\art\review_portrait_candidate.py artifacts\portrait-candidate-xingxi-vn-20260607\portrait_candidate.json --output-dir artifacts\portrait-candidate-xingxi-vn-20260607\review --report artifacts\portrait-candidate-xingxi-vn-20260607\review\portrait-candidate-review.json
python tools\art\extract_portrait_motion_frames.py --reference-image artifacts\portrait-candidate-xingxi-vn-20260607\portraits\neutral_open.png --frames-dir artifacts\portrait-video-source\frames --output-dir artifacts\portrait-candidate-xingxi-vn-motion --report artifacts\portrait-candidate-xingxi-vn-motion\candidate-motion-frame-report.json --source-tool "Gemini video" --generation-prompt "Static camera; same character, outfit, pose, and proportions; subtle breathing; one natural blink; slight hair sway; no text."
python tools\art\portrait_candidate_visual_qa.py artifacts\portrait-candidate-xingxi-vn-20260607\portrait_candidate.json --preview artifacts\portrait-candidate-xingxi-vn-20260607\preview\portrait-visual-qa.png --report artifacts\portrait-candidate-xingxi-vn-20260607\portrait-visual-qa-report.json
python tools\art\portrait_candidate_decision_brief.py artifacts\portrait-candidate-xingxi-vn-20260607\portrait_candidate.json --report artifacts\portrait-candidate-xingxi-vn-20260607\portrait-decision-brief.json --markdown artifacts\portrait-candidate-xingxi-vn-20260607\portrait-decision-brief.md
python tools\art\validate_portrait_candidates.py path\to\portrait_candidate.json --runtime-manifest assets\companion\original_oc\portrait_manifest.json --contact-sheet artifacts\portrait-candidate-contact-sheet.png
```

`prepare_portrait_candidate.py`, `review_portrait_candidate.py`, `extract_portrait_motion_frames.py`, `portrait_candidate_visual_qa.py`, and `portrait_candidate_decision_brief.py` are for ignored local VN candidate packs only. They create an RGBA cutout, blink/motion frame candidates from AI video PNG frames, `portrait_candidate.json`, contact sheet, multi-background visual QA preview, alpha/edge metrics, and JSON/Markdown human decision briefs, but they do not update `portrait_manifest.json`.

`extract_portrait_motion_frames.py` accepts exported PNG frames with `--frames-dir`. It can also accept `--video` when `ffmpeg` is installed locally; otherwise export frames from the video tool first and keep the downloaded source under ignored `artifacts\portrait-video-source\`. Pass `--source-tool` and `--generation-prompt` so the candidate pack writes `portrait_video_provenance.md` for later human QA.

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
$env:DEEPSEEK_API_KEY="sk-..."
python tools\llm_dialogue_smoke.py --provider deepseek --timeout-seconds 45 --report artifacts\llm_smoke\deepseek-live-smoke.json
Remove-Item Env:\DEEPSEEK_API_KEY
```

The dry run prints sanitized provider settings without API calls. The live LLM smoke uses a temporary save directory and can write a UTF-8 JSON report with `--report`. It fails if the provider cannot be called, if fallback is used, if growth state mutates, or if expression/motion coverage is too weak.

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
```

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
