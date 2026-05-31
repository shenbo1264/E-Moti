# Contributing to E-Moti

E-Moti is an early-stage desktop companion project. Contributions should keep the companion local-first, inspectable, and safe to run on a personal machine.

## Good Contribution Areas

- Setup, README, troubleshooting, and packaging documentation.
- Tests around state transitions, typed events, dialogue history, voice, search, screen observation, and Windows packaging scripts.
- Character-pack assets, sprite atlas previews, item icons, and validation tools.
- Optional AI provider adapters for expression, ASR, TTS, screen observation, and search.
- UI polish that makes the control panel and desktop pet mode easier to use.
- Windows packaging and installer improvements.

## Project Boundaries

- Keep pet progression local. AI services can express or summarize, but they should not own saves, inventory, relationship state, or core progression.
- Parse and validate model output before it reaches the UI.
- Keep screen observation and web search read-only unless a future feature explicitly asks for user-approved action.
- Do not bundle API keys, tokens, private URLs, local machine paths, or runtime saves.
- Keep `data/companion_save.json` and other runtime save files out of commits.
- Keep optional capabilities behind explicit settings and clear UI state.

## Development Loop

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install pytest pyinstaller
python -m pytest
```

For focused UI smoke tests:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py
```

For asset JSON validation:

```powershell
python -m json.tool assets\companion\original_oc\shop_items.json
```

## Pull Request Notes

- Keep PRs small and explain the user-visible behavior or project boundary being changed.
- Add or update tests when changing state, events, settings, parsing, capability adapters, or packaging scripts.
- If a change introduces a new optional external service, document the provider, required settings, failure mode, and privacy boundary.
- If a change touches UI copy, keep the distinction between companion identity and action states clear.
