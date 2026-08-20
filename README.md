# E-Moti

[English](README.md) | [简体中文](README.zh-CN.md)

![E-Moti AI Architecture Overview](docs/assets/emoti-ai-architecture-overview.png)

E-Moti is a Windows-first desktop AI companion pet built with Python and PySide6. It combines a lightweight virtual-pet loop, switchable character packs, emotional memory, proactive companion moments, and optional AI expression services. The game state is controlled by local rules; AI is used to make the companion speak, react, recall shared experiences, and perform with more personality.

The current art-production route is a **hatch-pet-style pixel-pet sequence workflow**: lock one canonical character base, generate and review one animation row at a time, inspect contact sheets, repair failed rows, and only then promote a validated pack into the runtime.

The bundled course-delivery role set includes **three visible switchable character packs**: `xingxi_pixel_pet`, `ikaros_pixel_pet`, and `nairong_pixel_pet`. Xingxi is the default companion. Ikaros and Nairong demonstrate the same character-pack, renderer, memory namespace, shop theme, and voice-profile contracts across different role styles.

> Learning, resting, comforting, and playing are action states. E-Moti is not a productivity coach, course supervisor, mascot skin, or chatbot-only shell.

## Design Principle

- Local game rules own progression, inventory, memories, relationships, goals, coins, and saves.
- AI improves the companion's speech, expression, motion cues, and read-only context use.
- Optional perception, search, voice, and ASR features enhance presentation but never take over the growth state machine.

## Features

- PySide6 control panel with status, actions, shop, inventory, relationship, memory, dialogue, and settings views.
- Transparent always-on-top desktop pet mode.
- Tray lifecycle: hide, restore, enter pet mode, and exit.
- Character library with three visible bundled packs: `xingxi_pixel_pet`, `ikaros_pixel_pet`, and `nairong_pixel_pet`.
- Local virtual-pet progression for mood, trust, coins, level, inventory, relationship unlocks, and long-term memory.
- Emotional Memory V2 with categorized shared experiences, source tracing, pin, correction, forgetting, retrieval, and per-character isolation.
- Stardust Memory Album: a player-facing PySide6 view for first moments, shared routines, gifts, player facts, and relationship chapters.
- Focus Companion moments with quiet hours, cooldowns, daily limits, three player responses, and non-blocking timers.
- Plugin Runtime and Plugin Center with manifest validation, permissions, dependency checks, static audit, reversible registration, failure isolation, and JSON settings.
- Three bundled plugins: capability contracts, local expression fallback, and the end-to-end Stargazing Corner example.
- Sprite renderer as the stable desktop-pet baseline.
- Pixel-pet sequence workflow with spritesheets, motion manifests, contact sheets, provenance notes, and QA reports.
- Optional LLM expression adapter for validated speech, visual actions, motion cues, and read-only interaction intents.
- Optional screen observation, web search, TTS, and ASR integrations behind explicit settings.
- Windows build and installer scripts.

## Architecture

E-Moti is organized as a local game core plus an AI performance layer and pluggable character packs.

| Layer | Modules | Responsibility |
| --- | --- | --- |
| UI and Shell | `app.py`, `capability_panels.py`, `desktop_shell.py`, `tray_controller.py` | Control panel, desktop pet window, tray lifecycle, capability settings |
| Game Core | `controller.py`, `engine.py`, `actions.py`, `models.py`, `storage.py` | State machine, interaction effects, inventory, coins, level, saves |
| Story and Memory | `emotional_memory_service.py`, `memory_integration_bridge.py`, `memory_album_controller.py`, `companion_story_runtime.py` | Emotional memories, retrieval, relationship chapters, album actions, traceable shared experiences |
| Proactive Companion | `focus_companion.py`, `focus_companion_runtime.py`, `proactive_companion.py` | Low-frequency companion moments, quiet hours, cooldowns, player responses, proactive topics |
| Character System | `character_pack.py`, `character_registry.py`, `character_session.py`, `character_resources.py` | Load, validate, switch, and isolate character packs |
| AI Expression Pipeline | `expression_event_pipeline.py`, `ai_expressor.py`, `expression_parser.py`, `visual_actions.py`, `interaction_intents.py` | Parse LLM output into typed events, speech, visual actions, and read-only intents |
| Read-only Context | `expression_context.py`, `ai_context_builder.py`, `screen_observation.py`, `web_search.py`, `topic_scout.py`, `proactive_companion.py` | Screen summaries, search cards, proactive topics, and recent context |
| Voice | `voice_tts.py`, `voice_asr.py`, `voice_service_control.py`, `character_voice_profile.py` | Character voice profiles, TTS playback, ASR transcription, service checks |
| Plugin Platform | `plugin_host.py`, `plugin_runtime.py`, `plugin_subsystem.py`, `plugin_center_qt.py`, `plugin_provider_adapters.py` | Plugin lifecycle, capability providers, audit, permissions, settings, isolation, and reversible contributions |
| Renderers | `presentation_renderer.py`, `snapshot_renderer.py`, `spirit_stage.py`, `live2d_web.py` | Sprite baseline, portrait/spirit research path, Live2D Web adapter path |
| Tooling and QA | `tools/`, `tests/`, `packaging/` | Character-pack validation, pixel-art QA, LLM smoke tests, Windows packaging |

Important boundaries:

- LLM output cannot mutate growth state, inventory, relationship, memory, goals, coins, or saves.
- Screen observation and web search only provide read-only expression context.
- ASR only becomes player text through `DialogueRequest`.
- TTS only consumes validated companion speech.
- Plugins contribute through host contracts and reversible registrations; a failing plugin does not prevent the base game from starting.
- External AI services can be disabled while the local pet loop, memory album, and local expression fallback remain playable.
- Sprite rendering is the current production baseline; portrait, AI-video, LivePortrait, and Live2D remain research or extension paths.

## Character Packs

Runtime character packs live under `assets/companion/`.

```text
assets/companion/<character_id>/
  character.json
  dialogue_style.json
  motion_manifest.json
  spritesheet.png
  preview/contact-sheet.png
  preview/profile.png
  provenance.md
  qa_report.json
  shop_items.json
  LICENSE.md
```

Bundled packs:

- `xingxi_pixel_pet`: default original companion.
- `ikaros_pixel_pet`: humanoid character-pack workflow representative.
- `nairong_pixel_pet`: pet-style and goofy character-pack workflow representative.
- `original_oc`: older compatibility assets retained for renderer coverage.

Fanwork or third-party-inspired packs should keep source notes, generation records, QA evidence, and license boundaries. Confirm rights before public redistribution.

## Setup

Requirements:

- Python 3.11+
- Windows 10/11
- PowerShell
- Inno Setup 6, only when building the installer

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install pytest pyinstaller
```

Run the control panel:

```powershell
python -m guanghe_companion.app
```

Run desktop pet mode:

```powershell
python -m guanghe_companion.app --pet-mode
```

Use demo save data:

```powershell
python -m guanghe_companion.app --demo-save
```

## Test

```powershell
python -m pytest
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest tests\test_repository_hygiene.py -q
```

The final local integration baseline passed `1185` tests, including `327` focused memory/plugin tests and Windows GUI/build smoke verification.

Validate character packs:

```powershell
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_character_pack.py assets\companion\ikaros_pixel_pet
python tools\validate_character_pack.py assets\companion\nairong_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet
```

Build Windows artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\windows-build-validation.json
```

Operational notes:

- Demo quickstart: `docs\demo_operator_quickstart.md`
- Final release gate: `docs\final_release_gate_2026-07.md`
- LLM operations: `docs\llm_expression_operations.md`
- Character-pack distribution: `docs\character_pack_distribution_policy.md`
- Plugin architecture: `docs\PLUGIN_ARCHITECTURE_CN.md`
- Plugin authoring: `docs\PLUGIN_AUTHORING_GUIDE_CN.md`
- Windows plugin integration: `docs\WINDOWS_INTEGRATION_QUICKSTART_CN.md`

## Optional AI Capabilities

E-Moti runs without network services. Optional capabilities can be configured in the UI:

- LLM expression: OpenAI Responses, DeepSeek, OpenRouter, Ollama, LM Studio, or custom OpenAI-compatible services.
- Screen observation: OpenAI-compatible vision endpoint.
- Web search: DuckDuckGo search through `ddgs`.
- TTS: Windows SAPI, Edge TTS, or a local HTTP TTS service.
- ASR: OpenAI-compatible transcription endpoint or a local Vosk model.

The open-source repository does not include API keys, private runtime configuration, dialogue history, third-party model weights, or local save files.

## Repository Notes

- `src/guanghe_companion/` contains the application code.
- `assets/companion/` contains runtime character packs.
- `plugins/` contains bundled capability contracts, the offline expression fallback, and the Stargazing Corner example.
- `public_config_template/` contains key-free public capability and plugin defaults.
- `tests/` contains regression, smoke, packaging, and hygiene tests.
- `tools/` contains validation, QA, release-readiness, art-workflow, and packaging helpers.
- `packaging/` contains Windows packaging entry points.
- `data/` is for local runtime saves and is ignored by git.
- Generated drafts, local model research, API keys, dialogue history, and private runtime artifacts must stay out of commits.

## License

MIT. See `LICENSE`.
