# Voice Service Experience Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the voice layer operable from the demo UI: the user can check local TTS/ASR service readiness, start missing local services when scripts are available, and read clear status messages before testing speech or ASR.

**Architecture:** Extract service probing and launcher command construction into a focused `voice_service_control` module. Keep the PySide6 panel thin: it emits user actions and displays formatted status text. Reuse the same module from the existing preflight CLI so UI and QA scripts do not drift.

**Tech Stack:** Python 3.11, PySide6, existing PowerShell service scripts, pytest.

---

## Files

- Create: `src/guanghe_companion/voice_service_control.py`
- Create: `tests/test_voice_service_control.py`
- Modify: `tools/voice_services/preflight_voice_services.py`
- Modify: `tests/test_voice_service_preflight_tool.py` only if the CLI import path requires it
- Modify: `src/guanghe_companion/capability_panels.py`
- Modify: `src/guanghe_companion/app.py`
- Modify: `tests/test_capability_panels.py`
- Modify: `tests/test_app.py`

## Task 1: Shared Voice Service Control Module

- [x] **Step 1: Write failing module tests**

Create tests for three behaviors:

```python
def test_probe_voice_services_formats_ready_and_missing_statuses():
    ...

def test_launch_missing_voice_services_starts_only_down_services(tmp_path):
    ...

def test_launch_missing_voice_services_reports_missing_scripts(tmp_path):
    ...
```

Expected first run: import fails because `guanghe_companion.voice_service_control` does not exist.

- [x] **Step 2: Implement the module**

Implement:

```python
VoiceServiceEndpoint
VoiceServiceStatus
VoiceServiceLaunchResult
DEFAULT_VOICE_SERVICE_ENDPOINTS
probe_voice_services()
all_voice_services_ready()
format_voice_service_statuses()
launch_missing_voice_services()
format_voice_service_launch_results()
```

The launcher must only start missing services, must not hide missing script paths, and must not change any companion save/state.

- [x] **Step 3: Verify focused tests**

Run:

```powershell
python -m pytest tests\test_voice_service_control.py -q
```

Expected: all tests pass.

## Task 2: Reuse Module From Existing Preflight CLI

- [x] **Step 1: Update CLI to use shared endpoints and probe formatting**

`tools/voice_services/preflight_voice_services.py` should call `probe_voice_services(timeout=args.timeout, probe=_probe_http)` and write the same JSON shape as before.

- [x] **Step 2: Verify CLI tests**

Run:

```powershell
python -m pytest tests\test_voice_service_preflight_tool.py tests\test_voice_service_control.py -q
```

Expected: all tests pass.

## Task 3: Add Voice Service UI Controls

- [x] **Step 1: Write failing panel tests**

Extend `tests/test_capability_panels.py` so `VoiceSettingsPanel` exposes:

```python
voice_service_status_label
voice_service_preflight_button
voice_service_launch_button
voiceServicePreflightRequested
voiceServiceLaunchRequested
set_service_status()
```

Expected first run: attributes or signals are missing.

- [x] **Step 2: Implement panel widgets**

Add a compact service-status row above the detailed TTS/ASR settings. The panel only emits signals and displays text.

- [x] **Step 3: Verify panel tests**

Run:

```powershell
python -m pytest tests\test_capability_panels.py -q
```

Expected: all tests pass.

## Task 4: Wire UI Actions In The App

- [x] **Step 1: Write failing app tests**

Extend `tests/test_app.py` to monkeypatch `probe_voice_services()` and `launch_missing_voice_services()`, click the new buttons, and assert status text changes without mutating character state.

- [x] **Step 2: Implement app handlers**

Add:

```python
_handle_voice_service_preflight()
_handle_voice_service_launch()
```

Connect them to the panel signals. Use repo-root service scripts when available; if the app is frozen without scripts, report the missing script instead of failing silently.

- [x] **Step 3: Verify UI tests**

Run:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
```

Expected: all tests pass.

## Task 5: Final Verification

- [x] **Step 1: Run focused voice tests**

```powershell
python -m pytest tests\test_voice_service_control.py tests\test_voice_service_preflight_tool.py tests\test_capability_panels.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
```

- [x] **Step 2: Run full suite**

```powershell
python -m pytest
```

- [x] **Step 3: Check diff hygiene**

```powershell
git diff --check
git status --short --untracked-files=all
```

- [x] **Step 4: Commit focused package**

```powershell
git add docs/superpowers/plans/2026-06-24-voice-service-experience-layer.md src/guanghe_companion/voice_service_control.py tools/voice_services/preflight_voice_services.py src/guanghe_companion/capability_panels.py src/guanghe_companion/app.py tests/test_voice_service_control.py tests/test_voice_service_preflight_tool.py tests/test_capability_panels.py tests/test_app.py
git commit -m "feat: add voice service experience controls"
```

## Task 6: Portable Voice Service Packaging Follow-up

- [x] **Step 1: Add frozen voice service runtime path tests**

`tests/test_runtime_paths.py` verifies that frozen apps prefer `_MEIPASS/voice_services`.

- [x] **Step 2: Add explicit bundled script directory support**

`launch_missing_voice_services()` accepts `scripts_dir`, and the app passes `voice_services_root()` so frozen builds use `_internal/voice_services`.

- [x] **Step 3: Bundle voice service launch scripts**

`tools/build_windows_app.ps1` copies `tools/voice_services` into the PyInstaller data bundle. `tools/validate_windows_build.py` rejects frozen builds missing required voice-service scripts.

- [x] **Step 4: Add optional portable runtime copy path**

`tools/build_windows_app.ps1` and `tools/build_windows_installer.ps1` support `-VoiceRuntimePath`. When a prepared runtime directory is supplied, it is copied to `dist/E-Moti/voice_runtime`.

- [x] **Step 5: Prefer portable voice runtime in launch scripts**

Qwen3TTS and SenseVoice scripts prefer `voice_runtime/.voice-services/...` when present. GPT-SoVITS prefers `voice_runtime/GPT-SoVITS` and `voice_runtime/gptsovits-venv/Scripts/python.exe` before falling back to environment variables or local development paths.

- [x] **Step 6: Verify package behavior**

Verified with focused tests, full pytest, Windows app build, Windows installer build, build validator, and frozen control-panel / `--pet-mode` 5-second smoke.
