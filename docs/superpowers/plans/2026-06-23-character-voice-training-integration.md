# Character Voice Training And Integration Plan

Date: 2026-06-23

## Current Verified State

- The repository has per-character `tts_profile` metadata and working local Qwen3-TTS preset synthesis.
- `xingxi_pixel_pet`, `ikaros_pixel_pet`, and `nairong_pixel_pet` currently use Qwen preset speakers plus character-specific instruction text.
- No `.wav`, `.mp3`, `.flac`, `.ogg`, or `.m4a` reference audio is present in the repository, so no character has been trained or cloned from real reference audio yet.
- The project now supports passing character reference audio and reference text through the runtime TTS path into the local Qwen HTTP service.

## External Route Check

Primary route:

- Qwen3-TTS Base is the best first route for this project because the current repo already runs `qwen-tts`, and the Base model supports rapid voice cloning from user-provided audio input. The official model card documents `generate_voice_clone(text, language, ref_audio, ref_text)` and says the Base checkpoint is intended for rapid voice cloning from input audio.
- Qwen3-TTS CustomVoice remains the fallback for designed voices and course-preview stability. It supports preset speakers and natural-language style instructions, but it is not a real reference-audio cloning path.

Secondary route:

- GPT-SoVITS is the practical follow-up when one-shot cloning is not close enough. Its README states that it can do zero-shot TTS from a 5-second vocal sample and few-shot fine-tuning from about 1 minute of training data. It also includes WebUI tools for segmentation, ASR, and labeling, which helps with messy character-source audio.

Alternative route:

- CosyVoice is a strong later candidate for production-quality zero-shot multilingual cloning and streaming. It is a broader stack, so it should not replace the current Qwen route until the Qwen path is measured with real samples.
- F5-TTS remains worth testing if Qwen/GPT-SoVITS quality is not enough, but it should not be introduced before the project has a stable voice-pack contract.

Sources:

- Qwen3-TTS Base model card: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base
- Qwen3-TTS CustomVoice model card: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
- GPT-SoVITS: https://github.com/RVC-Boss/GPT-SoVITS
- CosyVoice: https://github.com/FunAudioLLM/CosyVoice
- F5-TTS: https://github.com/SWivid/F5-TTS

## Voice Pack Contract

For bundled character packs or local UGC packs:

```text
<character_pack>/
  character.json
  voice/
    reference.wav
    provenance.md
    qa_report.json
```

`character.json` uses:

```json
{
  "tts_profile": {
    "provider": "http_qwen3tts",
    "model_variant": "qwen3tts_0.6b_base",
    "voice_source_type": "local_trained_clone",
    "training_status": "trained_local",
    "distribution_policy": "local_only",
    "reference_audio": ["voice/reference.wav"],
    "reference_text": "Reference transcript matching reference.wav."
  }
}
```

Runtime behavior:

- `reference_audio` is resolved relative to the character pack directory.
- `reference_text` is forwarded with the reference audio.
- If reference audio is present, the Qwen local service calls `generate_voice_clone`.
- If reference audio is absent, the service keeps the existing `generate_voice_design` or `generate_custom_voice` path.
- TTS remains output-only and only consumes validated companion speech.

## Reference Audio Preparation

Minimum for Qwen Base zero-shot:

- 3-10 seconds of clean single-speaker audio.
- Manual transcript matching the audio as closely as possible.
- Prefer WAV, mono or stereo, no background music, no overlapping voices.

Better for GPT-SoVITS few-shot:

- 1-3 minutes of clean single-speaker audio.
- Split into short clips.
- Transcript or ASR-generated labels reviewed by hand.
- Use GPT-SoVITS WebUI tools for segmentation and labeling when raw source audio is messy.

Recommended character order:

1. Xingxi: original voice design stays on Qwen CustomVoice unless a new original reference recording is created.
2. Nairong: test Qwen Base with 1-2 short expressive references first because the target voice is goofy and less language-heavy.
3. Ikaros: test Qwen Base, then GPT-SoVITS if similarity and calm prosody are not good enough.

## Commands

Install or refresh local Qwen service:

```powershell
powershell -ExecutionPolicy Bypass -File tools\voice_services\start_qwen3_tts_server.ps1 -InstallOnly
```

Run Qwen Base clone service:

```powershell
powershell -ExecutionPolicy Bypass -File tools\voice_services\start_qwen3_tts_server.ps1 -Model Qwen/Qwen3-TTS-12Hz-0.6B-Base -Port 9880
```

Smoke-test a character:

```powershell
python tools\voice_capability_smoke.py --character-id nairong_pixel_pet --tts-text "今天就陪我发会儿呆吧。" --skip-playback --report artifacts\voice-smoke\nairong-qwen-base.json
```

Expected report fields:

```json
{
  "tts": {
    "ok": true,
    "provider": "http_qwen3tts",
    "model_variant": "qwen3tts_0.6b_base",
    "reference_audio_count": 1,
    "reference_text_present": true
  }
}
```

## Acceptance Gate

For the first real cloned voice package:

1. Add only the local character voice reference files needed for the preview package.
2. Run character pack validation.
3. Start Qwen Base service.
4. Run `voice_capability_smoke.py` for all three characters.
5. Listen to at least three lines per character: greeting, emotional reaction, and short idle line.
6. Run focused tests:

```powershell
python -m pytest tests\test_character_voice_profile.py tests\test_character_pack.py tests\test_capability_runtime.py tests\test_voice_tts.py tests\test_qwen3_tts_local_server.py tests\test_voice_capability_smoke_tool.py -q
```

7. Run full regression:

```powershell
python -m pytest
```

## Remaining Dependency

Actual voice cloning cannot be completed until reference audio and matching transcript are available. The code path is ready to consume them, but the repo currently contains no usable reference audio.
