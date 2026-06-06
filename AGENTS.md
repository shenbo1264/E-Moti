# E-Moti Agent Operating Guide

This repository is the Windows-first desktop AI companion demo for the original character Xingxi. Treat this file as the standing instruction set for future coding agents working in this workspace.

## Current Product Route

The main experience route is now a spirit / GalGame-like companion presentation, not a small chibi pet as the primary visual style.

Priority direction:

1. Keep the existing small sprite desktop pet as a fallback, tray-friendly mode, and regression-safe baseline.
2. Build a new portrait/spirit presentation path with large half-body or full-body character art, expression variants, bottom-aligned scaling, crossfade transitions, and a dialogue stage.
3. Make LLM expression central to the perceived character performance: LLM output may choose speech, expression cues, motion cues, and read-only interaction intents through typed events.
4. Do not let LLM, screen observation, search, ASR, or TTS own growth state, inventory, memory, relationship, goals, or saves.
5. Live2D remains a later premium rendering path. Do not block the spirit / GalGame route on formal Live2D rigging.

Reference direction from Shinsekai is allowed only at the product and architecture level: large portrait staging, multiple portrait slots, crossfade between portrait images, background/dialogue layering, and character configuration fields such as sprites, scale, emotion tags, and personality setting. Do not copy Shinsekai source code, assets, prompts, character settings, or UI text.

## Near-Term Roadmap

### P0: Preserve The Verified Baseline

- Do not break the current PySide6 control panel, desktop pet mode, tray behavior, character switching, LLM smoke path, or packaging scripts.
- Keep `data/companion_save.json` uncommitted.
- Keep private ignored local note files untouched.
- Before changing runtime behavior, run relevant focused tests first and then full `python -m pytest`.

### P1: Portrait/Spirit Character Pack Contract

Add a renderer backend such as `portrait` or `spirit` without removing `sprite` or `live2d_web`.

Expected pack shape:

```text
assets/companion/<character_id>/
  character.json
  portrait_manifest.json
  portraits/
    neutral.png
    smile.png
    thinking.png
    surprised.png
    sad.png
    sleepy.png
```

The manifest should define safe relative image paths, expression ids, optional default scale, anchor/alignment, and fallback expression. Validation must reject missing files, unsafe paths, unsupported image modes, and oversized assets that would hurt UI performance.

### P2: Spirit Stage Surface

Create a PySide6 presentation surface for large portrait staging:

- transparent or quiet background suitable for a desktop companion;
- bottom-aligned portrait scaling;
- crossfade when expression or pose changes;
- dialogue/name layer styled for repeated interaction, not a marketing hero;
- fallback to sprite when a portrait pack is incomplete.

Keep this as a focused renderer layer. Do not mix it with state-machine rewrites, ASR, TTS, packaging, or Live2D work.

### P3: LLM-Driven Performance Mapping

Map typed `visual_actions.expression` and `visual_actions.motion` to portrait ids.

Allowed:

- choose `smile`, `thinking`, `surprised`, `sad`, `sleepy`, `neutral`;
- select a presentational pose or dialogue tone;
- enrich the read-only expression context.

Forbidden:

- mutate growth state;
- write memory or relationship state directly;
- change inventory, coins, goals, or saves;
- bypass `DialogueRequest`, typed events, snapshot contracts, or existing renderer adapters.

### P4: Formal Art Pipeline

Develop original Xingxi portrait assets using generated or commissioned art. Required checks:

- transparent PNG output;
- consistent face, outfit, palette, and proportions across expression variants;
- no copied third-party/IP character assets;
- no unlicensed Shinsekai, VPet, Bandori, Vocaloid, Miku, Codex pet, or fanwork source assets;
- preview sheet for human QA.

If automated generation is used, preserve prompts and provenance in a dedicated asset note. Do not commit API keys, temporary model outputs, or rejected experiments unless they are intended public assets.

### P5: QA And Packaging

Every package that changes UI or assets must run:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
```

If packaging or release behavior changes, also run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
```

## Execution Rules

### Evidence First

Do not trust prompt summaries, previous claims, or memory as current truth. Start by reading the live repo state:

```powershell
git status --short --untracked-files=all
git log --oneline --decorate -12
git branch --show-current
python -m pytest
```

Scale the verification to the task when a full test run is too expensive during early exploration, but do not claim completion without real commands.

### Do Not Build From Vibes

If the requirement is unclear, unstable, or market-facing, research before designing. Prefer current public evidence such as:

- Reddit and similar forums for user expectations and pain points;
- GitHub repos/issues/discussions for technical precedents;
- Steam/itch.io/community posts for companion, virtual pet, VN, and AI character UX;
- official docs for libraries and model providers.

Summarize what users actually ask for, what they reject, and what technical approaches appear mature. Cite sources when external research affects decisions.

### Do Not Reinvent Mature Infrastructure

Use proven libraries or established local patterns when they fit:

- PySide6 for desktop UI;
- existing renderer adapter boundaries for presentation;
- existing typed event/snapshot contracts for AI expression;
- Pillow or robust image libraries for asset validation;
- existing packaging scripts for Windows release.

Do not hand-roll engines for mature domains unless there is a narrow reason and a testable benefit. Do not add dependencies casually; if a dependency is needed, explain why it is better than local implementation and update tests/packaging.

### Use Subagents When Work Splits Cleanly

Use subagents or parallel workers for independent lanes such as:

- forum/user research;
- reference project read-only audit;
- renderer architecture review;
- asset pipeline QA;
- test coverage review;
- packaging risk review.

Do not assign overlapping file edits to multiple agents. The main agent must verify subagent conclusions against the repository and must not paste unreviewed subagent output into code or docs.

### Token And Effort Policy

Do not prematurely compress reasoning to save tokens when the task is architectural, ambiguous, or high-risk. The default is to spend enough analysis to avoid wrong work, especially around product route, AI behavior, asset licensing, packaging, and privacy.

Be concise in final user-facing summaries, but do not skip investigation, tests, or source reading internally.

### Goal Mode

When the route is clear and the user has asked to proceed, use the environment's goal/task tracking capability if available. Keep the goal concrete, continue until genuinely complete or blocked, and update status only when the objective is actually achieved or truly blocked.

If the platform requires explicit user authorization for goal creation, treat this guide as preference context but follow the platform rule.

### TDD And Verification

For production code changes:

1. Write or update a failing test first.
2. Run the focused test and confirm the expected failure.
3. Implement the smallest change that passes.
4. Run focused tests.
5. Run full `python -m pytest` before completion.

For docs-only changes, still run relevant lightweight checks such as `git diff --check` and any JSON validation touched by the change.

### Git Hygiene

- Never stage or commit `data/companion_save.json`.
- Never touch private ignored local note files.
- Do not revert user changes unless explicitly instructed.
- Keep commits focused by subsystem.
- Do not push, open PRs, change remotes, or merge branches unless the user explicitly asks.

### Privacy And Safety Boundaries

- No mouse/keyboard/clipboard/window control unless the user explicitly confirms that capability for the current package.
- No background listening, wake word, startup persistence, elevated install, or system-level automation without explicit confirmation.
- ASR only produces player text and must go through `DialogueRequest`.
- TTS only consumes validated companion speech.
- Screen observation and web search remain read-only expression context.

### Licensing And Asset Boundaries

- Do not copy Shinsekai, VPet, Bandori, Miku/Vocaloid, Codex pet, or other third-party/IP code/assets/prompts/character settings.
- GPL projects may inform architecture and tradeoffs only; do not copy source into this MIT repository.
- Fanwork character packs require explicit rights before distribution.
- Keep temporary research output under ignored paths unless it is intentionally curated for release.

## Definition Of Done

A package is done only when:

- the intended behavior or document is present in the repo;
- tests/checks appropriate to the risk have been run and reported;
- `git status --short --untracked-files=all` is understood;
- runtime save files and temporary research artifacts are excluded;
- the final summary states what changed, what was verified, and any remaining limitation.
