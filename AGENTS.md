# E-Moti Agent Operating Guide

This repository is the Windows-first desktop AI companion demo for the original character Xingxi. Treat this file as the standing instruction set for future coding agents working in this workspace.

## Priority Correction — 2026-10-30

The active work is the existing Python/PySide6 desktop: ordinary-chat memory, grounded shared experiences/profile, bounded relationship expression and natural proactive companionship. Preserve completed mobile code, commits and local work; pause new mobile/pairing/push/remote/observation scope. The older mobile-first ordering below is superseded. Read `docs/handoff/20261029/core-integration-20261030.md` for the current backend contract and actual evidence. Claude owns desktop UI/experience; Codex owns core services and model comparisons. Never report model behavior as verified without actual model outputs.

## Personal Agent And Mobile Handoff — 2026-10-29

Read `docs/handoff/20261029/README.md` and its requirements before new modernization work. The user assigns Claude to product/frontend implementation and Codex to backend/host implementation; use separate worktrees and the documented single-writer file ownership.

The current product scope is the existing Windows-first desktop plus Android/HyperOS phones, iPhone/iOS, and Huawei phones running native HarmonyOS. The earlier macOS request was a spoken mistake corrected by the user; do not schedule a Mac desktop client. A Mac/Xcode used to build iOS is only a build requirement. Keep Relay, Game Companion, and Body firmware independent.

E-Moti remains an independently usable personal companion with stable persona and shared memories. Optional work and observation capabilities must not become prerequisites for companionship. Desktop core memory and companionship come first; mobile integration and long-running supervision remain later goals. The asset-production notes below remain constraints/reference for asset work, not a requirement to regenerate artwork before this route.

The actual default in `character_pack.py` is currently `xingxi_pixel_pet`; preserve it and existing user selections. Older text naming `original_oc` as the default was stale. This documentation correction does not authorize replacing assets or changing any character's distribution rights.

## Current Product Route

The near-term experience route is now a hatch-pet-style pixel-pet sequence workflow. The older spirit / GalGame-like portrait route remains a renderer and research path, but it is not the active art-production route.

Priority direction:

1. Keep the existing sprite desktop pet as the tray-friendly baseline and regression-safe renderer.
2. Build small pixel-adjacent character sequence packs first: one canonical base, one grounded animation row at a time, contact-sheet QA, then row repair.
3. Preserve the current `xingxi_pixel_pet` default and existing packs. Any future default replacement requires its own asset QA and integration change. Treat Ikaros and Nairong as local UGC workflow representatives only unless rights are cleared.
4. Make LLM expression central to the perceived character performance: LLM output may choose speech, expression cues, motion cues, and read-only interaction intents through typed events.
5. Do not let LLM, screen observation, search, ASR, or TTS own growth state, inventory, memory, relationship, goals, or saves.
6. Keep portrait/spirit, AI-video, LivePortrait, and Live2D as research or later renderer paths. Do not let them block the pixel-pet sequence route.

Reference direction from Shinsekai is allowed only at the product and architecture level: character configuration, renderer boundaries, expression tags, and dialogue staging ideas. The active art route should follow compact pixel-pet production, not copied Shinsekai code, assets, prompts, character settings, or UI text.

## Near-Term Roadmap

### P0: Preserve The Verified Baseline

- Do not break the current PySide6 control panel, desktop pet mode, tray behavior, character switching, LLM smoke path, or packaging scripts.
- Keep `data/companion_save.json` uncommitted.
- Keep private ignored local note files untouched.
- Before changing runtime behavior, run relevant focused tests first and then full `python -m pytest`.

### P1: Pixel-Pet Character Pack Contract

Define a candidate pixel-pet character pack contract without removing `sprite`, `portrait`, or `live2d_web`.

Expected pack shape:

```text
character_packs_drafts/<character_id>/
  character.json
  dialogue_style.json
  motion_manifest.json
  spritesheet.png
  preview/contact-sheet.png
  provenance.md
  qa_report.json
```

Validation should reuse existing atlas and character-pack gates where possible. Candidate packs must reject unsafe paths, invalid JSON, missing provenance, non-RGBA spritesheets, wrong frame geometry, and row/frame manifest mismatches.

### P2: Xingxi Canonical Base

Lock one original Xingxi pixel-pet base before generating rows:

- use the hatch-pet workflow idea;
- keep generated candidates under ignored `artifacts/pixel-pet-sequence-drafts/`;
- record prompts, provenance, rejected variants, and QA notes;
- do not update `assets/companion/original_oc` until a full pack passes validation and human QA.

Do not regenerate all characters at once. Xingxi is the only track that can become a bundled open-source asset after QA.

### P3: One Animation Row At A Time

Generate one grounded row first, preferably idle breathing plus blink. Do not attempt a full spritesheet until one row survives contact-sheet QA.

Expected loop:

```text
canonical base -> row prompt -> row candidate -> contact sheet -> QA -> repair failed row only
```

### P4: LLM-Driven Pixel Emote Mapping

Map typed `visual_actions.expression` and `visual_actions.motion` to pixel-pet expressions or motion families.

Allowed:

- choose presentational ids such as `neutral`, `happy`, `blink`, `goofy`, `confused`, `sleepy`, or `focused`;
- select a presentational pose, motion family, or dialogue tone;
- enrich the read-only expression context.

Forbidden:

- mutate growth state;
- write memory or relationship state directly;
- change inventory, coins, goals, or saves;
- bypass `DialogueRequest`, typed events, snapshot contracts, or existing renderer adapters.

### P5: User-Pack Local Import And Release Gate

Build the demo loop around official Xingxi plus local UGC packs:

- Preserve the current Xingxi default. Future bundled candidates do not replace it unless a separate package updates the default route and passes UI, full test, and packaging gates.
- Ikaros and Nairong remain local UGC workflow representatives unless rights are cleared.
- Character library UI must keep provenance, license, and distribution boundaries visible.
- Every character keeps independent art assets, character data, memory/save namespace, and QA notes.

Every package that changes UI or assets must run the relevant UI smoke tests and then full pytest. If runtime manifests, default assets, or installer behavior change, run the Windows build and installer validators too.

Common UI/asset acceptance:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
```

If packaging or release behavior changes, also run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\windows-build-validation.json
```

If `python` on PATH is not the intended Python 3.11+ interpreter, pass `-PythonPath` to the build scripts instead of editing the environment inside the repo.

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
