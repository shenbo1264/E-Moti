# Unified Voice Provider And Bilingual TTS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give E-Moti one stable app-facing TTS provider while allowing each character to keep its own backend voice route, and let Ikaros display Chinese text while synthesizing Japanese speech.

**Architecture:** Add an in-process `http_emoti_voice` gateway provider in the existing TTS layer. Character packs will point the app at the same provider, while profile metadata chooses the backend provider and optional synthesis-language strategy. UI display keeps using validated typed `speech`; TTS may consume a separate presentational synthesis text that never mutates growth state, inventory, relationship, memory, goals, or saves.

**Tech Stack:** PySide6 app, existing `TTSManager`, `CapabilityRuntime`, `CharacterVoiceProfile`, HTTP Qwen3TTS service, HTTP GPT-SoVITS service, pytest.

---

## Current Verified State

- Baseline command on 2026-06-24: `python -m pytest` -> `946 passed`.
- Current app-facing providers differ by character:
  - `xingxi_pixel_pet`: `http_qwen3tts`, `http://127.0.0.1:9880/`, voice `Vivian`.
  - `ikaros_pixel_pet`: `http_gptsovits`, `http://127.0.0.1:9882/`, voice `ikaros_curated160_e4`.
  - `nairong_pixel_pet`: `http_qwen3tts`, `http://127.0.0.1:9880/`, voice `Dylan`.
- Character switching does not synthesize speech. TTS is invoked later through `CapabilityRuntime.speak_text()`, then `TTSManager.speak()`.
- The typed event model currently has one user-visible `speech` string. There is no separate synthesis text field yet.

## 2026-06-24 Implementation Result

- Implemented `http_emoti_voice` as the single app-facing provider.
- Added backend provider/profile fields so each character can delegate to Qwen3TTS or GPT-SoVITS without changing the app-facing provider.
- Added profile-level bilingual synthesis metadata:
  - `display_language`
  - `synthesis_language`
  - `synthesis_text_mode`
  - `synthesis_text_map`
- Migrated bundled Xingxi, Ikaros, and Nairong character profiles to `http_emoti_voice`.
- Ikaros keeps GPT-SoVITS as backend and includes a first-pass Chinese display / Japanese synthesis static map for demo lines.
- Verified focused tests, UI/desktop tests, full regression, JSON validation, live TTS smoke, Windows build, installer build, frozen build validation, and frozen exe smoke.

Fresh verification after implementation:

```powershell
python -m pytest tests\test_voice_tts.py tests\test_voice_capability_smoke_tool.py tests\test_character_voice_profile.py tests\test_capability_settings.py tests\test_capability_runtime.py tests\test_voice_provider_catalog.py tests\test_character_pack.py tests\test_capability_panels.py -q
# 63 passed

python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
# 107 passed

python -m pytest
# 953 passed
```

## Product Decision

Use a single app-facing provider:

```json
"provider": "http_emoti_voice"
```

Keep backend route in profile metadata:

```json
"backend_provider": "http_gptsovits",
"backend_api_url": "http://127.0.0.1:9882/",
"backend_model_variant": "gptsovits_v2"
```

For Ikaros bilingual presentation:

```json
"display_language": "zh",
"synthesis_language": "all_ja",
"synthesis_text_mode": "profile_static_map"
```

The first implementation uses a deterministic local phrase map for known demo lines and falls back to the validated display text when no mapping exists. This keeps the architecture testable without adding an LLM translation call into the TTS hot path. A later package can replace the mapper with an LLM translation adapter behind the same interface.

## Files

- Modify: `src/guanghe_companion/capability_settings.py`
  - Add `http_emoti_voice` provider alias.
  - Add backend and bilingual synthesis fields to `TTSSettings`.
- Modify: `src/guanghe_companion/character_voice_profile.py`
  - Parse and expose backend provider fields.
  - Parse and expose `display_language`, `synthesis_language`, `synthesis_text_mode`, and `synthesis_text_map`.
- Modify: `src/guanghe_companion/capability_runtime.py`
  - Apply the new character profile fields into runtime `TTSSettings`.
- Modify: `src/guanghe_companion/voice_provider_catalog.py`
  - Add `http_emoti_voice`.
- Modify: `src/guanghe_companion/voice_tts.py`
  - Add `EmotiVoiceGatewayProvider`.
  - Add a small `select_synthesis_text()` helper.
  - Keep Qwen and GPT-SoVITS providers unchanged behind the gateway.
- Modify: `tools/voice_capability_smoke.py`
  - Allow skip-playback construction for `http_emoti_voice`.
- Modify:
  - `assets/companion/xingxi_pixel_pet/character.json`
  - `assets/companion/ikaros_pixel_pet/character.json`
  - `assets/companion/nairong_pixel_pet/character.json`
- Tests:
  - `tests/test_capability_settings.py`
  - `tests/test_character_voice_profile.py`
  - `tests/test_capability_runtime.py`
  - `tests/test_voice_provider_catalog.py`
  - `tests/test_voice_tts.py`
  - `tests/test_voice_capability_smoke_tool.py`
  - `tests/test_character_pack.py`

## Task 1: Profile Contract

**Files:**
- Modify: `tests/test_character_voice_profile.py`
- Modify: `src/guanghe_companion/character_voice_profile.py`
- Modify: `tests/test_capability_settings.py`
- Modify: `src/guanghe_companion/capability_settings.py`

- [ ] **Step 1: Write failing profile tests**

Add tests that assert a character profile can expose:

```python
assert profile.provider == "http_emoti_voice"
assert profile.backend_provider == "http_gptsovits"
assert profile.backend_api_url == "http://127.0.0.1:9882/"
assert profile.backend_model_variant == "gptsovits_v2"
assert profile.display_language == "zh"
assert profile.synthesis_language == "all_ja"
assert profile.synthesis_text_mode == "profile_static_map"
assert profile.synthesis_text_map == {"我在这里。": "マスター、私はここにいます。"}
```

Also assert settings aliases:

```python
assert TTSSettings.from_dict({"provider": "emoti-voice"}).provider == "http_emoti_voice"
assert TTSSettings.from_dict({"provider": "http_emoti_voice", "backend_provider": "gpt-sovits"}).backend_provider == "http_gptsovits"
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
python -m pytest tests\test_character_voice_profile.py tests\test_capability_settings.py -q
```

Expected: tests fail because the new fields do not exist yet.

- [ ] **Step 3: Implement minimal profile/settings fields**

Add frozen dataclass fields and sanitizers. Keep maps small and bounded:

```python
synthesis_text_map: dict[str, str] = field(default_factory=dict)
```

Clean each key/value to control-character-free text with maximum length 160.

- [ ] **Step 4: Verify tests pass**

Run:

```powershell
python -m pytest tests\test_character_voice_profile.py tests\test_capability_settings.py -q
```

Expected: pass.

## Task 2: Runtime Application Boundary

**Files:**
- Modify: `tests/test_capability_runtime.py`
- Modify: `src/guanghe_companion/capability_runtime.py`

- [ ] **Step 1: Write failing runtime test**

Add a test where global settings use `http_qwen3tts`, profile uses `http_emoti_voice`, and backend route is GPT-SoVITS:

```python
assert received_settings.provider == "http_emoti_voice"
assert received_settings.backend_provider == "http_gptsovits"
assert received_settings.backend_api_url == "http://127.0.0.1:9882/"
assert received_settings.synthesis_language == "all_ja"
assert received_settings.synthesis_text_map["我在这里。"] == "マスター、私はここにいます。"
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
python -m pytest tests\test_capability_runtime.py::test_voice_runtime_applies_unified_gateway_and_bilingual_profile -q
```

Expected: fail because runtime profile application does not copy the new fields.

- [ ] **Step 3: Implement runtime profile copying**

Extend `apply_character_tts_profile()` to copy backend and synthesis fields. Do not change ASR, state, memory, relationship, inventory, or saves.

- [ ] **Step 4: Verify runtime tests**

Run:

```powershell
python -m pytest tests\test_capability_runtime.py -q
```

Expected: pass.

## Task 3: Unified Gateway Provider

**Files:**
- Modify: `tests/test_voice_tts.py`
- Modify: `src/guanghe_companion/voice_tts.py`
- Modify: `tests/test_voice_provider_catalog.py`
- Modify: `src/guanghe_companion/voice_provider_catalog.py`

- [ ] **Step 1: Write failing gateway tests**

Add tests proving:

```python
result = gateway.speak("我在这里。", settings)
assert delegated_text == "マスター、私はここにいます。"
assert delegated_settings.provider == "http_gptsovits"
assert delegated_settings.api_url == "http://127.0.0.1:9882/"
assert delegated_settings.language == "all_ja"
assert delegated_settings.model_variant == "gptsovits_v2"
```

Also test fallback when no map entry exists:

```python
assert delegated_text == "新的中文句子。"
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
python -m pytest tests\test_voice_tts.py tests\test_voice_provider_catalog.py -q
```

Expected: fail because `http_emoti_voice` does not exist.

- [ ] **Step 3: Implement `EmotiVoiceGatewayProvider`**

The provider chooses backend settings by replacing:

```python
provider=settings.backend_provider
api_url=settings.backend_api_url
language=settings.synthesis_language or settings.language
model_variant=settings.backend_model_variant or settings.model_variant
```

Then delegates through an internal provider factory. If backend is missing or equals `http_emoti_voice`, return a clear failure instead of recursing.

- [ ] **Step 4: Verify gateway tests**

Run:

```powershell
python -m pytest tests\test_voice_tts.py tests\test_voice_provider_catalog.py -q
```

Expected: pass.

## Task 4: Smoke Tool And Character Profiles

**Files:**
- Modify: `tests/test_voice_capability_smoke_tool.py`
- Modify: `tools/voice_capability_smoke.py`
- Modify: `tests/test_character_pack.py`
- Modify:
  - `assets/companion/xingxi_pixel_pet/character.json`
  - `assets/companion/ikaros_pixel_pet/character.json`
  - `assets/companion/nairong_pixel_pet/character.json`

- [ ] **Step 1: Write failing smoke/profile tests**

Assert `voice_capability_smoke` can construct `http_emoti_voice` with `--skip-playback`.

Assert bundled characters now use the unified app-facing provider:

```python
assert pack.tts_profile.provider == "http_emoti_voice"
```

Assert Ikaros keeps GPT-SoVITS as backend:

```python
assert pack.tts_profile.backend_provider == "http_gptsovits"
assert pack.tts_profile.synthesis_language == "all_ja"
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
python -m pytest tests\test_voice_capability_smoke_tool.py tests\test_character_pack.py -q
```

Expected: fail because smoke and bundled packs have not been migrated.

- [ ] **Step 3: Implement smoke support and migrate profiles**

Set all three character packs to:

```json
"provider": "http_emoti_voice"
```

For Xingxi and Nairong use backend `http_qwen3tts`. For Ikaros use backend `http_gptsovits`, `synthesis_language: "all_ja"`, and a small static map for demo lines.

- [ ] **Step 4: Verify profile tests**

Run:

```powershell
python -m pytest tests\test_voice_capability_smoke_tool.py tests\test_character_pack.py -q
python -m json.tool assets\companion\xingxi_pixel_pet\character.json
python -m json.tool assets\companion\ikaros_pixel_pet\character.json
python -m json.tool assets\companion\nairong_pixel_pet\character.json
```

Expected: pass.

## Task 5: Full Verification And Release Impact

**Files:**
- Modify if needed: `docs/e_moti_course_submission_2026-06-23.md`
- Modify if needed: `docs/superpowers/plans/2026-06-23-character-voice-training-integration.md`

- [ ] **Step 1: Focused tests**

Run:

```powershell
python -m pytest tests\test_voice_tts.py tests\test_voice_capability_smoke_tool.py tests\test_character_voice_profile.py tests\test_capability_settings.py tests\test_capability_runtime.py tests\test_voice_provider_catalog.py tests\test_character_pack.py -q
```

Expected: pass.

- [ ] **Step 2: UI tests**

Run:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
```

Expected: pass.

- [ ] **Step 3: Full regression**

Run:

```powershell
python -m pytest
```

Expected: pass.

- [ ] **Step 4: Optional live TTS smoke when services are running**

Run only if `9880` and `9882` are listening:

```powershell
python tools\voice_capability_smoke.py --character-id xingxi_pixel_pet --tts-text "星汐，和导师打个招呼。" --skip-playback --report artifacts\voice-smoke\xingxi-unified-gateway-live.json
python tools\voice_capability_smoke.py --character-id ikaros_pixel_pet --tts-text "我在这里。" --skip-playback --report artifacts\voice-smoke\ikaros-unified-gateway-live.json
python tools\voice_capability_smoke.py --character-id nairong_pixel_pet --tts-text "奶龙，和导师打个招呼。" --skip-playback --report artifacts\voice-smoke\nairong-unified-gateway-live.json
```

Expected: each report has `"ok": true`; Ikaros report should show `provider: "http_emoti_voice"` at the character profile level and backend delegation should produce Japanese synthesis text.

- [ ] **Step 5: Commit**

Run:

```powershell
git status --short --untracked-files=all
git diff --check
git add docs/superpowers/plans/2026-06-24-unified-voice-provider-bilingual-tts.md src/guanghe_companion tests tools assets/companion/*/character.json
git commit -m "feat: unify character voice provider"
```

Expected: no `data/`, `artifacts/`, model weights, API keys, or raw training audio are staged.

## Acceptance Criteria

- The app-facing provider for Xingxi, Ikaros, and Nairong is `http_emoti_voice`.
- The backend route remains per character and is controlled by character profile metadata.
- Ikaros can display a Chinese line while the TTS layer synthesizes a mapped Japanese line.
- No TTS path can mutate growth state, memory, relationship, inventory, goals, or saves.
- Existing Qwen and GPT-SoVITS providers remain independently testable.
- Full regression passes before completion.
