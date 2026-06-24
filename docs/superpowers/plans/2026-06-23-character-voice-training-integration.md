# Character Voice Training And Integration Plan

Date: 2026-06-23

## Current Verified State

- The repository has per-character `tts_profile` metadata and working local Qwen3-TTS / GPT-SoVITS synthesis routes.
- `xingxi_pixel_pet`, `ikaros_pixel_pet`, and `nairong_pixel_pet` now use the unified app-facing `http_emoti_voice` provider.
- The unified provider delegates per character: Xingxi and Nairong currently use Qwen3TTS backends; Ikaros uses GPT-SoVITS backend profile `ikaros_pixel_pet_gptsovits_curated160_e4_v1`.
- The Ikaros role package includes `assets/companion/ikaros_pixel_pet/voice/reference_generated.wav` plus matching Japanese `reference_text`.
- The runtime TTS path now supports both Qwen-style reference cloning and GPT-SoVITS root-endpoint synthesis behind the same app-facing provider.
- Ikaros supports first-pass Chinese display / Japanese synthesis through a validated speech-to-synthesis text map in the TTS layer.
- The command-line voice smoke tool supports `--tts-text-file`, so Japanese/Chinese smoke text can be read as UTF-8 instead of relying on Windows shell argument encoding.

## 2026-06-24 Ikaros Training Record

Training source:

- Source folder: `%IKAROS_SOURCE_DIR%` (local user-provided Ikaros audio folder).
- Probe result: 642 WAV files, 22050 Hz mono, about 2255.95 seconds total, median clip length about 3.379 seconds.
- ASR labels were generated locally with faster-whisper and converted into GPT-SoVITS list format.
- ASCII training workspace: `E:\E_Moti_voice`, used because `pyopenjtalk` and related Japanese text tooling failed under the Chinese project path.

Environment:

- GPT-SoVITS checkout: `E:\E_Moti_voice\GPT-SoVITS`.
- Venv: `E:\E_Moti_voice\gptsovits-venv`.
- GPU: RTX 5060, CUDA path verified through PyTorch.
- Required Windows training patches were applied only to the local GPT-SoVITS checkout: single-GPU/Windows DataLoader settings, Lightning checkpoint access, and an API `librosa.load` fallback for `torchaudio`/`torchcodec` on Windows.

Training outputs:

```text
E:\E_Moti_voice\GPT-SoVITS\SoVITS_weights_v2\ikaros_full642_v2_e3_s1926.pth
E:\E_Moti_voice\GPT-SoVITS\GPT_weights_v2\ikaros_curated160_v2-e4.ckpt
```

Selection rationale:

- SoVITS voice/acoustic side was trained on the full 642-file dataset for 3 epochs and exported as `ikaros_full642_v2_e3_s1926.pth`.
- Full 642-file GPT semantic training completed, but e1/e2/e3 produced frequent early-EOS behavior in practical synthesis, with medium lines often collapsing to about 0.94 seconds.
- A 160-line curated Japanese subset was selected from the same source using duration, text length, and Japanese-character-ratio filters. This subset is about 593.7 seconds.
- Curated160 GPT training reached top_3_acc_epoch about 0.832 at epoch 5. A/B smoke chose e4 because it produced stable short and medium line durations while keeping the calm Ikaros-like delivery.
- Provider sampling was tightened to `temperature=0.35`, `top_p=0.7`, `top_k=15`, and `rate=-1` maps to `speed=0.9`.

Live smoke evidence:

```text
artifacts\voice-smoke\ikaros-character-profile-gptsovits-short-file-live.json
artifacts\voice-smoke\ikaros-character-profile-gptsovits-short-file-live.wav
artifacts\voice-smoke\ikaros-character-profile-gptsovits-medium-file-live.json
artifacts\voice-smoke\ikaros-character-profile-gptsovits-medium-file-live.wav
```

Verified results:

- Short line via `ikaros_pixel_pet` character profile: app provider `http_emoti_voice`, backend provider `http_gptsovits`, 32000 Hz mono WAV, about 2.48 seconds.
- Medium line via `ikaros_pixel_pet` character profile: app provider `http_emoti_voice`, backend provider `http_gptsovits`, 32000 Hz mono WAV, about 6.66 seconds.
- Header-only 44-byte WAV responses are now rejected by the provider instead of reported as successful speech.

Start the local Ikaros GPT-SoVITS service:

```powershell
powershell -ExecutionPolicy Bypass -File tools\voice_services\start_ikaros_gptsovits_server.ps1 -NoWait
```

Smoke-test through the character pack:

```powershell
python tools\voice_capability_smoke.py --character-id ikaros_pixel_pet --tts-text-file artifacts\voice-smoke\ikaros_short_ja.txt --skip-playback --report artifacts\voice-smoke\ikaros-character-profile-gptsovits-short-file-live.json
python tools\voice_capability_smoke.py --character-id ikaros_pixel_pet --tts-text-file artifacts\voice-smoke\ikaros_medium_ja.txt --skip-playback --report artifacts\voice-smoke\ikaros-character-profile-gptsovits-medium-file-live.json
```

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

The Ikaros voice is trained and connected for the local course submission environment. Remaining voice work is now product hardening rather than basic feasibility:

- Package or document the external GPT-SoVITS runtime bundle cleanly, because the 85 MB SoVITS weight, 155 MB GPT weight, and GPT-SoVITS dependency tree are not committed into the Git repository.
- Run human listening QA for at least greeting, idle, comfort, and confused/shy lines.
- Apply the same voice-training workflow to Nairong if a more accurate local voice is required before the final presentation.
