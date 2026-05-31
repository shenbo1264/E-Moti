# E-Moti

E-Moti is a Windows-first desktop companion pet demo built with Python and PySide6.

The current companion is the original character 星汐. She is a small desktop companion that responds through local state, sprite motions, dialogue bubbles, inventory items, relationship progress, and short-lived contextual expression. Learning, resting, comforting, and playing are action states, not the product identity.

This project is not a productivity coach, course supervisor, mascot skin, or chatbot-only shell.

## Features

- Control panel mode with status, actions, shop, inventory, relationship, memory, dialogue, and settings views.
- Desktop pet mode with transparent always-on-top presentation and direct sprite interaction.
- System tray support for hiding, restoring, entering pet mode, and exiting.
- Local state machine for focus, charge, stability, mood, trust, coins, level, inventory, memories, and relationship unlocks.
- Sprite atlas driven motion layer using the bundled original character assets.
- Optional LLM expression adapter that can turn validated local events into character speech.
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

- LLM expression: OpenAI-compatible chat completion settings.
- Screen observation: OpenAI-compatible vision endpoint.
- Web search: DuckDuckGo search through `ddgs`.
- TTS: Windows SAPI or a local HTTP Qwen3TTS-compatible service.
- ASR: OpenAI-compatible transcription endpoint or a local Vosk model.

These capabilities are expression helpers. They do not own pet progression or save data.

## Repository Notes

- `src/guanghe_companion/` contains the application code.
- `assets/companion/original_oc/` contains the bundled original character runtime assets.
- `tests/` contains the regression and smoke tests.
- `packaging/` and `tools/` contain Windows build entry points and scripts.
- `data/` contains local runtime saves and is intentionally ignored by git.

## License

MIT. See `LICENSE`.
