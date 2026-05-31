# E-Moti

E-Moti is a Windows-first desktop AI companion runtime built with Python and PySide6.

It ships with the original companion 星汐, a small desktop companion that responds through local state, sprite motions, dialogue bubbles, inventory items, relationship progress, and short-lived contextual expression. The project is intentionally more than a sprite demo and less than a general agent operating system: it explores how a character-centric desktop companion can hold state, express emotion, and connect to optional AI services without letting those services own pet progression or local saves.

This project is not a productivity coach, course supervisor, mascot skin, or chatbot-only shell. Learning, resting, comforting, and playing are action states, not the product identity.

![星汐 idle motion](assets/companion/original_oc/preview/gifs/Default.gif)
![星汐 comfort motion](assets/companion/original_oc/preview/gifs/Comfort.gif)

## Ecosystem Position

E-Moti sits at the intersection of desktop companions, character tools, and AI agent interfaces.

- **Desktop-native AI surface**: E-Moti is a persistent companion surface instead of another browser tab or chat page.
- **Local-first pet core**: mood, focus, charge, trust, inventory, memory, relationship unlocks, and saves are owned by deterministic local logic.
- **Typed AI boundary**: model output is parsed and validated as companion events before it reaches the UI.
- **Multimodal extension bench**: LLM expression, screen observation, web search, TTS, and ASR are optional capabilities behind explicit settings.
- **Character asset workflow**: sprite atlas metadata, preview GIFs, item icons, and character pack data make it possible to iterate on AI-generated or artist-made companion assets.
- **Windows distribution path**: the repo includes PyInstaller and Inno Setup entry points for turning the companion into an installable desktop app.

The long-term direction is a hackable, open-source shell for AI-native desktop companions: local state and consent boundaries stay stable while new model providers, voice stacks, art pipelines, browser-use connectors, and computer/compute-use adapters can be added around them.

## Current Features

- Control panel mode with status, actions, shop, inventory, relationship, memory, dialogue, and settings views.
- Desktop pet mode with transparent always-on-top presentation and direct sprite interaction.
- System tray support for hiding, restoring, entering pet mode, and exiting.
- Local state machine for focus, charge, stability, mood, trust, coins, level, inventory, memories, and relationship unlocks.
- Sprite atlas driven motion layer using the bundled original character assets.
- Dialogue history, replay, revert, and local memory summaries.
- Optional LLM expression adapter with OpenAI Responses, OpenAI-compatible chat completions, DeepSeek, OpenRouter, and custom provider presets.
- Optional screen observation, web search, TTS, and ASR integrations behind explicit settings.
- Windows packaging scripts for a frozen app and Inno Setup installer.
- Regression and smoke tests covering state, events, UI, dialogue, voice, search, screen observation, packaging scripts, and repository hygiene.

## Architecture Boundaries

E-Moti keeps pet growth and AI expression separate.

- The local controller owns state, inventory, relationship, memory, goals, and saves.
- LLM output is parsed through typed events before it reaches the UI.
- Screen observation and web search only enter read-only expression context.
- ASR only becomes player text input.
- TTS only speaks already validated companion speech.
- Browser-use and computer-use style automation are roadmap integrations, not current default behavior.
- No API key is bundled in the repository.
- Runtime saves are local files and are ignored by git.

These boundaries are part of the project identity. They let E-Moti experiment with richer AI capabilities while keeping the companion predictable, inspectable, and safe to run locally.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `src/guanghe_companion/` | Application code, local state, UI, AI expression adapters, optional capability services. |
| `assets/companion/original_oc/` | Bundled original character data, sprite atlas, item icons, and preview GIFs. |
| `tests/` | Regression and smoke tests for the companion runtime and build scripts. |
| `tools/` | Windows build scripts and art preview validation helpers. |
| `packaging/` | Frozen-app launchers and Inno Setup installer definition. |
| `data/` | Local runtime saves. This directory is intentionally ignored by git. |

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

## Build

Build the frozen Windows app:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
```

The app executable is written to:

```text
dist\E-Moti\E-Moti.exe
```

Build the installer after the app has been built:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
```

The installer is written to:

```text
dist\installer\E-Moti_Setup_0.1.0.exe
```

If Inno Setup is installed somewhere else, pass `-ISCCPath` to `tools\build_windows_installer.ps1`.

## Optional AI Capabilities

The demo can run without network services. Optional capabilities must be configured by the user in the app UI:

- LLM expression: OpenAI Responses, OpenAI-compatible chat completion settings, or compatible third-party providers.
- Screen observation: OpenAI-compatible vision endpoint.
- Web search: DuckDuckGo search through `ddgs`.
- TTS: Windows SAPI or a local HTTP Qwen3TTS-compatible service.
- ASR: OpenAI-compatible transcription endpoint or a local Vosk model.

These capabilities are expression helpers. They do not own pet progression or save data.

## Roadmap

- **Character pipeline**: expand character-pack documentation, add more validation for AI-generated sprite atlases, and make asset replacement easier.
- **Voice loop**: improve ASR/TTS ergonomics, voice presets, latency feedback, and local/offline provider examples.
- **Context loop**: keep screen observation and search read-only while improving summaries, citations, and consent prompts.
- **Agent loop**: explore browser-use, computer-use, and compute-use adapters as explicit, user-approved companion skills.
- **Distribution**: harden Windows packaging, release notes, installer QA, and first-run setup docs.
- **Community**: document contribution areas for designers, AI workflow builders, and Python desktop developers.

## Contributing

E-Moti is early-stage and welcomes focused, well-scoped contributions. Good contribution areas include tests, documentation, character assets, optional provider adapters, packaging, and small UX improvements.

See `CONTRIBUTING.md` for the project boundaries and local development loop.

## License

MIT. See `LICENSE`.
