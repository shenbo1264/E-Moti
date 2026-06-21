# Voice Foundation Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade E-Moti voice capability from a demo-only TTS/ASR channel into a low-coupling, character-aware voice foundation that can use Edge TTS for preview, Qwen3-TTS for formal character voice, and FunASR/SenseVoice or Qwen3-ASR for speech input without breaking companion state boundaries.

**Architecture:** Keep voice as a capability layer below the PySide6 UI and above provider adapters. TTS consumes only validated companion speech; ASR produces only player text through `DialogueRequest`; provider catalogs and diagnostics are separated from growth state, save data, character memory, and renderer adapters.

**Tech Stack:** Python 3.11, PySide6, existing typed settings/runtime contracts, `edge-tts` preview provider, HTTP/OpenAI-compatible adapters for Qwen3-TTS and ASR services, pytest, existing Windows packaging scripts.

---

## Current Evidence

Verified in `D:\学工文档\光核\电子宠物\E-Moti_demo\.worktrees\final-package-qa` on 2026-06-21:

- Branch: `codex/final-package-qa`
- Baseline commit: `48779fb feat: package character-aware voice preview`
- Working tree before this plan: clean
- Full suite: `python -m pytest` -> `900 passed`

Existing implementation facts:

- `src/guanghe_companion/voice_tts.py` already has `TTSManager`, `HttpQwen3TTSProvider`, `WindowsSapiTTSProvider`, and `EdgeNeuralTTSProvider`.
- `src/guanghe_companion/voice_asr.py` already has `ASRService`, `QtAudioWavRecorder`, `OpenAICompatibleASRTranscriber`, and `VoskASRTranscriber`.
- `src/guanghe_companion/capability_runtime.py` already keeps ASR output as `DialogueRequest(source="asr")`.
- `src/guanghe_companion/capability_panels.py` still hardcodes provider combo values and does not expose `edge_tts`, FunASR, SenseVoice, or Qwen3-ASR presets clearly.
- Some voice status strings in `voice_tts.py`, `voice_asr.py`, and `capability_panels.py` are mojibake in current files and should be repaired as part of the voice package.

## External Route References

- Qwen3-TTS official project: https://github.com/QwenLM/Qwen3-TTS
- Qwen3-ASR official project: https://github.com/QwenLM/Qwen3-ASR
- FunASR official docs: https://modelscope.github.io/FunASR/
- SenseVoice official project: https://github.com/FunAudioLLM/SenseVoice
- CosyVoice official project: https://github.com/FunAudioLLM/CosyVoice
- GPT-SoVITS official project: https://github.com/RVC-Boss/GPT-SoVITS
- edge-tts package: https://pypi.org/project/edge-tts/

Route decision:

- Preview default: `edge_tts`, because it is already packaged and live-smoked for three roles.
- Formal TTS route: Qwen3-TTS via HTTP/local-service adapter, not in-process model loading.
- Voice cloning research route: GPT-SoVITS or CosyVoice behind an explicit local-service preset; do not distribute cloned fanwork voices.
- ASR first implementation route: FunASR/SenseVoice through the existing OpenAI-compatible transcription adapter.
- ASR high-quality follow-up route: Qwen3-ASR through the same adapter shape when a local server or gateway is available.

## Decoupling Principles

1. `capability_settings.py` owns normalized settings only; it should not know UI labels or diagnostic prose.
2. `voice_provider_catalog.py` should own provider options, recommended presets, labels, default endpoints, and documentation hints.
3. `voice_tts.py` and `voice_asr.py` should own provider execution only; they should not own UI options.
4. `capability_panels.py` should render provider choices from the catalog and collect settings, not define route strategy.
5. `capability_runtime.py` remains the only bridge from UI actions to capability services.
6. TTS cannot mutate state. ASR cannot mutate state. ASR auto-send can only return `DialogueRequest`.
7. Heavy model services stay outside the frozen app unless a separate packaging package explicitly vendors them.

## File Structure

- Create: `src/guanghe_companion/voice_provider_catalog.py`
  - Provider option dataclasses.
  - TTS provider list: `edge_tts`, `http_qwen3tts`, `windows_sapi`.
  - ASR provider list: `openai_compatible`, `funasr_openai`, `sensevoice_openai`, `qwen3_asr_openai`, `vosk`.
  - Helper functions for combo values, default models, default local endpoints, and public route notes.
- Modify: `src/guanghe_companion/capability_settings.py`
  - Accept new provider aliases while preserving a stable canonical provider id.
  - Keep secret redaction.
- Modify: `src/guanghe_companion/capability_panels.py`
  - Populate TTS/ASR provider combos from `voice_provider_catalog.py`.
  - Repair Chinese UI text in the voice and capability settings panels touched by this package.
- Modify: `src/guanghe_companion/voice_tts.py`
  - Repair Chinese result messages.
  - Treat Qwen3-TTS as a named HTTP/local-service route without changing current HTTP payload compatibility.
- Modify: `src/guanghe_companion/voice_asr.py`
  - Repair Chinese result messages.
  - Route `funasr_openai`, `sensevoice_openai`, and `qwen3_asr_openai` through `OpenAICompatibleASRTranscriber`.
- Create: `tools/voice_capability_smoke.py`
  - A CLI smoke tool that can test TTS synthesis without playback and ASR transcription from a WAV file.
  - Writes JSON report under ignored `artifacts/voice-smoke/`.
- Modify: `.gitignore`
  - Ignore `artifacts/voice-smoke/`.
- Modify tests:
  - `tests/test_voice_provider_catalog.py`
  - `tests/test_capability_settings.py`
  - `tests/test_capability_panels.py`
  - `tests/test_voice_tts.py`
  - `tests/test_voice_asr.py`
  - `tests/test_voice_capability_smoke_tool.py`
  - `tests/test_windows_packaging_scripts.py`

## Task 1: Provider Catalog And Settings Aliases

**Files:**
- Create: `src/guanghe_companion/voice_provider_catalog.py`
- Modify: `src/guanghe_companion/capability_settings.py`
- Test: `tests/test_voice_provider_catalog.py`
- Test: `tests/test_capability_settings.py`

- [ ] **Step 1: Write failing catalog tests**

Add `tests/test_voice_provider_catalog.py`:

```python
from __future__ import annotations


def test_voice_provider_catalog_exposes_formal_and_preview_tts_routes() -> None:
    from guanghe_companion.voice_provider_catalog import tts_provider_ids, tts_provider_option

    assert tts_provider_ids() == ("edge_tts", "http_qwen3tts", "windows_sapi")
    assert tts_provider_option("edge_tts").label == "Edge Neural TTS"
    assert tts_provider_option("http_qwen3tts").recommended_use == "formal_character_voice"
    assert tts_provider_option("http_qwen3tts").default_model == "qwen3tts_1.6b"


def test_voice_provider_catalog_exposes_openai_compatible_asr_routes() -> None:
    from guanghe_companion.voice_provider_catalog import asr_provider_ids, asr_provider_option

    assert asr_provider_ids() == (
        "openai_compatible",
        "funasr_openai",
        "sensevoice_openai",
        "qwen3_asr_openai",
        "vosk",
    )
    assert asr_provider_option("funasr_openai").transcriber_family == "openai_compatible"
    assert asr_provider_option("sensevoice_openai").default_model == "iic/SenseVoiceSmall"
    assert asr_provider_option("qwen3_asr_openai").recommended_use == "high_quality_asr"
```

Extend `tests/test_capability_settings.py`:

```python
def test_capability_settings_accepts_voice_route_aliases() -> None:
    from guanghe_companion.capability_settings import ASRSettings, TTSSettings

    assert TTSSettings.from_dict({"provider": "edge"}).provider == "edge_tts"
    assert TTSSettings.from_dict({"provider": "qwen3_tts"}).provider == "http_qwen3tts"
    assert ASRSettings.from_dict({"provider": "funasr"}).provider == "funasr_openai"
    assert ASRSettings.from_dict({"provider": "sensevoice"}).provider == "sensevoice_openai"
    assert ASRSettings.from_dict({"provider": "qwen3_asr"}).provider == "qwen3_asr_openai"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests\test_voice_provider_catalog.py tests\test_capability_settings.py -q
```

Expected:

- `ModuleNotFoundError` for `voice_provider_catalog`.
- Alias assertions fail until `capability_settings.py` is updated.

- [ ] **Step 3: Implement catalog**

Create `src/guanghe_companion/voice_provider_catalog.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TTSProviderOption:
    provider_id: str
    label: str
    recommended_use: str
    default_model: str
    default_api_url: str
    route_note: str


@dataclass(frozen=True, slots=True)
class ASRProviderOption:
    provider_id: str
    label: str
    transcriber_family: str
    recommended_use: str
    default_model: str
    default_base_url: str
    route_note: str


TTS_PROVIDER_OPTIONS: tuple[TTSProviderOption, ...] = (
    TTSProviderOption(
        provider_id="edge_tts",
        label="Edge Neural TTS",
        recommended_use="private_preview",
        default_model="",
        default_api_url="",
        route_note="Zero-key online preview voice; keep as demo fallback.",
    ),
    TTSProviderOption(
        provider_id="http_qwen3tts",
        label="Qwen3-TTS HTTP",
        recommended_use="formal_character_voice",
        default_model="qwen3tts_1.6b",
        default_api_url="http://127.0.0.1:9880/",
        route_note="Formal route for original character voice through a local HTTP service.",
    ),
    TTSProviderOption(
        provider_id="windows_sapi",
        label="Windows SAPI",
        recommended_use="offline_fallback",
        default_model="",
        default_api_url="",
        route_note="Windows built-in fallback; limited character expressiveness.",
    ),
)

ASR_PROVIDER_OPTIONS: tuple[ASRProviderOption, ...] = (
    ASRProviderOption(
        provider_id="openai_compatible",
        label="OpenAI-compatible ASR",
        transcriber_family="openai_compatible",
        recommended_use="generic_cloud_or_local",
        default_model="whisper-1",
        default_base_url="",
        route_note="Generic transcription endpoint adapter.",
    ),
    ASRProviderOption(
        provider_id="funasr_openai",
        label="FunASR OpenAI-compatible",
        transcriber_family="openai_compatible",
        recommended_use="local_asr_first",
        default_model="paraformer-zh",
        default_base_url="http://127.0.0.1:10095/v1",
        route_note="Low-coupling first local ASR route; reuse existing multipart transcription adapter.",
    ),
    ASRProviderOption(
        provider_id="sensevoice_openai",
        label="SenseVoice OpenAI-compatible",
        transcriber_family="openai_compatible",
        recommended_use="emotion_aware_asr",
        default_model="iic/SenseVoiceSmall",
        default_base_url="http://127.0.0.1:10095/v1",
        route_note="ASR route with emotion/language/event potential; transcript still enters only as player text.",
    ),
    ASRProviderOption(
        provider_id="qwen3_asr_openai",
        label="Qwen3-ASR OpenAI-compatible",
        transcriber_family="openai_compatible",
        recommended_use="high_quality_asr",
        default_model="qwen3-asr",
        default_base_url="http://127.0.0.1:10096/v1",
        route_note="Higher-quality follow-up route when a local gateway is available.",
    ),
    ASRProviderOption(
        provider_id="vosk",
        label="Vosk offline",
        transcriber_family="vosk",
        recommended_use="offline_fallback",
        default_model="",
        default_base_url="",
        route_note="Offline fallback; requires local model path.",
    ),
)


def tts_provider_ids() -> tuple[str, ...]:
    return tuple(option.provider_id for option in TTS_PROVIDER_OPTIONS)


def asr_provider_ids() -> tuple[str, ...]:
    return tuple(option.provider_id for option in ASR_PROVIDER_OPTIONS)


def tts_provider_option(provider_id: str) -> TTSProviderOption:
    for option in TTS_PROVIDER_OPTIONS:
        if option.provider_id == provider_id:
            return option
    return TTS_PROVIDER_OPTIONS[0]


def asr_provider_option(provider_id: str) -> ASRProviderOption:
    for option in ASR_PROVIDER_OPTIONS:
        if option.provider_id == provider_id:
            return option
    return ASR_PROVIDER_OPTIONS[0]
```

Modify `src/guanghe_companion/capability_settings.py` aliases:

```python
TTS_PROVIDER_ALIASES = {
    "windows_sapi": "windows_sapi",
    "sapi": "windows_sapi",
    "edge": "edge_tts",
    "edge_tts": "edge_tts",
    "edge_neural": "edge_tts",
    "http_qwen3tts": "http_qwen3tts",
    "qwen3tts": "http_qwen3tts",
    "qwen3_tts": "http_qwen3tts",
}

ASR_PROVIDER_ALIASES = {
    "openai": "openai_compatible",
    "openai_compatible": "openai_compatible",
    "whisper": "openai_compatible",
    "funasr": "funasr_openai",
    "funasr_openai": "funasr_openai",
    "sensevoice": "sensevoice_openai",
    "sensevoice_openai": "sensevoice_openai",
    "qwen3_asr": "qwen3_asr_openai",
    "qwen3_asr_openai": "qwen3_asr_openai",
    "vosk": "vosk",
}
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
python -m pytest tests\test_voice_provider_catalog.py tests\test_capability_settings.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src\guanghe_companion\voice_provider_catalog.py src\guanghe_companion\capability_settings.py tests\test_voice_provider_catalog.py tests\test_capability_settings.py
git commit -m "feat: catalog voice provider routes"
```

## Task 2: Voice UI Uses Catalog

**Files:**
- Modify: `src/guanghe_companion/capability_panels.py`
- Test: `tests/test_capability_panels.py`

- [ ] **Step 1: Write failing UI tests**

Extend `tests/test_capability_panels.py`:

```python
def test_voice_settings_panel_uses_catalog_provider_choices(qtbot) -> None:
    from guanghe_companion.capability_panels import VoiceSettingsPanel

    panel = VoiceSettingsPanel()
    qtbot.addWidget(panel)

    tts_values = [panel.tts_provider_combo.itemText(index) for index in range(panel.tts_provider_combo.count())]
    asr_values = [panel.asr_provider_combo.itemText(index) for index in range(panel.asr_provider_combo.count())]

    assert tts_values == ["edge_tts", "http_qwen3tts", "windows_sapi"]
    assert asr_values == [
        "openai_compatible",
        "funasr_openai",
        "sensevoice_openai",
        "qwen3_asr_openai",
        "vosk",
    ]
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
python -m pytest tests\test_capability_panels.py::test_voice_settings_panel_uses_catalog_provider_choices -q
```

Expected: fails because `edge_tts`, `funasr_openai`, `sensevoice_openai`, and `qwen3_asr_openai` are not in the combo lists.

- [ ] **Step 3: Implement catalog-backed combo values**

In `src/guanghe_companion/capability_panels.py`, import:

```python
from .voice_provider_catalog import asr_provider_ids, tts_provider_ids
```

Change the combo setup:

```python
self.tts_provider_combo.addItems(list(tts_provider_ids()))
...
self.asr_provider_combo.addItems(list(asr_provider_ids()))
```

- [ ] **Step 4: Run UI panel tests**

Run:

```powershell
python -m pytest tests\test_capability_panels.py tests\test_app.py::test_voice_settings_page_marks_tts_and_asr_disabled -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\guanghe_companion\capability_panels.py tests\test_capability_panels.py
git commit -m "feat: expose voice provider routes in settings UI"
```

## Task 3: Repair Voice Message Text

**Files:**
- Modify: `src/guanghe_companion/voice_tts.py`
- Modify: `src/guanghe_companion/voice_asr.py`
- Modify: `src/guanghe_companion/capability_panels.py`
- Test: `tests/test_voice_tts.py`
- Test: `tests/test_voice_asr.py`

- [ ] **Step 1: Write failing Chinese-message tests**

Update existing tests in `tests/test_voice_tts.py` and `tests/test_voice_asr.py` so they assert readable Chinese messages:

```python
assert disabled.message == "TTS 未启用"
assert empty.message == "没有可朗读文本"
assert "edge-tts 朗读失败" in result.message
```

```python
assert disabled.message == "ASR 未启用"
assert missing_recording.message == "尚未开始录音"
assert started.message == "录音中"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests\test_voice_tts.py tests\test_voice_asr.py -q
```

Expected: fails because current messages are mojibake.

- [ ] **Step 3: Replace touched voice messages with UTF-8 Chinese**

Use exact messages:

```python
TTSResult(False, "TTS 未启用")
TTSResult(False, "没有可朗读文本")
TTSResult(False, f"TTS provider 不可用：{settings.provider}")
TTSResult(False, "HTTP TTS 未返回音频")
TTSResult(True, "朗读完成", str(output))
TTSResult(False, f"HTTP TTS 失败：{exc}")
TTSResult(True, "朗读已开始")
TTSResult(False, f"Windows SAPI TTS 失败：{exc}")
TTSResult(False, "edge-tts 未安装，无法使用在线神经语音")
TTSResult(False, "edge-tts provider 返回无效合成器")
TTSResult(False, f"edge-tts 朗读失败：{exc}")
TTSResult(True, "已停止朗读")
```

Use exact ASR messages:

```python
ASRResult(False, "ASR 未启用")
ASRResult(False, "录音依赖未安装或不可用")
ASRResult(False, f"录音失败：{exc}")
ASRResult(True, "录音中")
ASRResult(False, "尚未开始录音")
ASRResult(False, "录音为空")
ASRResult(False, f"ASR 识别失败：{exc}")
ASRResult(False, "ASR provider 返回无效结果")
ASRResult(False, "没有可用麦克风")
ASRResult(False, "麦克风不支持 16kHz/16-bit mono 录音")
ASRResult(False, "缺少 ASR Base URL 或 API Key")
ASRResult(False, f"ASR 请求失败：{exc}")
ASRResult(False, "ASR 未返回文本")
ASRResult(True, "识别完成", text)
ASRResult(False, "Vosk 模型路径不存在")
ASRResult(False, "vosk 未安装")
ASRResult(False, f"Vosk 识别失败：{exc}")
ASRResult(False, "Vosk 未返回文本")
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests\test_voice_tts.py tests\test_voice_asr.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\guanghe_companion\voice_tts.py src\guanghe_companion\voice_asr.py src\guanghe_companion\capability_panels.py tests\test_voice_tts.py tests\test_voice_asr.py
git commit -m "fix: repair voice capability messages"
```

## Task 4: ASR Provider Routing For FunASR, SenseVoice, And Qwen3-ASR

**Files:**
- Modify: `src/guanghe_companion/voice_asr.py`
- Test: `tests/test_voice_asr.py`

- [ ] **Step 1: Write failing routing test**

Add to `tests/test_voice_asr.py`:

```python
def test_default_asr_transcriber_routes_named_openai_compatible_services() -> None:
    from guanghe_companion.voice_asr import OpenAICompatibleASRTranscriber, default_asr_transcriber

    assert isinstance(default_asr_transcriber("openai_compatible"), OpenAICompatibleASRTranscriber)
    assert isinstance(default_asr_transcriber("funasr_openai"), OpenAICompatibleASRTranscriber)
    assert isinstance(default_asr_transcriber("sensevoice_openai"), OpenAICompatibleASRTranscriber)
    assert isinstance(default_asr_transcriber("qwen3_asr_openai"), OpenAICompatibleASRTranscriber)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
python -m pytest tests\test_voice_asr.py::test_default_asr_transcriber_routes_named_openai_compatible_services -q
```

Expected: fails until explicit named routes are handled.

- [ ] **Step 3: Implement routing**

In `src/guanghe_companion/voice_asr.py`:

```python
OPENAI_COMPATIBLE_ASR_PROVIDERS = {
    "openai_compatible",
    "funasr_openai",
    "sensevoice_openai",
    "qwen3_asr_openai",
}


def default_asr_transcriber(provider: str) -> ASRTranscriber:
    if provider == "vosk":
        return VoskASRTranscriber()
    if provider in OPENAI_COMPATIBLE_ASR_PROVIDERS:
        return OpenAICompatibleASRTranscriber()
    return OpenAICompatibleASRTranscriber()
```

- [ ] **Step 4: Run ASR tests**

Run:

```powershell
python -m pytest tests\test_voice_asr.py tests\test_capability_settings.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\guanghe_companion\voice_asr.py tests\test_voice_asr.py
git commit -m "feat: route named asr services"
```

## Task 5: Voice Capability Smoke Tool

**Files:**
- Create: `tools/voice_capability_smoke.py`
- Modify: `.gitignore`
- Test: `tests/test_voice_capability_smoke_tool.py`

- [ ] **Step 1: Write failing smoke-tool tests**

Create `tests/test_voice_capability_smoke_tool.py`:

```python
from __future__ import annotations

import json


def test_voice_smoke_tool_writes_tts_report_without_playback(tmp_path, monkeypatch) -> None:
    from tools import voice_capability_smoke
    from guanghe_companion.voice_tts import TTSResult

    calls = []

    class FakeProvider:
        def speak(self, text, settings):
            calls.append((text, settings.provider, settings.voice))
            return TTSResult(True, "朗读完成", str(tmp_path / "out.mp3"))

        def stop(self):
            pass

    monkeypatch.setattr(
        voice_capability_smoke,
        "default_tts_provider_factory",
        lambda provider: FakeProvider(),
    )
    report = tmp_path / "report.json"

    code = voice_capability_smoke.main([
        "--tts-provider",
        "edge_tts",
        "--tts-text",
        "星汐语音测试",
        "--tts-voice",
        "zh-CN-XiaoxiaoNeural",
        "--report",
        str(report),
    ])

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["tts"]["ok"] is True
    assert calls == [("星汐语音测试", "edge_tts", "zh-CN-XiaoxiaoNeural")]


def test_voice_smoke_tool_writes_asr_report_from_audio_file(tmp_path, monkeypatch) -> None:
    from tools import voice_capability_smoke
    from guanghe_companion.voice_asr import ASRResult

    audio = tmp_path / "speech.wav"
    audio.write_bytes(b"wav")
    report = tmp_path / "report.json"

    class FakeTranscriber:
        def transcribe(self, audio_bytes, settings):
            assert audio_bytes == b"wav"
            assert settings.provider == "funasr_openai"
            return ASRResult(True, "识别完成", "你好星汐")

    monkeypatch.setattr(voice_capability_smoke, "default_asr_transcriber", lambda provider: FakeTranscriber())

    code = voice_capability_smoke.main([
        "--asr-provider",
        "funasr_openai",
        "--asr-base-url",
        "http://127.0.0.1:10095/v1",
        "--asr-api-key",
        "local",
        "--asr-audio",
        str(audio),
        "--report",
        str(report),
    ])

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["asr"]["ok"] is True
    assert payload["asr"]["text"] == "你好星汐"
    assert "local" not in json.dumps(payload, ensure_ascii=False)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
python -m pytest tests\test_voice_capability_smoke_tool.py -q
```

Expected: fails because `tools.voice_capability_smoke` does not exist.

- [ ] **Step 3: Implement smoke tool**

Create `tools/voice_capability_smoke.py` with:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from guanghe_companion.capability_settings import ASRSettings, TTSSettings
from guanghe_companion.voice_asr import default_asr_transcriber
from guanghe_companion.voice_tts import default_tts_provider_factory


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test E-Moti voice providers.")
    parser.add_argument("--tts-provider", default="")
    parser.add_argument("--tts-text", default="")
    parser.add_argument("--tts-voice", default="")
    parser.add_argument("--tts-api-url", default="")
    parser.add_argument("--tts-model-variant", default="qwen3tts_1.6b")
    parser.add_argument("--asr-provider", default="")
    parser.add_argument("--asr-model", default="whisper-1")
    parser.add_argument("--asr-base-url", default="")
    parser.add_argument("--asr-api-key", default="")
    parser.add_argument("--asr-audio", default="")
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)

    report: dict[str, object] = {"tts": None, "asr": None}
    exit_code = 0

    if args.tts_provider:
        provider = default_tts_provider_factory(args.tts_provider)
        if provider is None:
            report["tts"] = {"ok": False, "message": f"TTS provider 不可用：{args.tts_provider}"}
            exit_code = 1
        else:
            result = provider.speak(
                args.tts_text,
                TTSSettings(
                    enabled=True,
                    provider=args.tts_provider,
                    voice=args.tts_voice,
                    api_url=args.tts_api_url,
                    model_variant=args.tts_model_variant,
                ),
            )
            report["tts"] = {"ok": result.ok, "message": result.message, "audio_path": result.audio_path}
            if not result.ok:
                exit_code = 1

    if args.asr_provider:
        audio_path = Path(args.asr_audio)
        if not audio_path.exists():
            report["asr"] = {"ok": False, "message": "ASR 音频文件不存在", "text": ""}
            exit_code = 1
        else:
            transcriber = default_asr_transcriber(args.asr_provider)
            result = transcriber.transcribe(
                audio_path.read_bytes(),
                ASRSettings(
                    enabled=True,
                    provider=args.asr_provider,
                    model=args.asr_model,
                    base_url=args.asr_base_url,
                    api_key=args.asr_api_key,
                ),
            )
            report["asr"] = {"ok": result.ok, "message": result.message, "text": result.text}
            if not result.ok:
                exit_code = 1

    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
```

Add to `.gitignore`:

```text
artifacts/voice-smoke/
```

- [ ] **Step 4: Run smoke-tool tests**

Run:

```powershell
python -m pytest tests\test_voice_capability_smoke_tool.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add .gitignore tools\voice_capability_smoke.py tests\test_voice_capability_smoke_tool.py
git commit -m "feat: add voice capability smoke tool"
```

## Task 6: Verification And Packaging Gate

**Files:**
- No production file changes unless previous tasks require fixes.
- Report artifacts go under ignored `artifacts/voice-smoke/`.

- [ ] **Step 1: Run focused voice tests**

```powershell
python -m pytest tests\test_voice_provider_catalog.py tests\test_capability_settings.py tests\test_capability_panels.py tests\test_voice_tts.py tests\test_voice_asr.py tests\test_voice_capability_smoke_tool.py -q
```

Expected: pass.

- [ ] **Step 2: Run UI smoke tests**

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
```

Expected: pass.

- [ ] **Step 3: Run full suite**

```powershell
python -m pytest
```

Expected: pass.

- [ ] **Step 4: Run live TTS smoke for preview provider**

```powershell
python tools\voice_capability_smoke.py --tts-provider edge_tts --tts-text "星汐语音升级测试。" --tts-voice zh-CN-XiaoxiaoNeural --report artifacts\voice-smoke\edge-tts-live.json
python -m json.tool artifacts\voice-smoke\edge-tts-live.json
```

Expected:

- report exists;
- `tts.ok` is true on a networked machine;
- no API key is written.

- [ ] **Step 5: Run ASR dry smoke with mocked or user-provided WAV**

If a local FunASR/SenseVoice service exists:

```powershell
python tools\voice_capability_smoke.py --asr-provider sensevoice_openai --asr-model iic/SenseVoiceSmall --asr-base-url http://127.0.0.1:10095/v1 --asr-api-key local --asr-audio artifacts\voice-smoke\sample.wav --report artifacts\voice-smoke\sensevoice-live.json
python -m json.tool artifacts\voice-smoke\sensevoice-live.json
```

Expected:

- `asr.ok` true when service and WAV are present;
- recognized text is present;
- the API key literal is not in the report.

If no ASR service is running, record the blocker as `local_asr_service_missing`; do not call ASR complete.

- [ ] **Step 6: Packaging check if runtime files changed**

Because `pyproject.toml`, packaging scripts, or provider imports may be touched:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\voice-smoke\windows-build-validation.json
```

Expected: build validator `ok: true`.

## Acceptance Criteria

- Provider routes are visible from a single catalog, not hardcoded in multiple UI locations.
- `edge_tts` remains a preview-safe TTS route.
- Qwen3-TTS is documented and selectable as the formal HTTP/local-service route.
- FunASR/SenseVoice/Qwen3-ASR are selectable ASR routes through the existing OpenAI-compatible adapter.
- ASR auto-send still returns `DialogueRequest(source="asr")` only.
- TTS still consumes cleaned validated speech only.
- No new code path mutates growth state, inventory, relationship, memory, goals, coins, or save files.
- Full pytest remains green.
- Voice smoke artifacts stay ignored.

## Known Non-Goals For This Package

- Do not train or distribute Ikaros/Nairong cloned voices.
- Do not vendor Qwen3-TTS, Qwen3-ASR, FunASR, SenseVoice, GPT-SoVITS, or CosyVoice model weights into the app.
- Do not add background listening, wake word, startup persistence, or microphone always-on behavior.
- Do not replace current character pack or renderer routes.
- Do not make ASR complete unless a real local/cloud transcription endpoint is tested with a WAV or microphone capture.

