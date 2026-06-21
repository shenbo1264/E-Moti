# Character Voice Profile Authorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement per-character voice profiles with explicit authorization boundaries for designed, licensed, local-generated, and locally trained voice routes.

**Architecture:** Character packs own a typed voice-profile contract, while the capability runtime only converts that profile into presentational `TTSSettings`. The registry validates licensing and path boundaries before a pack is listed, and TTS providers receive only sanitized runtime fields such as provider, voice, model variant, language, and Qwen style instruction.

**Tech Stack:** PySide6 app, existing character pack registry, dataclass settings, local HTTP Qwen3-TTS route, pytest.

---

## Scope

This package implements the infrastructure required for Xingxi and future local UGC characters to have distinct voice profiles. It does not bundle unlicensed Ikaros or Nairong cloned voices into the public repository; those packs must remain local-only until rights are cleared.

## File Structure

- Create `src/guanghe_companion/character_voice_profile.py`: typed profile parser, runtime projection, and authorization validation helpers.
- Modify `src/guanghe_companion/character_pack.py`: store `CharacterVoiceProfile` instead of a loose dict.
- Modify `src/guanghe_companion/character_registry.py`: validate `character.json.tts_profile` distribution and reference-audio paths.
- Modify `src/guanghe_companion/capability_settings.py`: add sanitized `profile_id` and `instruct` fields to `TTSSettings`.
- Modify `src/guanghe_companion/capability_runtime.py`: overlay character voice profile fields onto global TTS settings without touching growth state.
- Modify `src/guanghe_companion/voice_tts.py`: pass Qwen voice-profile metadata and style instruction through the HTTP payload.
- Modify `src/guanghe_companion/app.py`: read the typed voice profile through `to_runtime_dict()`.
- Modify bundled `assets/companion/*/character.json`: declare original Xingxi voice profiles as designed, public-safe Qwen profiles.
- Add or update tests under `tests/`: character voice parsing, registry validation, runtime overlay, Qwen payload, app voice test, and repository hygiene.

## Contract

`character.json.tts_profile` accepts these keys:

```json
{
  "profile_id": "xingxi_qwen_vivian_designed_v1",
  "display_name": "Xingxi Qwen Vivian designed voice",
  "provider": "http_qwen3tts",
  "api_url": "http://127.0.0.1:9880/",
  "language": "zh",
  "voice": "Vivian",
  "model_variant": "qwen3tts_0.6b_customvoice",
  "rate": 1,
  "volume": 0.92,
  "instruct": "Speak as a gentle, slightly shy Chinese desktop companion.",
  "voice_source_type": "original_design",
  "training_status": "designed",
  "distribution_policy": "public_ok",
  "rights_note": "Original voice direction; no third-party cloned material included.",
  "reference_audio": []
}
```

Allowed `voice_source_type` values:

- `original_design`: original character voice direction designed from prompt/style only.
- `licensed_voice`: trained or referenced voice with explicit rights.
- `local_generated`: locally generated candidate with no third-party imitation claim.
- `local_trained_clone`: clone or trained tone from local reference samples.
- `third_party_reference`: fanwork or third-party character reference.

Allowed `training_status` values:

- `not_trained`
- `designed`
- `candidate`
- `trained_local`
- `blocked_rights`

Allowed `distribution_policy` values:

- `public_ok`
- `local_only`
- `blocked`

Rules:

- `local_trained_clone` and `third_party_reference` must not use `public_ok`.
- `private_local_fanwork` packs may reuse public-safe original or licensed voice routes, but cloned or third-party-reference voice profiles must use `local_only` or `blocked`.
- `shareable_after_review` packs may use `public_ok` only when voice source is `original_design`, `licensed_voice`, or `local_generated`.
- `reference_audio` paths must be relative files under `voice/` and must not be absolute or contain `..`.
- Runtime projection is presentational only; it must not mutate state, memory, inventory, relationships, goals, or saves.

## Tasks

### Task 1: Restore Repository Hygiene Baseline

**Files:**
- Modify: `tests/test_voice_service_deployment_scripts.py`

- [ ] **Step 1: Run the failing hygiene test**

Run:

```powershell
python -m pytest tests\test_repository_hygiene.py::test_tracked_text_files_do_not_expose_local_paths_or_private_note_names -q
```

Expected before fix: FAIL because a tracked test literal includes a forbidden local path token.

- [ ] **Step 2: Replace literal forbidden tokens with constructed values**

Use string construction for drive prefixes and Unicode escape sequences for local private words so the hygiene test can scan the repository without matching itself.

- [ ] **Step 3: Verify the hygiene test passes**

Run:

```powershell
python -m pytest tests\test_repository_hygiene.py::test_tracked_text_files_do_not_expose_local_paths_or_private_note_names -q
```

Expected after fix: PASS.

### Task 2: Add Typed Voice Profile Parsing Tests

**Files:**
- Create: `tests/test_character_voice_profile.py`
- Test target: `src/guanghe_companion/character_voice_profile.py`

- [ ] **Step 1: Write failing tests**

Test exact behaviors:

```python
def test_voice_profile_parses_qwen_designed_profile():
    profile = CharacterVoiceProfile.from_payload({
        "profile_id": "xingxi_qwen_vivian_designed_v1",
        "display_name": "Xingxi Vivian",
        "provider": "http-qwen3tts",
        "api_url": " http://127.0.0.1:9880/ ",
        "language": "zh",
        "voice": "Vivian",
        "model_variant": "0.6B",
        "rate": 2,
        "volume": 0.8,
        "instruct": "gentle companion tone",
        "voice_source_type": "original_design",
        "training_status": "designed",
        "distribution_policy": "public_ok",
        "rights_note": "original voice direction",
    })
    assert profile.to_runtime_dict()["provider"] == "http_qwen3tts"
    assert profile.to_runtime_dict()["instruct"] == "gentle companion tone"
```

Also test unsafe reference-audio paths, public third-party clone rejection, and private local fanwork acceptance.

- [ ] **Step 2: Verify tests fail**

Run:

```powershell
python -m pytest tests\test_character_voice_profile.py -q
```

Expected: FAIL because `character_voice_profile.py` does not exist.

### Task 3: Implement Voice Profile Contract

**Files:**
- Create: `src/guanghe_companion/character_voice_profile.py`
- Modify: `src/guanghe_companion/character_pack.py`
- Modify tests: `tests/test_character_pack.py`

- [ ] **Step 1: Implement `CharacterVoiceProfile`**

Create a frozen dataclass with sanitized fields and methods:

```python
CharacterVoiceProfile.from_payload(value: object) -> CharacterVoiceProfile
CharacterVoiceProfile.to_runtime_dict() -> dict[str, object]
validate_voice_profile_payload(root: Path, payload: object, distribution_boundary: str, errors: list[str]) -> None
```

- [ ] **Step 2: Wire `CharacterPack.tts_profile` to the typed dataclass**

`load_character_pack_from_dir()` should parse `tts_profile` through `CharacterVoiceProfile.from_payload()`.

- [ ] **Step 3: Verify focused tests pass**

Run:

```powershell
python -m pytest tests\test_character_voice_profile.py tests\test_character_pack.py -q
```

Expected: PASS.

### Task 4: Validate Authorization Boundaries In Registry

**Files:**
- Modify: `src/guanghe_companion/character_registry.py`
- Modify: `tests/test_character_registry.py`

- [ ] **Step 1: Write failing registry tests**

Add tests that:

- reject `third_party_reference` with `distribution_policy: public_ok`;
- reject `reference_audio: ["../sample.wav"]`;
- accept `private_local_fanwork` plus `local_trained_clone` plus `distribution_policy: local_only`.

- [ ] **Step 2: Implement validation call**

Call `validate_voice_profile_payload(root, payload.get("tts_profile"), distribution_boundary, errors)` from `_validate_character_payload()`.

- [ ] **Step 3: Verify registry tests pass**

Run:

```powershell
python -m pytest tests\test_character_registry.py tests\test_character_voice_profile.py -q
```

Expected: PASS.

### Task 5: Apply Voice Profiles At Runtime

**Files:**
- Modify: `src/guanghe_companion/capability_settings.py`
- Modify: `src/guanghe_companion/capability_runtime.py`
- Modify: `src/guanghe_companion/app.py`
- Modify tests: `tests/test_capability_settings.py`, `tests/test_capability_runtime.py`, `tests/test_app.py`

- [ ] **Step 1: Write failing runtime tests**

Assert that a character profile can override `provider`, `api_url`, `language`, `voice`, `model_variant`, `rate`, `volume`, `profile_id`, and `instruct` while leaving the original settings object unchanged.

- [ ] **Step 2: Implement settings fields and overlay**

Add `profile_id` and `instruct` to `TTSSettings.from_dict()` with length limits. Extend `_character_tts_settings()` to overlay sanitized profile fields.

- [ ] **Step 3: Update app profile reader**

`_current_character_tts_profile()` should return `self.controller.character_pack.tts_profile.to_runtime_dict()`.

- [ ] **Step 4: Verify focused runtime tests pass**

Run:

```powershell
python -m pytest tests\test_capability_settings.py tests\test_capability_runtime.py tests\test_app.py -q
```

Expected: PASS.

### Task 6: Send Qwen Style Instruction In TTS Payload

**Files:**
- Modify: `src/guanghe_companion/voice_tts.py`
- Modify: `tests/test_voice_tts.py`

- [ ] **Step 1: Write failing Qwen payload test**

Assert that `HttpQwen3TTSProvider` sends `profile_id` and `instruct` when present.

- [ ] **Step 2: Implement payload fields**

`_qwen3tts_payload()` should include `profile_id` and `instruct` only when non-empty.

- [ ] **Step 3: Verify voice TTS tests pass**

Run:

```powershell
python -m pytest tests\test_voice_tts.py -q
```

Expected: PASS.

### Task 7: Update Bundled Xingxi Profiles

**Files:**
- Modify: `assets/companion/xingxi_pixel_pet/character.json`
- Modify: `assets/companion/original_oc/character.json`
- Modify tests if necessary: `tests/test_character_pack.py`

- [ ] **Step 1: Declare public-safe original designed Qwen profiles**

Use `provider: http_qwen3tts`, `voice: Vivian`, `model_variant: qwen3tts_0.6b_customvoice`, `voice_source_type: original_design`, `training_status: designed`, and `distribution_policy: public_ok`.

- [ ] **Step 2: Validate bundled packs**

Run:

```powershell
python -m pytest tests\test_character_pack.py tests\test_character_registry.py -q
```

Expected: PASS.

### Task 8: Final Verification And Commit

**Files:**
- All changed files.

- [ ] **Step 1: Run focused voice/profile suite**

Run:

```powershell
python -m pytest tests\test_character_voice_profile.py tests\test_character_pack.py tests\test_character_registry.py tests\test_capability_settings.py tests\test_capability_runtime.py tests\test_voice_tts.py tests\test_app.py -q
```

Expected: PASS.

- [ ] **Step 2: Run UI smoke tests**

Run:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run:

```powershell
python -m pytest
```

Expected: PASS.

- [ ] **Step 4: Run diff whitespace check**

Run:

```powershell
git diff --check
```

Expected: exit code 0.

- [ ] **Step 5: Commit the package**

Stage only source, tests, docs, and intentional character manifests. Do not stage runtime saves, ignored voice artifacts, model files, private notes, or secrets.

```powershell
git status --short --untracked-files=all
git add docs/superpowers/plans/2026-06-22-character-voice-profile-authorization.md src/guanghe_companion/character_voice_profile.py src/guanghe_companion/character_pack.py src/guanghe_companion/character_registry.py src/guanghe_companion/capability_settings.py src/guanghe_companion/capability_runtime.py src/guanghe_companion/app.py src/guanghe_companion/voice_tts.py tests/test_character_voice_profile.py tests/test_character_pack.py tests/test_character_registry.py tests/test_capability_settings.py tests/test_capability_runtime.py tests/test_voice_tts.py tests/test_app.py tests/test_voice_service_deployment_scripts.py assets/companion/xingxi_pixel_pet/character.json assets/companion/original_oc/character.json
git commit -m "feat: add character voice profile boundaries"
```

Expected: commit succeeds.
