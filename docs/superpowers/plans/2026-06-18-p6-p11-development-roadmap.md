# P6-P11 Development Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the project from P6 through P11 as a release-ready Windows desktop AI companion demo with a clear open-source posture, a working LLM expression loop, a QA-gated character-pack workflow, and controlled architecture decoupling.

**Architecture:** Keep local growth state and AI expression separate. The controller and domain modules own state, inventory, relationship, memory, goals, and saves; LLM, screen observation, search, ASR, and TTS remain typed-event or read-only presentation inputs. Preserve `original_oc` as the default pack unless a separate default-promotion decision package explicitly changes it.

**Tech Stack:** Python 3.11, PySide6, Pillow, pytest, existing Windows packaging scripts, existing pixel-pet validation and release-readiness tools.

---

## Current Evidence Baseline

This plan starts from the repository state verified on 2026-06-18:

- Branch: `codex/demo-worktree-cleanup`
- HEAD: `6227aeb feat: promote clean edge xingxi pixel pet candidate`
- Full tests: `python -m pytest` passed with `832 passed`
- Runtime default character: `original_oc`
- Optional bundled pixel-pet candidate: `assets/companion/xingxi_pixel_pet`
- `xingxi_pixel_pet` gates: character pack validation ready, pixel pack validation ready, visual QA ready, emote mapping ready, promotion gate ready
- LLM gate evidence: DeepSeek expression cue probe report exists under ignored `artifacts/llm_smoke/`
- Working tree risk: `AGENTS.md` may be modified by user context and must not be swept into unrelated commits

Before implementing any package, refresh this baseline with:

```powershell
git status --short --untracked-files=all
git log --oneline --decorate -12
git branch --show-current
python -m pytest
```

Expected current baseline before new work:

```text
tests pass
data/companion_save.json is not staged
no API keys are tracked
AGENTS.md is either intentionally included in a docs package or left unstaged
```

## Non-Negotiable Boundaries

- Do not commit `data/companion_save.json`.
- Do not commit provider API keys, local absolute paths, private notes, or ignored smoke artifacts.
- Do not copy Shinsekai, VPet, Bandori, Vocaloid, Codex pet, Ikaros, Nairong, or other third-party code/assets/prompts/settings into this MIT repository.
- Do not distribute Ikaros or Nairong assets unless rights are cleared.
- Do not let LLM mutate growth state, inventory, relationship, memory, goals, coins, or saves.
- Do not let ASR bypass `DialogueRequest`.
- Do not let TTS speak unvalidated text.
- Do not let screen observation or web search become state writers.
- Do not promote `xingxi_pixel_pet` to default without the P8 hard decision gate.
- Do not start mouse, keyboard, clipboard, window-control, wake-word, startup, or elevated-install work in this roadmap.

## Package Overview

| Package | Purpose | Normal Commit Count | Hard Stop |
| --- | --- | ---: | --- |
| P6 | Open-source release hardening and public docs | 1-2 | if tracked private/local material is found |
| P7 | LLM expression usability and diagnostics | 2-3 | if live provider fails for account/quota/network reasons |
| P8 | Default-character decision package | 0-2 | before changing default from `original_oc` |
| P9 | Local UGC character-pack workflow | 2-3 | before distributing fanwork/IP assets |
| P10 | Architecture decoupling without behavior drift | 2-4 | if UI behavior changes beyond extraction |
| P11 | Pixel-pet production runbook and final release gate | 1-3 | before any new generated asset enters `assets/companion/` |

## Files And Responsibilities

### Existing Files Likely To Change

- `README.md`  
  Public entry point. Keep product positioning, setup, test, LLM, character-pack, and release commands current.

- `.gitignore`  
  Local secrets, saves, generated assets, and smoke artifacts. Add patterns only when a real local artifact class appears.

- `tests/test_repository_hygiene.py`  
  Public-release guard for forbidden local paths, private note names, required ignore patterns, and current route wording.

- `src/guanghe_companion/expression_clients.py`  
  OpenAI-compatible provider client boundary. Do not print secrets.

- `src/guanghe_companion/expression_settings.py`  
  Provider/settings normalization and redaction.

- `src/guanghe_companion/llm_smoke.py`  
  Smoke scenarios, report payloads, state mutation checks, quality checks.

- `tools/llm_dialogue_smoke.py`  
  CLI smoke entry point for provider-backed dialogue.

- `tools/llm_expression_cue_probe.py`  
  CLI cue probe for speech/expression/motion/intent coverage.

- `src/guanghe_companion/character_pack.py`  
  Default character constant and runtime character pack loading.

- `src/guanghe_companion/character_registry.py`  
  Built-in and local user-pack validation/listing.

- `src/guanghe_companion/app.py`  
  Current large PySide6 integration layer. P10 should extract small pure helpers first, not rewrite the window.

- `tools/release_readiness_report.py`  
  Current large readiness aggregator. P10 should extract check providers behind tests.

- `docs/pixel_pet_sequence_sop.md`  
  Current pixel-pet workflow SOP.

- `docs/current_development_route_2026-06-17.md`  
  Current route evidence log. Append only concise factual updates when useful.

### New Files Proposed By This Plan

- `docs/open_source_release_checklist.md`  
  Public-release checklist for secrets, local paths, asset boundaries, test gates, and packaging gates.

- `docs/character_pack_distribution_policy.md`  
  Distribution policy for official packs, shareable packs, local UGC, and private fanwork.

- `docs/llm_expression_operations.md`  
  Operator guide for configuring, testing, and debugging LLM expression providers.

- `docs/character_pack_authoring_runbook.md`  
  Practical local-pack creation/import/QA runbook.

- `docs/final_release_gate_2026-06.md`  
  Final P11 gate record with commands and expected release state.

- `src/guanghe_companion/expression_provider_diagnostics.py`  
  Pure diagnostics types/functions for provider settings and redacted health reports.

- `src/guanghe_companion/character_library_view_model.py`  
  Pure formatting and list-row helpers extracted from `app.py`.

- `tools/llm_provider_diagnostics.py`  
  CLI wrapper around provider diagnostics.

- `tools/scaffold_character_pack.py`  
  Local-only starter pack scaffolder using existing character-pack rules.

- `tools/pixel_pet_sequence_status.py`  
  Read-only status summarizer for pixel-pet draft runs and candidate packs.

- `tests/test_expression_provider_diagnostics.py`
- `tests/test_character_library_view_model.py`
- `tests/test_character_pack_scaffold_tool.py`
- `tests/test_pixel_pet_sequence_status_tool.py`

---

## P6: Open-Source Release Hardening

**Purpose:** Make the repository safe and understandable for public release without changing runtime behavior.

**Out of scope:** Default-character change, new AI features, new art generation, installer behavior changes.

### Task P6.1: Baseline And Secret Hygiene

**Files:**
- Modify: `tests/test_repository_hygiene.py`
- Modify if needed: `.gitignore`
- Create: `docs/open_source_release_checklist.md`

- [ ] **Step 1: Run evidence commands**

```powershell
git status --short --untracked-files=all
git log --oneline --decorate -12
git branch --show-current
python -m pytest
git grep -n -E "sk-[A-Za-z0-9_-]{16,}|api[_-]?key" -- . ":!artifacts" ":!dist"
```

Expected:

```text
pytest passes
the secret-pattern grep has no unexpected matches outside tests and public examples
only intentional docs changes are staged later
```

- [ ] **Step 2: Add a public-doc route assertion**

Add this test to `tests/test_repository_hygiene.py`:

```python
def test_readme_names_pixel_pet_as_current_art_route() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8-sig")

    assert "hatch-pet-style pixel-pet sequence workflow" in readme
    assert "`xingxi_pixel_pet` as an optional bundled sprite candidate" in readme
    assert "`original_oc` remains the default companion pack" in readme
```

- [ ] **Step 3: Run the new hygiene test and confirm the real result**

```powershell
python -m pytest tests\test_repository_hygiene.py -q
```

Expected if README is already aligned:

```text
3 passed
```

If it fails, update `README.md` with exact wording that preserves these facts:

```text
The current near-term route is a hatch-pet-style pixel-pet sequence workflow.
The repo includes `xingxi_pixel_pet` as an optional bundled sprite candidate.
`original_oc` remains the default companion pack.
```

- [ ] **Step 4: Create the public release checklist**

Create `docs/open_source_release_checklist.md` with these sections:

```markdown
# Open Source Release Checklist

## Required Before Public Push

- `git status --short --untracked-files=all` reviewed.
- `python -m pytest` passes.
- `git grep -n "sk-" -- . ":!artifacts" ":!dist"` contains only test placeholders or public documentation examples.
- `data/companion_save.json`, `data/companion_demo_save.json`, and `data/dialogue_history.json` are not tracked.
- `assets/companion/original_oc` remains the default pack unless a default-promotion package says otherwise.
- `assets/companion/xingxi_pixel_pet` is described as an optional bundled candidate.
- Ikaros and Nairong are not distributed as bundled assets.
- Third-party reference projects are not copied into this repository.

## Public Asset Boundary

- `original_oc`: default bundled original character pack.
- `xingxi_pixel_pet`: optional bundled official candidate after QA.
- Ikaros: local UGC/fanwork workflow representative only.
- Nairong: local UGC/fanwork workflow representative only.

## Final Commands

```powershell
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --fail-on-warnings
```
```

- [ ] **Step 5: Verify docs-only changes**

```powershell
git diff --check
python -m pytest tests\test_repository_hygiene.py -q
python -m pytest
```

- [ ] **Step 6: Commit P6.1**

```powershell
git add README.md .gitignore tests\test_repository_hygiene.py docs\open_source_release_checklist.md
git commit -m "docs: add open source release checklist"
```

Only include `.gitignore` or `README.md` if they actually changed.

### Task P6.2: Distribution Policy Documentation

**Files:**
- Create: `docs/character_pack_distribution_policy.md`
- Modify: `README.md`
- Test: `tests/test_repository_hygiene.py`

- [ ] **Step 1: Create policy doc**

Create `docs/character_pack_distribution_policy.md`:

```markdown
# Character Pack Distribution Policy

## Pack Classes

### Default Official Pack

`assets/companion/original_oc` is the runtime default. It is the stable fallback for demos, tests, and packaging.

### Optional Official Candidate

`assets/companion/xingxi_pixel_pet` is a QA-gated optional bundled candidate. It can be selected from the character library, but it does not replace the default pack unless a separate default-promotion package changes `DEFAULT_CHARACTER_ID` and passes release gates.

### Shareable After Review

A pack may use `distribution_boundary: "shareable_after_review"` only when provenance, license, manual QA, renderer assets, and validation reports are present.

### Local UGC Only

`local_ugc_only` packs may be imported locally but are not assumed to be safe for redistribution.

### Private Local Fanwork

`private_local_fanwork` packs are for private workflow testing. They must not be committed into `assets/companion/`.

## Current Fanwork Representatives

- Ikaros: local UGC/fanwork workflow representative only.
- Nairong: local UGC/fanwork workflow representative only.

## Release Rule

No third-party character pack enters bundled assets without explicit rights review and an updated release checklist.
```

- [ ] **Step 2: Link it from README**

Add one short paragraph near the character-pack validation section:

```markdown
Character-pack distribution rules are documented in `docs\character_pack_distribution_policy.md`. Keep third-party and fanwork packs local unless rights are cleared.
```

- [ ] **Step 3: Verify**

```powershell
git diff --check
python -m pytest tests\test_repository_hygiene.py -q
python -m pytest
```

- [ ] **Step 4: Commit P6.2**

```powershell
git add README.md docs\character_pack_distribution_policy.md tests\test_repository_hygiene.py
git commit -m "docs: document character pack distribution policy"
```

---

## P7: LLM Expression Usability And Diagnostics

**Purpose:** Make the LLM path operationally usable: configuration is testable, failures are explainable, secrets stay redacted, and live smoke can prove speech/expression/motion/intent behavior without mutating state.

**Out of scope:** Long-term memory writes by LLM, autonomous task execution, wake-word/background listening, mouse/keyboard/clipboard/window control.

### Task P7.1: Provider Diagnostics Module

**Files:**
- Create: `src/guanghe_companion/expression_provider_diagnostics.py`
- Create: `tests/test_expression_provider_diagnostics.py`
- Create: `tools/llm_provider_diagnostics.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_expression_provider_diagnostics.py`:

```python
from __future__ import annotations

from guanghe_companion.expression_provider_diagnostics import (
    diagnose_expression_provider_settings,
)
from guanghe_companion.expression_settings import normalize_expression_settings


def test_diagnostics_reports_disabled_provider_without_secret() -> None:
    settings = normalize_expression_settings({"enabled": False, "api_key": "sk-secret"})

    report = diagnose_expression_provider_settings(settings)

    assert report.ok is False
    assert report.status == "disabled"
    assert "expression provider is disabled" in report.reasons
    assert "sk-secret" not in report.to_public_dict().__repr__()


def test_diagnostics_accepts_deepseek_openai_compatible_settings() -> None:
    settings = normalize_expression_settings(
        {
            "enabled": True,
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-secret",
            "timeout_seconds": 45,
        }
    )

    report = diagnose_expression_provider_settings(settings)

    assert report.ok is True
    assert report.status == "ready"
    assert report.provider == "deepseek"
    assert report.model == "deepseek-v4-flash"
    assert "sk-secret" not in str(report.to_public_dict())


def test_diagnostics_rejects_enabled_provider_without_key() -> None:
    settings = normalize_expression_settings(
        {
            "enabled": True,
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key": "",
        }
    )

    report = diagnose_expression_provider_settings(settings)

    assert report.ok is False
    assert report.status == "missing_api_key"
    assert "api key is missing" in report.reasons
```

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests\test_expression_provider_diagnostics.py -q
```

Expected:

```text
fails because guanghe_companion.expression_provider_diagnostics does not exist
```

- [ ] **Step 3: Implement diagnostics**

Create `src/guanghe_companion/expression_provider_diagnostics.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .expression_settings import ExpressionSettings


@dataclass(frozen=True, slots=True)
class ExpressionProviderDiagnosticReport:
    ok: bool
    status: str
    provider: str
    model: str
    base_url: str
    timeout_seconds: int
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "reasons": list(self.reasons),
        }


def diagnose_expression_provider_settings(
    settings: ExpressionSettings,
) -> ExpressionProviderDiagnosticReport:
    reasons: list[str] = []
    if not settings.enabled:
        reasons.append("expression provider is disabled")
        return _report(settings, ok=False, status="disabled", reasons=reasons)
    if not settings.api_key.strip():
        reasons.append("api key is missing")
        return _report(settings, ok=False, status="missing_api_key", reasons=reasons)
    if settings.timeout_seconds <= 0:
        reasons.append("timeout_seconds must be positive")
        return _report(settings, ok=False, status="invalid_timeout", reasons=reasons)
    return _report(settings, ok=True, status="ready", reasons=reasons)


def _report(
    settings: ExpressionSettings,
    *,
    ok: bool,
    status: str,
    reasons: list[str],
) -> ExpressionProviderDiagnosticReport:
    return ExpressionProviderDiagnosticReport(
        ok=ok,
        status=status,
        provider=settings.provider,
        model=settings.model,
        base_url=settings.base_url,
        timeout_seconds=settings.timeout_seconds,
        reasons=tuple(reasons),
    )
```

- [ ] **Step 4: Add CLI wrapper**

Create `tools/llm_provider_diagnostics.py`:

```python
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from guanghe_companion.expression_provider_diagnostics import (
    diagnose_expression_provider_settings,
)
from guanghe_companion.expression_settings import normalize_expression_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check LLM expression provider settings without printing secrets.")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    settings = normalize_expression_settings(
        {
            "enabled": True,
            "provider": args.provider,
            "model": args.model,
            "base_url": args.base_url,
            "api_key": os.environ.get(args.api_key_env, ""),
            "timeout_seconds": args.timeout_seconds,
        }
    )
    report = diagnose_expression_provider_settings(settings).to_public_dict()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Verify**

```powershell
python -m pytest tests\test_expression_provider_diagnostics.py -q
python tools\llm_provider_diagnostics.py --report artifacts\llm_smoke\provider-diagnostics.json
```

Expected without `DEEPSEEK_API_KEY`:

```text
pytest passes
diagnostics exits 1 with status missing_api_key and does not print an API key
```

- [ ] **Step 6: Commit P7.1**

```powershell
git add src\guanghe_companion\expression_provider_diagnostics.py tests\test_expression_provider_diagnostics.py tools\llm_provider_diagnostics.py
git commit -m "feat: add llm provider diagnostics"
```

### Task P7.2: Live LLM Smoke And Operator Guide

**Files:**
- Create: `docs/llm_expression_operations.md`
- Modify: `README.md`
- Test: `tests/test_llm_smoke.py`, `tests/test_expression_event_pipeline.py`, `tests/test_visual_actions.py`

- [ ] **Step 1: Create operator guide**

Create `docs/llm_expression_operations.md`:

```markdown
# LLM Expression Operations

## Purpose

The LLM expression provider improves Xingxi's speech, expression cues, motion cues, and read-only interaction intent. It does not own growth state, inventory, relationship, memory, goals, coins, or saves.

## Configure DeepSeek

```powershell
$env:DEEPSEEK_API_KEY="your-local-key"
python tools\llm_provider_diagnostics.py --provider deepseek --model deepseek-v4-flash --base-url https://api.deepseek.com
```

## Dry Run

```powershell
python tools\llm_dialogue_smoke.py --provider deepseek --dry-run
```

## Live Cue Probe

```powershell
python tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\deepseek-expression-cue-probe-latest.json
```

## Pass Criteria

- `ok=true`
- `fallback_count=0`
- `speech_quality.violations=[]`
- `state_mutation_check.ok=true`
- expression cues cover joy, sadness, sleepy, focused, and surprised

## Failure Handling

- `missing_api_key`: configure the local environment variable only.
- provider timeout: keep local fallback speech enabled and do not change state.
- unsafe event: inspect the smoke report, parser tests, and typed event schema before retrying.
```

- [ ] **Step 2: Link from README**

Add one sentence to the LLM section:

```markdown
LLM setup and smoke-test operations are documented in `docs\llm_expression_operations.md`.
```

- [ ] **Step 3: Run dry-run and focused tests**

```powershell
python tools\llm_dialogue_smoke.py --provider deepseek --dry-run
python -m pytest tests\test_llm_smoke.py tests\test_expression_event_pipeline.py tests\test_visual_actions.py -q
```

Expected:

```text
dry-run exits 0
focused tests pass
```

- [ ] **Step 4: Run live probe when a local key is available**

```powershell
$env:DEEPSEEK_API_KEY="local-key-not-for-commit"
python tools\llm_provider_diagnostics.py --provider deepseek --model deepseek-v4-flash --base-url https://api.deepseek.com --report artifacts\llm_smoke\provider-diagnostics-latest.json
python tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\deepseek-expression-cue-probe-latest.json
```

Expected:

```text
provider diagnostics ready
cue probe ok=true
state_mutation_check.ok=true
no key printed to stdout or report
```

- [ ] **Step 5: Commit P7.2**

```powershell
git add README.md docs\llm_expression_operations.md
git commit -m "docs: add llm expression operations guide"
```

Do not stage `artifacts\llm_smoke\*.json`.

---

## P8: Default Character Decision Package

**Purpose:** Decide whether the default runtime pack stays `original_oc` or becomes `xingxi_pixel_pet`. This package is a hard decision gate.

**Out of scope:** New art generation, new renderer work, fanwork distribution, LLM feature expansion.

### Task P8.1: Decision Preflight

**Files:**
- Read: `src/guanghe_companion/character_pack.py`
- Read: `assets/companion/xingxi_pixel_pet/manual_qa.json`
- Read: `docs/character_pack_distribution_policy.md`
- Create: `docs/default_character_decision_2026-06.md`

- [ ] **Step 1: Run preflight commands**

```powershell
python -m pytest tests\test_character_pack.py tests\test_character_registry.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --fail-on-warnings
python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-20260618\p8-default-decision-emote-mapping.json --markdown artifacts\route-scan-20260618\p8-default-decision-emote-mapping.md
```

Expected:

```text
all commands pass
generated artifacts remain ignored
```

- [ ] **Step 2: Create decision record**

Create `docs/default_character_decision_2026-06.md` with one of these two decisions.

For keeping the current default:

```markdown
# Default Character Decision 2026-06

Decision: keep `original_oc` as default.

Reason:

- `original_oc` remains the stable demo baseline.
- `xingxi_pixel_pet` is available as an optional bundled candidate.
- No runtime manifest or default constant change is required.

Verification:

- `python -m pytest` passes.
- `python tools\validate_character_pack.py assets\companion\original_oc` passes.
- `python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet` passes.
```

For promoting the pixel-pet candidate:

```markdown
# Default Character Decision 2026-06

Decision: promote `xingxi_pixel_pet` to default.

Reason:

- `xingxi_pixel_pet` passed manual QA, visual QA, promotion gate, LLM emote mapping, UI smoke, full tests, and Windows packaging gates.
- This changes the first-run visual experience to the pixel-pet sequence route.

Required code change:

- Change `DEFAULT_CHARACTER_ID` in `src/guanghe_companion/character_pack.py` from `original_oc` to `xingxi_pixel_pet`.

Required release gates:

- UI smoke.
- Full pytest.
- Windows app build.
- Installer build.
- Frozen control-panel smoke.
- Frozen `--pet-mode` smoke.
```

- [ ] **Step 3: Stop for explicit user confirmation before code change**

If the decision is to promote `xingxi_pixel_pet`, stop and get explicit user confirmation in the active thread before editing `src/guanghe_companion/character_pack.py`.

### Task P8.2: Default Promotion Implementation

Run this task only after explicit confirmation to promote `xingxi_pixel_pet`.

**Files:**
- Modify: `src/guanghe_companion/character_pack.py`
- Modify: `tests/test_character_pack.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_character_library_qa_tool.py`
- Modify: `README.md`
- Modify: `docs/default_character_decision_2026-06.md`

- [ ] **Step 1: Write failing default tests**

In `tests/test_character_pack.py`, update the default assertion:

```python
def test_load_default_character_pack_reads_original_oc_manifest():
    pack = load_default_character_pack()

    assert pack.character_id == "xingxi_pixel_pet"
```

If the test name still says `original_oc`, rename it to:

```python
def test_load_default_character_pack_reads_current_default_manifest():
```

In `tests/test_character_library_qa_tool.py`, update:

```python
assert payload["default_character_id"] == "xingxi_pixel_pet"
```

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests\test_character_pack.py tests\test_character_library_qa_tool.py -q
```

Expected:

```text
fails because DEFAULT_CHARACTER_ID is still original_oc
```

- [ ] **Step 3: Change the default constant**

Modify `src/guanghe_companion/character_pack.py`:

```python
DEFAULT_CHARACTER_ID = "xingxi_pixel_pet"
```

- [ ] **Step 4: Update public docs**

Update `README.md` so it states:

```markdown
The default companion pack is `xingxi_pixel_pet`. The older `original_oc` pack remains bundled as a stable fallback.
```

Update `docs/default_character_decision_2026-06.md` with:

```markdown
Implementation result: `DEFAULT_CHARACTER_ID` now points to `xingxi_pixel_pet`.
```

- [ ] **Step 5: Run focused tests**

```powershell
python -m pytest tests\test_character_pack.py tests\test_character_registry.py tests\test_character_library_qa_tool.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
```

- [ ] **Step 6: Run full and packaging gates**

```powershell
python -m pytest
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\windows-build-validation.json
```

- [ ] **Step 7: Run frozen smoke**

```powershell
dist\E-Moti\E-Moti.exe
dist\E-Moti\E-Moti.exe --pet-mode
```

Close each after 5 seconds and record the result in `docs/default_character_decision_2026-06.md`.

- [ ] **Step 8: Commit P8.2**

```powershell
git add src\guanghe_companion\character_pack.py tests\test_character_pack.py tests\test_character_library_qa_tool.py tests\test_app.py README.md docs\default_character_decision_2026-06.md
git commit -m "feat: promote pixel pet as default character"
```

If the decision is to keep `original_oc`, commit only the decision record:

```powershell
git add docs\default_character_decision_2026-06.md
git commit -m "docs: record default character decision"
```

---

## P9: Local UGC Character-Pack Workflow

**Purpose:** Make local character-pack creation/import understandable and testable without distributing fanwork assets.

**Out of scope:** Generating or committing Ikaros/Nairong assets, public fanwork distribution, replacing default assets.

### Task P9.1: Authoring Runbook

**Files:**
- Create: `docs/character_pack_authoring_runbook.md`
- Modify: `README.md`

- [ ] **Step 1: Create runbook**

Create `docs/character_pack_authoring_runbook.md`:

```markdown
# Character Pack Authoring Runbook

## Goal

Create a complete local character pack that can be validated, imported, selected in the character library, and kept separate from other characters' state.

## Required Pack Shape

```text
character_packs_drafts/xingxi_pixel_pet/
  character.json
  dialogue_style.json
  motion_manifest.json
  shop_items.json
  spritesheet.png
  preview/contact-sheet.png
  provenance.md
  LICENSE.md
  qa_report.json
```

## Distribution Boundary

Use one of:

- `shareable_after_review`
- `local_ugc_only`
- `private_local_fanwork`

Use `private_local_fanwork` for Ikaros or Nairong experiments unless rights are cleared.

## Validation Commands

```powershell
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet
python tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\xingxi-pixel-pet-latest.json --screenshot-dir artifacts\character-library-qa\xingxi-pixel-pet-latest-screenshots
python -m pytest tests\test_character_registry.py tests\test_character_session.py tests\test_character_pack_import_tool.py tests\test_app.py -q
```

## Import Rule

Only import complete packs that pass validation. Do not copy ignored draft folders directly into `assets/companion/`.
```

- [ ] **Step 2: Link from README**

Add:

```markdown
Local character-pack authoring is documented in `docs\character_pack_authoring_runbook.md`.
```

- [ ] **Step 3: Verify**

```powershell
git diff --check
python -m pytest tests\test_repository_hygiene.py tests\test_character_pack.py tests\test_character_pack_import_tool.py -q
python -m pytest
```

- [ ] **Step 4: Commit P9.1**

```powershell
git add README.md docs\character_pack_authoring_runbook.md
git commit -m "docs: add character pack authoring runbook"
```

### Task P9.2: Starter Pack Scaffolder

**Files:**
- Create: `tools/scaffold_character_pack.py`
- Create: `tests/test_character_pack_scaffold_tool.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_character_pack_scaffold_tool.py`:

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_scaffold_character_pack_writes_private_local_fanwork_pack(tmp_path: Path) -> None:
    target = tmp_path / "packs"

    result = subprocess.run(
        [
            sys.executable,
            "tools/scaffold_character_pack.py",
            "--character-id",
            "test_pet",
            "--name",
            "Test Pet",
            "--title",
            "Local test pack",
            "--distribution-boundary",
            "private_local_fanwork",
            "--output-root",
            str(target),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0
    pack_dir = target / "test_pet"
    character = json.loads((pack_dir / "character.json").read_text(encoding="utf-8"))
    assert character["character_id"] == "test_pet"
    assert character["distribution_boundary"] == "private_local_fanwork"
    assert (pack_dir / "provenance.md").read_text(encoding="utf-8").startswith("# Provenance")
    assert (pack_dir / "preview").is_dir()


def test_scaffold_character_pack_rejects_unsafe_character_id(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "tools/scaffold_character_pack.py",
            "--character-id",
            "..\\bad",
            "--name",
            "Bad",
            "--title",
            "Bad",
            "--output-root",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 2
    assert "unsafe character id" in result.stderr
```

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests\test_character_pack_scaffold_tool.py -q
```

Expected:

```text
fails because tools/scaffold_character_pack.py does not exist
```

- [ ] **Step 3: Implement scaffolder**

Create `tools/scaffold_character_pack.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from guanghe_companion.character_session import is_safe_character_id


ALLOWED_BOUNDARIES = ("shareable_after_review", "local_ugc_only", "private_local_fanwork")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local character-pack scaffold.")
    parser.add_argument("--character-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--distribution-boundary", choices=ALLOWED_BOUNDARIES, default="private_local_fanwork")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    if not is_safe_character_id(args.character_id):
        parser.error("unsafe character id")

    pack_dir = Path(args.output_root) / args.character_id
    pack_dir.mkdir(parents=True, exist_ok=False)
    (pack_dir / "preview").mkdir()
    (pack_dir / "item_icons").mkdir()

    _write_json(
        pack_dir / "character.json",
        {
            "character_id": args.character_id,
            "name": args.name,
            "title": args.title,
            "description": "Local character-pack scaffold. Replace placeholder art before import.",
            "spritesheet": "spritesheet.png",
            "motion_manifest": "motion_manifest.json",
            "renderer": {"backend": "sprite", "motion_map": {}, "expression_map": {}},
            "default_mode": "Calm",
            "modes": ["Calm"],
            "mode_descriptions": {"Calm": "Stable local test mode."},
            "motion_labels": {"Default": "Idle"},
            "distribution_boundary": args.distribution_boundary,
            "relationship_decorations": [],
        },
    )
    _write_json(
        pack_dir / "dialogue_style.json",
        {
            "voice": "local test companion",
            "tone": "gentle",
            "taboos": ["Do not claim bundled distribution rights."],
        },
    )
    _write_json(
        pack_dir / "motion_manifest.json",
        {
            "sheet_columns": 1,
            "sheet_rows": 9,
            "frame_width": 192,
            "frame_height": 208,
            "background": "transparent",
            "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
        },
    )
    _write_json(pack_dir / "shop_items.json", [])
    (pack_dir / "provenance.md").write_text(
        "# Provenance\n\nGenerated as a local scaffold. Replace placeholder metadata before distribution review.\n",
        encoding="utf-8",
    )
    (pack_dir / "LICENSE.md").write_text(
        "# License\n\nLocal scaffold only. Add rights information before distribution.\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "path": str(pack_dir)}, ensure_ascii=False))
    return 0


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify**

```powershell
python -m pytest tests\test_character_pack_scaffold_tool.py -q
python -m pytest tests\test_character_pack.py tests\test_character_pack_import_tool.py tests\test_character_registry.py -q
python -m pytest
```

- [ ] **Step 5: Commit P9.2**

```powershell
git add tools\scaffold_character_pack.py tests\test_character_pack_scaffold_tool.py
git commit -m "feat: add local character pack scaffolder"
```

---

## P10: Architecture Decoupling

**Purpose:** Reduce coupling in large integration files while preserving behavior.

**Out of scope:** UI redesign, new features, state-machine changes, default-character changes.

### Task P10.1: Extract Character Library Pure View Model

**Files:**
- Create: `src/guanghe_companion/character_library_view_model.py`
- Create: `tests/test_character_library_view_model.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_app.py`, `tests/test_character_library_qa_tool.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_character_library_view_model.py`:

```python
from __future__ import annotations

from pathlib import Path

from guanghe_companion.character_library_view_model import (
    character_pack_distribution_text,
    character_pack_import_review_text,
)
from guanghe_companion.character_registry import CharacterPackSummary


def _summary() -> CharacterPackSummary:
    root = Path("assets/companion/xingxi_pixel_pet")
    return CharacterPackSummary(
        character_id="xingxi_pixel_pet",
        name="星汐 Pixel Pet",
        title="像素桌面同伴候选",
        description="QA-gated optional candidate.",
        path=root,
        source="builtin",
        distribution_boundary="shareable_after_review",
        preview_path=root / "preview" / "contact-sheet.png",
        provenance_paths=(root / "provenance.md",),
        license_paths=(root / "LICENSE.md",),
    )


def test_character_pack_distribution_text_keeps_provenance_and_license_relative() -> None:
    text = character_pack_distribution_text(_summary())

    assert "Distribution" in text
    assert "Source: builtin" in text
    assert "Distribution: shareable_after_review" in text
    assert "Provenance: provenance.md" in text
    assert "License: LICENSE.md" in text


def test_character_pack_import_review_text_warns_about_rights() -> None:
    text = character_pack_import_review_text(_summary())

    assert "Import character pack: xingxi_pixel_pet" in text
    assert "Only import packs you have rights to use and distribute." in text
```

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests\test_character_library_view_model.py -q
```

Expected:

```text
fails because guanghe_companion.character_library_view_model does not exist
```

- [ ] **Step 3: Implement pure helper module**

Create `src/guanghe_companion/character_library_view_model.py`:

```python
from __future__ import annotations

from pathlib import Path

from .character_registry import CharacterPackSummary


def character_pack_distribution_text(pack: CharacterPackSummary) -> str:
    return "\n".join(
        (
            "Distribution",
            f"Source: {pack.source}",
            f"Distribution: {pack.distribution_boundary}",
            f"Provenance: {_relative_pack_paths(pack, pack.provenance_paths)}",
            f"License: {_relative_pack_paths(pack, pack.license_paths)}",
        )
    )


def character_pack_import_review_text(pack: CharacterPackSummary) -> str:
    return "\n\n".join(
        (
            f"Import character pack: {pack.character_id}",
            f"{pack.name}\n{pack.title}",
            character_pack_distribution_text(pack),
            "Only import packs you have rights to use and distribute.",
        )
    )


def _relative_pack_paths(pack: CharacterPackSummary, paths: tuple[Path, ...]) -> str:
    if not paths:
        return "missing"
    labels: list[str] = []
    for path in paths:
        try:
            labels.append(path.relative_to(pack.path).as_posix())
        except ValueError:
            labels.append(path.name)
    return ", ".join(labels)
```

- [ ] **Step 4: Replace helpers in `app.py`**

In `src/guanghe_companion/app.py`, add:

```python
from .character_library_view_model import (
    character_pack_distribution_text,
    character_pack_import_review_text,
)
```

Replace calls:

```python
_character_pack_distribution_text(pack)
_character_pack_import_review_text(pack)
```

with:

```python
character_pack_distribution_text(pack)
character_pack_import_review_text(pack)
```

Remove these local helper functions from `app.py`:

```python
def _character_pack_distribution_text(...)
def _relative_pack_paths(...)
def _character_pack_import_review_text(...)
```

- [ ] **Step 5: Verify behavior**

```powershell
python -m pytest tests\test_character_library_view_model.py tests\test_app.py tests\test_character_library_qa_tool.py -q
python -m pytest
```

- [ ] **Step 6: Commit P10.1**

```powershell
git add src\guanghe_companion\character_library_view_model.py src\guanghe_companion\app.py tests\test_character_library_view_model.py
git commit -m "refactor: extract character library view model"
```

### Task P10.2: Extract Readiness Check Providers Incrementally

**Files:**
- Create: `tools/readiness_checks.py`
- Modify: `tools/release_readiness_report.py`
- Modify: `tests/test_release_readiness_report.py`

- [ ] **Step 1: Identify one low-risk check to extract**

Start with source character-pack readiness because it is already deterministic and file-based.

Run:

```powershell
python -m pytest tests\test_release_readiness_report.py -q
```

Expected:

```text
passes before refactor
```

- [ ] **Step 2: Add extracted provider tests**

Append to `tests/test_release_readiness_report.py`:

```python
def test_source_character_pack_check_reports_ready_for_original_oc() -> None:
    from tools.readiness_checks import build_source_character_pack_check

    check = build_source_character_pack_check(REPO_ROOT / "assets" / "companion" / "original_oc")

    assert check["id"] == "source_character_pack"
    assert check["ok"] is True
    assert check["status"] == "ready"
    assert check["character_id"] == "original_oc"
```

- [ ] **Step 3: Run and confirm failure**

```powershell
python -m pytest tests\test_release_readiness_report.py::test_source_character_pack_check_reports_ready_for_original_oc -q
```

Expected:

```text
fails because tools.readiness_checks does not exist
```

- [ ] **Step 4: Implement provider**

Create `tools/readiness_checks.py` with a function returning the same dictionary shape currently used by `tools/release_readiness_report.py` for source character-pack checks. Keep this function pure:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from guanghe_companion.character_registry import summarize_character_pack_dir, validate_character_pack_dir


def build_source_character_pack_check(path: Path) -> dict[str, Any]:
    report = validate_character_pack_dir(path, source="local")
    summary = summarize_character_pack_dir(path, source="local") if report.ok else None
    return {
        "id": "source_character_pack",
        "label": "Source Character Pack",
        "ok": report.ok,
        "status": "ready" if report.ok else "blocked",
        "path": str(path),
        "character_id": report.character_id,
        "manual_qa_required": False,
        "distribution_boundary": summary.distribution_boundary if summary is not None else "",
        "provenance_files": [item.name for item in summary.provenance_paths] if summary is not None else [],
        "license_files": [item.name for item in summary.license_paths] if summary is not None else [],
        "errors": list(report.errors),
        "warnings": [],
        "next_actions": ["pack is ready for local import or distribution review"] if report.ok else [],
    }
```

- [ ] **Step 5: Wire release report to provider**

Modify `tools/release_readiness_report.py` so its source character-pack branch calls:

```python
from tools.readiness_checks import build_source_character_pack_check
```

and appends:

```python
checks.append(build_source_character_pack_check(Path(args.character_pack)))
```

Preserve the existing public JSON shape.

- [ ] **Step 6: Verify**

```powershell
python -m pytest tests\test_release_readiness_report.py -q
python tools\release_readiness_report.py --character-pack assets\companion\xingxi_pixel_pet --json artifacts\release-readiness-p10-refactor.json --markdown artifacts\release-readiness-p10-refactor.md
python -m pytest
```

- [ ] **Step 7: Commit P10.2**

```powershell
git add tools\readiness_checks.py tools\release_readiness_report.py tests\test_release_readiness_report.py
git commit -m "refactor: extract source character readiness check"
```

---

## P11: Pixel-Pet Production Runbook And Final Release Gate

**Purpose:** End the roadmap with a repeatable pixel-pet production workflow and a final gate that proves the project is demo-ready and open-source-ready.

**Out of scope:** New default promotion without P8 decision, new third-party assets, new renderer route.

### Task P11.1: Pixel-Pet Sequence Status Tool

**Files:**
- Create: `tools/pixel_pet_sequence_status.py`
- Create: `tests/test_pixel_pet_sequence_status_tool.py`
- Modify: `docs/pixel_pet_sequence_sop.md`

- [ ] **Step 1: Write failing tests**

Create `tests/test_pixel_pet_sequence_status_tool.py`:

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pixel_pet_sequence_status_reports_missing_run_dir(tmp_path: Path) -> None:
    report = tmp_path / "status.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/pixel_pet_sequence_status.py",
            "--run-dir",
            str(tmp_path / "missing"),
            "--report",
            str(report),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["status"] == "missing_run_dir"


def test_pixel_pet_sequence_status_reports_candidate_pack_ready(tmp_path: Path) -> None:
    pack_dir = tmp_path / "run" / "character_packs_drafts" / "sample_pet"
    pack_dir.mkdir(parents=True)
    (pack_dir / "character.json").write_text("{}", encoding="utf-8")
    report = tmp_path / "status.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/pixel_pet_sequence_status.py",
            "--run-dir",
            str(tmp_path / "run"),
            "--report",
            str(report),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["status"] == "has_candidate_pack"
    assert payload["candidate_pack_count"] == 1
```

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m pytest tests\test_pixel_pet_sequence_status_tool.py -q
```

Expected:

```text
fails because tools/pixel_pet_sequence_status.py does not exist
```

- [ ] **Step 3: Implement read-only status tool**

Create `tools/pixel_pet_sequence_status.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize a pixel-pet sequence draft run.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    payload = build_status(run_dir)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ok"] else 1


def build_status(run_dir: Path) -> dict[str, Any]:
    if not run_dir.is_dir():
        return {
            "ok": False,
            "status": "missing_run_dir",
            "run_dir": str(run_dir),
            "candidate_pack_count": 0,
            "candidate_packs": [],
        }
    candidate_root = run_dir / "character_packs_drafts"
    candidate_packs = sorted(path for path in candidate_root.glob("*") if path.is_dir()) if candidate_root.is_dir() else []
    status = "has_candidate_pack" if candidate_packs else "needs_candidate_pack"
    return {
        "ok": bool(candidate_packs),
        "status": status,
        "run_dir": str(run_dir),
        "candidate_pack_count": len(candidate_packs),
        "candidate_packs": [str(path) for path in candidate_packs],
    }


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Link from SOP**

Add this section to `docs/pixel_pet_sequence_sop.md`:

```markdown
## Draft Run Status

Use the read-only status tool before deciding whether a hatch-pet draft has enough structure for validation:

```powershell
python tools\pixel_pet_sequence_status.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2 --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\sequence-status.json
```

The report is an ignored artifact. It does not copy, edit, promote, or import assets.
```

- [ ] **Step 5: Verify**

```powershell
python -m pytest tests\test_pixel_pet_sequence_status_tool.py -q
python -m pytest tests\test_pixel_pet_pack_validator_tool.py tests\test_pixel_pet_visual_qa.py tests\test_pixel_pet_emote_mapping.py -q
python -m pytest
```

- [ ] **Step 6: Commit P11.1**

```powershell
git add tools\pixel_pet_sequence_status.py tests\test_pixel_pet_sequence_status_tool.py docs\pixel_pet_sequence_sop.md
git commit -m "feat: add pixel pet sequence status tool"
```

### Task P11.2: Final Release Gate Record

**Files:**
- Create: `docs/final_release_gate_2026-06.md`

- [ ] **Step 1: Run final source gates**

```powershell
git status --short --untracked-files=all
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-20260618\final-xingxi-pixel-pack-validation.json
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\route-scan-20260618\final-xingxi-pixel-visual-qa.json --preview artifacts\route-scan-20260618\final-xingxi-pixel-visual-qa-preview.png --fail-on-warnings
python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-20260618\final-xingxi-pixel-emote-mapping.json --markdown artifacts\route-scan-20260618\final-xingxi-pixel-emote-mapping.md
```

- [ ] **Step 2: Run UI and release gates**

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python tools\release_readiness_report.py --character-pack assets\companion\xingxi_pixel_pet --llm-report artifacts\llm_smoke\deepseek-expression-cue-probe-clean-edge-live-rerun-20260618.json --pixel-pet-emote-mapping-report artifacts\route-scan-20260618\final-xingxi-pixel-emote-mapping.json --pixel-pet-visual-qa-report artifacts\route-scan-20260618\final-xingxi-pixel-visual-qa.json --json artifacts\route-scan-20260618\final-release-readiness.json --markdown artifacts\route-scan-20260618\final-release-readiness.md
```

- [ ] **Step 3: Run packaging gates if P8 changed default or release packaging changed**

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\windows-build-validation.json
```

- [ ] **Step 4: Create final gate doc**

Create `docs/final_release_gate_2026-06.md`:

```markdown
# Final Release Gate 2026-06

## Product State

- Default character: `original_oc` unless P8.2 promoted `xingxi_pixel_pet`; if P8.2 ran, record `xingxi_pixel_pet` and the P8 commit hash.
- Optional bundled character: `xingxi_pixel_pet`.
- LLM expression provider status: record the latest `tools\llm_expression_cue_probe.py` report path and `ok` value.
- Pixel-pet visual QA status: record the latest `tools\art\pixel_pet_visual_qa.py --fail-on-warnings` result.
- Release readiness status: record the latest `tools\release_readiness_report.py` status.
- Windows build status: `not rerun in P11` unless packaging gates were required; if rerun, record `ok` or the blocker.
- Installer status: `not rerun in P11` unless packaging gates were required; if rerun, record `ok` or the blocker.

## Verification Commands

```powershell
python -m pytest
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --fail-on-warnings
python tools\release_readiness_report.py --character-pack assets\companion\xingxi_pixel_pet
```

## Distribution Boundary

- `original_oc`: default bundled original character pack unless P8.2 changed default.
- `xingxi_pixel_pet`: QA-gated optional bundled official candidate, or default if P8.2 explicitly promoted it.
- Ikaros: local UGC/fanwork workflow representative only; not bundled.
- Nairong: local UGC/fanwork workflow representative only; not bundled.

## Known Limits

- LLM does not own growth state, memory, relationship, inventory, goals, or saves.
- Ikaros and Nairong are local UGC workflow representatives only.
- Live2D, LivePortrait, AI-video, and VN portrait routes remain research paths.
```

Replace the status sentences above with the actual command result from this package before committing.

- [ ] **Step 5: Verify final docs**

```powershell
git diff --check
python -m pytest tests\test_repository_hygiene.py -q
python -m pytest
```

- [ ] **Step 6: Commit P11.2**

```powershell
git add docs\final_release_gate_2026-06.md
git commit -m "docs: record final release gate"
```

---

## Final Definition Of Done

P6-P11 is complete only when:

- `python -m pytest` passes after the final package.
- `git status --short --untracked-files=all` is understood and clean except intentionally ignored local runtime files.
- `data/companion_save.json` is not staged or committed.
- No real provider key is tracked.
- Public docs describe the current product route accurately.
- `original_oc` default status is either preserved or changed only by P8 with explicit decision evidence.
- `xingxi_pixel_pet` remains validated as an optional bundled candidate or is promoted through P8 gates.
- LLM expression has a current diagnostics/smoke path and a no-state-mutation report.
- UGC/fanwork boundaries are visible in docs and UI/import workflow.
- At least one architecture decoupling commit lands without changing behavior.
- Final release gate documentation records actual commands and results.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-18-p6-p11-development-roadmap.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per package or task, review between tasks, and keep commits small.
2. **Inline Execution** - execute tasks in this session using executing-plans, with checkpoints at P8 and before any packaging/default-character decision.

Recommended execution order:

```text
P6.1 -> P6.2 -> P7.1 -> P7.2 -> P8.1 -> P8.2 only if confirmed -> P9.1 -> P9.2 -> P10.1 -> P10.2 -> P11.1 -> P11.2
```

Hard stop points:

- P8 default-character promotion.
- Any fanwork/IP asset distribution.
- Any provider/network blocker that prevents live LLM verification.
- Any packaging failure that requires changing installer behavior.
- Any attempt to add mouse, keyboard, clipboard, window control, wake-word, startup, or elevated install features.
