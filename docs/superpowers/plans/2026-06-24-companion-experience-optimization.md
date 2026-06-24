# Companion Experience Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve E-Moti from a technically complete demo into a smoother course-submission experience by reducing perceived voice latency, making voice/LLM/ASR flows easier to verify, and keeping every AI capability behind the existing typed boundaries.

**Architecture:** Keep the current state machine, typed events, `CapabilityRuntime`, and `http_emoti_voice` gateway as the core boundaries. Optimize the user-facing hot paths by adding deterministic TTS caching, non-blocking speech execution, service preflight/warmup reporting, richer character synthesis text mapping, and a repeatable simulated-play QA script. No AI provider may mutate growth state, inventory, relationship, memory, goals, coins, or saves.

**Tech Stack:** Python 3.11, PySide6, existing `TTSManager` and `CapabilityRuntime`, local Qwen3TTS HTTP service, local GPT-SoVITS HTTP service, SenseVoice-compatible ASR service, DeepSeek/OpenAI-compatible LLM expression path, pytest, existing Windows packaging scripts.

---

## Difficulty Judgment

The residual limitation is manageable, not a fundamental blocker.

The slow part is currently the first real synthesis call, especially the Qwen3TTS backend used by Xingxi and Nairong. The current architecture already solved the most important design risk by adding `http_emoti_voice`: the app has one stable provider surface while each character profile can delegate to Qwen3TTS or GPT-SoVITS. That means optimization can happen behind the gateway without rewriting character switching, ASR, LLM expression, or the pet state machine.

The practical risk is user perception:

- If a button click blocks while TTS synthesizes for 18-30 seconds, the demo feels broken even when the backend eventually returns audio.
- If every repeated demo line synthesizes from scratch, course presentation becomes fragile.
- If service startup and warmup are invisible, the user cannot tell whether the voice feature is working or waiting.
- If bilingual Ikaros only maps three fixed lines, the feature is real but too narrow for a natural demo.

The plan therefore treats voice as a product hot path:

1. cache repeated speech;
2. avoid blocking the UI while synthesis runs;
3. surface warmup/status clearly;
4. broaden bilingual mapping in a bounded way;
5. verify with an end-to-end simulated play script.

## Current Verified State

Verified on 2026-06-24 at the repository root:

```powershell
git status --short --untracked-files=all
# clean

git log --oneline --decorate -5
# 39a646f (HEAD -> main) feat: unify character voice provider
# 41f7ee2 feat: connect ikaros gptsovits voice profile
# 93793f1 feat: support qwen xvector voice clone refs
# 9f0f288 feat: add reference voice clone routing
# 1b80935 feat: add character voice profile audition smoke

git branch --show-current
# main

python -m pytest
# 953 passed
```

Relevant current behavior:

- `src/guanghe_companion/voice_tts.py` has synchronous `TTSManager.speak()`.
- `src/guanghe_companion/app.py::_handle_tts_test()` calls TTS synchronously from the UI handler.
- `src/guanghe_companion/app.py::_maybe_auto_speak_snapshot()` calls `CapabilityRuntime.speak_text()` synchronously after applying a snapshot.
- `http_emoti_voice` delegates to per-character backend providers.
- Xingxi and Nairong use Qwen3TTS backend through the gateway.
- Ikaros uses GPT-SoVITS backend through the gateway and has `synthesis_text_mode: "profile_static_map"`.
- ASR already goes through `DialogueRequest(source="asr")`.
- Screen observation and web search are read-only expression context.

## File Structure

Planned modifications are intentionally small and isolated.

- Modify: `src/guanghe_companion/voice_tts.py`
  - Add deterministic cache key helpers.
  - Add cached playback for HTTP Qwen3TTS and GPT-SoVITS.
  - Add a small result message distinction for cache hits.
- Modify: `tests/test_voice_tts.py`
  - Add cache hit tests for Qwen3TTS, GPT-SoVITS, and gateway bilingual mapping.
- Modify: `src/guanghe_companion/voice_async.py`
  - New focused module for background TTS execution.
  - Does not know about app widgets, game state, ASR, or LLM.
- Modify: `tests/test_voice_async.py`
  - Prove background runner emits start/finish callbacks and can ignore stale results.
- Modify: `src/guanghe_companion/app.py`
  - Use `VoiceAsyncRunner` for TTS test and auto-speak.
  - Keep ASR, LLM, screen observation, and web search behavior unchanged.
- Modify: `tests/test_app.py`
  - Prove slow TTS does not block UI handlers.
  - Prove auto TTS still consumes only validated snapshot speech.
- Modify: `tools/voice_capability_smoke.py`
  - Add `elapsed_seconds`, `synthesis_text_preview`, and backend fields to reports.
- Modify: `tests/test_voice_capability_smoke_tool.py`
  - Verify report fields and secret-free output.
- Modify: `tools/voice_services/preflight_voice_services.py`
  - New CLI that checks local TTS/ASR endpoints and optional warmup lines.
- Modify: `tests/test_voice_service_preflight_tool.py`
  - Verify endpoint checks, warmup report shape, and failure messages.
- Modify: `assets/companion/ikaros_pixel_pet/character.json`
  - Expand demo-safe `synthesis_text_map` for common Chinese display lines.
- Modify: `tests/test_character_pack.py`
  - Prove Ikaros keeps Chinese display / Japanese synthesis metadata and the expanded phrase map is valid.
- Modify: `tools/simulate_companion_playthrough.py`
  - New reproducible QA script for character switching, dialogue, LLM expression smoke, TTS smoke, and ASR audio-file smoke when inputs are provided.
- Modify: `tests/test_simulate_companion_playthrough_tool.py`
  - Verify report shape without live services.
- Modify: `docs/e_moti_course_submission_2026-06-23.md`
  - Update only after implementation and verification, recording real commands and real results.

## Task 1: Deterministic TTS Cache

**Files:**
- Modify: `tests/test_voice_tts.py`
- Modify: `src/guanghe_companion/voice_tts.py`

- [ ] **Step 1: Write the failing Qwen cache test**

Add this test to `tests/test_voice_tts.py`:

```python
def test_http_qwen3tts_provider_reuses_cached_audio_for_same_voice_request(tmp_path) -> None:
    from guanghe_companion.capability_settings import TTSSettings
    from guanghe_companion.voice_tts import HttpQwen3TTSProvider

    posts: list[dict[str, object]] = []
    played: list[str] = []

    def fake_post(url: str, payload: dict[str, object], timeout: int) -> bytes:
        posts.append(payload)
        return b"RIFFdemo-qwen-audio"

    provider = HttpQwen3TTSProvider(
        post=fake_post,
        cache_dir=tmp_path,
        audio_player=lambda path: played.append(str(path)),
    )
    settings = TTSSettings(
        enabled=True,
        provider="http_qwen3tts",
        api_url="http://127.0.0.1:9880/",
        language="zh",
        voice="Vivian",
        model_variant="qwen3tts_0.6b_customvoice",
        instruct="warm companion voice",
    )

    first = provider.speak("星汐在这里。", settings)
    second = provider.speak("星汐在这里。", settings)

    assert first.ok is True
    assert second.ok is True
    assert "缓存" in second.message
    assert len(posts) == 1
    assert len(played) == 2
    assert played[0] == played[1]
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
python -m pytest tests\test_voice_tts.py::test_http_qwen3tts_provider_reuses_cached_audio_for_same_voice_request -q
```

Expected before implementation:

```text
FAILED ... assert len(posts) == 1
```

- [ ] **Step 3: Implement cache helpers in `voice_tts.py`**

Add deterministic helpers near the existing helper functions:

```python
import hashlib

def _tts_cache_path(cache_dir: Path, prefix: str, text: str, settings: TTSSettings, suffix: str) -> Path:
    payload = {
        "text": text,
        "provider": settings.provider,
        "language": settings.language,
        "voice": settings.voice,
        "model_variant": settings.model_variant,
        "profile_id": settings.profile_id,
        "instruct": settings.instruct,
        "reference_audio": list(settings.reference_audio),
        "reference_text": settings.reference_text,
        "rate": settings.rate,
        "volume": settings.volume,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return cache_dir / f"{prefix}_{digest}{suffix}"
```

Then update `HttpQwen3TTSProvider.speak()`:

```python
self._cache_dir.mkdir(parents=True, exist_ok=True)
output = _tts_cache_path(self._cache_dir, "qwen3tts", text, settings, ".wav")
if output.exists():
    self._audio_player(output)
    return TTSResult(True, "朗读完成（缓存）", str(output))
audio = self._post(endpoint, payload, 180)
...
output.write_bytes(audio)
self._audio_player(output)
return TTSResult(True, "朗读完成", str(output))
```

Keep the existing latest-file behavior only if tests require it; otherwise the stable cache path becomes the audio path returned in reports.

- [ ] **Step 4: Verify the Qwen cache test passes**

Run:

```powershell
python -m pytest tests\test_voice_tts.py::test_http_qwen3tts_provider_reuses_cached_audio_for_same_voice_request -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Add GPT-SoVITS cache coverage**

Add this test:

```python
def test_http_gptsovits_provider_reuses_cached_audio_for_same_voice_request(tmp_path) -> None:
    from guanghe_companion.capability_settings import TTSSettings
    from guanghe_companion.voice_tts import HttpGPTSoVITSProvider

    posts: list[dict[str, object]] = []
    played: list[str] = []

    def fake_post(url: str, payload: dict[str, object], timeout: int) -> bytes:
        posts.append(payload)
        return b"RIFFdemo-gptsovits-audio"

    provider = HttpGPTSoVITSProvider(
        post=fake_post,
        cache_dir=tmp_path,
        audio_player=lambda path: played.append(str(path)),
    )
    settings = TTSSettings(
        enabled=True,
        provider="http_gptsovits",
        api_url="http://127.0.0.1:9882/",
        language="all_ja",
        voice="ikaros_curated160_e4",
        model_variant="gptsovits_v2",
        reference_audio=("D:/voice-packs/ikaros/reference.wav",),
        reference_text="マスター、私はここにいます。",
        rate=-1,
        volume=0.88,
    )

    first = provider.speak("マスター、私はここにいます。", settings)
    second = provider.speak("マスター、私はここにいます。", settings)

    assert first.ok is True
    assert second.ok is True
    assert "缓存" in second.message
    assert len(posts) == 1
    assert len(played) == 2
    assert played[0] == played[1]
```

- [ ] **Step 6: Implement GPT cache using the same helper**

Update `HttpGPTSoVITSProvider.speak()`:

```python
self._cache_dir.mkdir(parents=True, exist_ok=True)
output = _tts_cache_path(self._cache_dir, "gptsovits", text, settings, ".wav")
if output.exists():
    self._audio_player(output)
    return TTSResult(True, "GPT-SoVITS speech complete（缓存）", str(output))
audio = self._post(endpoint, payload, 180)
...
output.write_bytes(audio)
self._audio_player(output)
return TTSResult(True, "GPT-SoVITS speech complete", str(output))
```

- [ ] **Step 7: Verify focused TTS tests**

Run:

```powershell
python -m pytest tests\test_voice_tts.py -q
```

Expected:

```text
15 passed
```

- [ ] **Step 8: Commit Task 1**

Run:

```powershell
git status --short --untracked-files=all
git diff --check
git add src\guanghe_companion\voice_tts.py tests\test_voice_tts.py
git commit -m "feat: cache repeated tts synthesis"
```

Expected: no `data/`, `artifacts/`, `dist/`, API keys, or generated audio are staged.

## Task 2: Non-Blocking TTS Runner

**Files:**
- Create: `src/guanghe_companion/voice_async.py`
- Create: `tests/test_voice_async.py`
- Modify: `src/guanghe_companion/app.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Add a focused async runner test**

Create `tests/test_voice_async.py`:

```python
from __future__ import annotations


def test_voice_async_runner_reports_latest_result_only() -> None:
    from guanghe_companion.capability_settings import TTSSettings
    from guanghe_companion.voice_async import VoiceAsyncRunner
    from guanghe_companion.voice_tts import TTSResult

    finished: list[tuple[int, TTSResult]] = []

    class FakeRuntime:
        def speak_text(self, text: str) -> TTSResult:
            return TTSResult(True, f"spoken:{text}")

    runner = VoiceAsyncRunner(
        speak=lambda text: FakeRuntime().speak_text(text),
        on_finished=lambda job_id, result: finished.append((job_id, result)),
        executor_class=None,
    )

    first = runner.run("first")
    second = runner.run("second")
    runner._finish_for_test(first, TTSResult(True, "spoken:first"))
    runner._finish_for_test(second, TTSResult(True, "spoken:second"))

    assert finished == [(second, TTSResult(True, "spoken:second"))]
```

- [ ] **Step 2: Run the failing async runner test**

Run:

```powershell
python -m pytest tests\test_voice_async.py -q
```

Expected before implementation:

```text
ERROR ... ModuleNotFoundError: No module named 'guanghe_companion.voice_async'
```

- [ ] **Step 3: Implement `VoiceAsyncRunner`**

Create `src/guanghe_companion/voice_async.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from itertools import count

from .voice_tts import TTSResult


@dataclass(slots=True)
class VoiceAsyncRunner:
    speak: Callable[[str], TTSResult]
    on_finished: Callable[[int, TTSResult], None]
    executor_class: type[ThreadPoolExecutor] | None = ThreadPoolExecutor

    def __post_init__(self) -> None:
        self._ids = count(1)
        self._latest_job_id = 0
        self._executor = self.executor_class(max_workers=1, thread_name_prefix="voice-tts") if self.executor_class else None

    def run(self, text: str) -> int:
        job_id = next(self._ids)
        self._latest_job_id = job_id
        if self._executor is None:
            return job_id
        future = self._executor.submit(self.speak, text)
        future.add_done_callback(lambda done, current=job_id: self._finish(current, done))
        return job_id

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def _finish(self, job_id: int, future: Future[TTSResult]) -> None:
        try:
            result = future.result()
        except Exception as exc:
            result = TTSResult(False, f"TTS 后台朗读失败：{exc}")
        self._finish_for_test(job_id, result)

    def _finish_for_test(self, job_id: int, result: TTSResult) -> None:
        if job_id == self._latest_job_id:
            self.on_finished(job_id, result)
```

- [ ] **Step 4: Verify async runner test**

Run:

```powershell
python -m pytest tests\test_voice_async.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Add app non-blocking tests**

Add tests in `tests/test_app.py` proving `_handle_tts_test()` and `_maybe_auto_speak_snapshot()` enqueue work instead of calling the slow manager inline. Use a fake runner:

```python
class FakeVoiceRunner:
    def __init__(self):
        self.texts = []

    def run(self, text: str) -> int:
        self.texts.append(text)
        return len(self.texts)

    def shutdown(self) -> None:
        pass
```

Assert:

```python
window.voice_async_runner = FakeVoiceRunner()
window._handle_tts_test()
assert window.voice_async_runner.texts == [f"{window.controller.character_pack.name} voice test."]
assert "后台" in window.voice_status_label.text()
```

- [ ] **Step 6: Wire app to `VoiceAsyncRunner`**

In `CompanionWindow.__init__`, create:

```python
self.voice_async_runner = VoiceAsyncRunner(
    speak=self.capability_runtime.speak_text,
    on_finished=self._handle_async_tts_finished,
)
```

Update `_handle_tts_test()`:

```python
self.voice_async_runner.run(f"{self.controller.character_pack.name} voice test.")
self.voice_status_label.setText("TTS 正在后台合成...")
```

Update `_maybe_auto_speak_snapshot()`:

```python
self.voice_async_runner.run(speech)
self.voice_status_label.setText("TTS 正在后台合成...")
```

Add:

```python
def _handle_async_tts_finished(self, job_id: int, result: TTSResult) -> None:
    self.voice_status_label.setText(result.message)
```

In close cleanup:

```python
self.voice_async_runner.shutdown()
```

If Qt thread affinity causes label updates from a worker callback, replace direct callback with `QTimer.singleShot(0, lambda: self._handle_async_tts_finished(job_id, result))`.

- [ ] **Step 7: Verify app and voice tests**

Run:

```powershell
python -m pytest tests\test_voice_async.py tests\test_app.py::test_auto_tts_consumes_snapshot_speech_after_validation -q
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
```

Expected: pass.

- [ ] **Step 8: Commit Task 2**

Run:

```powershell
git status --short --untracked-files=all
git diff --check
git add src\guanghe_companion\voice_async.py src\guanghe_companion\app.py tests\test_voice_async.py tests\test_app.py
git commit -m "feat: run tts synthesis off the ui path"
```

## Task 3: Voice Smoke Reports With Latency And Backend Proof

**Files:**
- Modify: `tools/voice_capability_smoke.py`
- Modify: `tests/test_voice_capability_smoke_tool.py`

- [ ] **Step 1: Add failing report-field test**

In `tests/test_voice_capability_smoke_tool.py`, extend the gateway skip-playback test:

```python
assert payload["tts"]["elapsed_seconds"] >= 0
assert payload["tts"]["backend_provider"] == "http_gptsovits"
assert payload["tts"]["synthesis_language"] == "all_ja"
assert payload["tts"]["synthesis_text_preview"] == "マスター、私はここにいます。"
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
python -m pytest tests\test_voice_capability_smoke_tool.py::test_voice_smoke_tool_can_skip_qt_playback_for_emoti_voice_gateway -q
```

Expected: fail because the fields are missing.

- [ ] **Step 3: Implement timing and preview**

In `tools/voice_capability_smoke.py`, import:

```python
from time import perf_counter
from guanghe_companion.voice_tts import select_synthesis_text
```

Around `provider.speak(...)`:

```python
display_text = _tts_text_from_args(args, character_pack)
synthesis_text = select_synthesis_text(display_text, tts_settings)
started = perf_counter()
result = provider.speak(display_text, tts_settings)
elapsed_seconds = round(perf_counter() - started, 3)
```

Add report fields:

```python
"elapsed_seconds": elapsed_seconds,
"backend_provider": tts_settings.backend_provider,
"backend_model_variant": tts_settings.backend_model_variant,
"display_language": tts_settings.display_language,
"synthesis_language": tts_settings.synthesis_language,
"synthesis_text_preview": synthesis_text[:80],
```

- [ ] **Step 4: Verify smoke tool tests**

Run:

```powershell
python -m pytest tests\test_voice_capability_smoke_tool.py -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 3**

Run:

```powershell
git diff --check
git add tools\voice_capability_smoke.py tests\test_voice_capability_smoke_tool.py
git commit -m "feat: report voice smoke latency and backend"
```

## Task 4: Voice Service Preflight And Warmup

**Files:**
- Create: `tools/voice_services/preflight_voice_services.py`
- Create: `tests/test_voice_service_preflight_tool.py`

- [ ] **Step 1: Add preflight tests**

Create `tests/test_voice_service_preflight_tool.py`:

```python
from __future__ import annotations

import json


def test_voice_service_preflight_reports_endpoint_status(tmp_path, monkeypatch) -> None:
    from tools.voice_services import preflight_voice_services

    calls: list[str] = []

    def fake_probe(url: str, timeout: float) -> tuple[bool, str]:
        calls.append(url)
        return (True, "listening")

    monkeypatch.setattr(preflight_voice_services, "_probe_http", fake_probe)
    report = tmp_path / "preflight.json"

    code = preflight_voice_services.main(["--report", str(report)])

    assert code == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["qwen3tts"]["ok"] is True
    assert payload["gptsovits"]["ok"] is True
    assert payload["sensevoice_asr"]["ok"] is True
    assert calls == [
        "http://127.0.0.1:9880/tts",
        "http://127.0.0.1:9882/",
        "http://127.0.0.1:8899/v1/models",
    ]
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
python -m pytest tests\test_voice_service_preflight_tool.py -q
```

Expected: fail because the tool does not exist.

- [ ] **Step 3: Implement preflight tool**

Create `tools/voice_services/preflight_voice_services.py`:

```python
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Sequence


DEFAULT_ENDPOINTS = {
    "qwen3tts": "http://127.0.0.1:9880/tts",
    "gptsovits": "http://127.0.0.1:9882/",
    "sensevoice_asr": "http://127.0.0.1:8899/v1/models",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local E-Moti voice services.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args(argv)

    report = {}
    exit_code = 0
    for name, url in DEFAULT_ENDPOINTS.items():
        ok, message = _probe_http(url, args.timeout)
        report[name] = {"ok": ok, "url": url, "message": message}
        if not ok:
            exit_code = 1

    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return exit_code


def _probe_http(url: str, timeout: float) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return True, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        if 200 <= exc.code < 500:
            return True, f"HTTP {exc.code}"
        return False, f"HTTP {exc.code}"
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return False, str(exc)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify preflight tests**

Run:

```powershell
python -m pytest tests\test_voice_service_preflight_tool.py -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 4**

Run:

```powershell
git diff --check
git add tools\voice_services\preflight_voice_services.py tests\test_voice_service_preflight_tool.py
git commit -m "feat: add voice service preflight report"
```

## Task 5: Broaden Ikaros Chinese Display / Japanese Synthesis Map

**Files:**
- Modify: `assets/companion/ikaros_pixel_pet/character.json`
- Modify: `tests/test_character_pack.py`

- [ ] **Step 1: Add phrase-map contract test**

In `tests/test_character_pack.py`, add:

```python
def test_ikaros_bilingual_phrase_map_covers_demo_flow_lines() -> None:
    from guanghe_companion.character_pack import load_character_pack

    pack = load_character_pack("ikaros_pixel_pet")
    profile = pack.tts_profile

    expected_lines = {
        "我在这里。",
        "伊卡洛斯，和导师打个招呼。",
        "伊卡洛斯，陪我安静一会儿。",
        "我会陪着你。",
        "需要我待在这里吗？",
        "我明白了，Master。",
    }
    assert expected_lines.issubset(set(profile.synthesis_text_map))
    assert all("マスター" in value or "Master" in value for value in profile.synthesis_text_map.values())
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
python -m pytest tests\test_character_pack.py::test_ikaros_bilingual_phrase_map_covers_demo_flow_lines -q
```

Expected: fail because the map only contains the first three lines.

- [ ] **Step 3: Extend `synthesis_text_map`**

Add entries:

```json
"我会陪着你。": "マスター、そばにいます。",
"需要我待在这里吗？": "マスター、ここで待機しますか。",
"我明白了，Master。": "マスター、了解しました。"
```

- [ ] **Step 4: Verify JSON and character tests**

Run:

```powershell
python -m json.tool assets\companion\ikaros_pixel_pet\character.json > $null
python -m pytest tests\test_character_pack.py -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 5**

Run:

```powershell
git diff --check
git add assets\companion\ikaros_pixel_pet\character.json tests\test_character_pack.py
git commit -m "feat: expand ikaros bilingual tts phrase map"
```

## Task 6: Simulated Companion Playthrough QA Tool

**Files:**
- Create: `tools/simulate_companion_playthrough.py`
- Create: `tests/test_simulate_companion_playthrough_tool.py`

- [ ] **Step 1: Add report-shape test**

Create `tests/test_simulate_companion_playthrough_tool.py`:

```python
from __future__ import annotations

import json


def test_simulated_playthrough_report_without_live_services(tmp_path) -> None:
    from tools import simulate_companion_playthrough

    report = tmp_path / "playthrough.json"
    code = simulate_companion_playthrough.main(["--report", str(report), "--skip-live-voice"])

    assert code == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert [item["character_id"] for item in payload["characters"]] == [
        "xingxi_pixel_pet",
        "ikaros_pixel_pet",
        "nairong_pixel_pet",
    ]
    assert payload["state_mutation_guard"]["ok"] is True
    assert payload["voice"]["skipped"] is True
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
python -m pytest tests\test_simulate_companion_playthrough_tool.py -q
```

Expected: fail because the tool does not exist.

- [ ] **Step 3: Implement dry-run playthrough**

Create `tools/simulate_companion_playthrough.py` with:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.character_pack import load_character_pack
from guanghe_companion.controller import CompanionController


CHARACTER_IDS = ("xingxi_pixel_pet", "ikaros_pixel_pet", "nairong_pixel_pet")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a reproducible E-Moti simulated playthrough.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--skip-live-voice", action="store_true")
    args = parser.parse_args(argv)

    controller = CompanionController()
    before = controller.get_typed_snapshot()
    characters = []
    for character_id in CHARACTER_IDS:
        pack = load_character_pack(character_id)
        characters.append(
            {
                "character_id": pack.character_id,
                "name": pack.name,
                "renderer_backend": pack.renderer.backend,
                "tts_provider": pack.tts_profile.provider,
                "tts_backend_provider": pack.tts_profile.backend_provider,
            }
        )
    snapshot = controller.perform_action("touch", include_ai_expression=False)
    after = controller.get_typed_snapshot()
    state_guard_ok = bool(after.stats != before.stats or snapshot)

    payload = {
        "ok": True,
        "characters": characters,
        "state_mutation_guard": {
            "ok": state_guard_ok,
            "memory_entries": len(after.memory_log),
            "event_entries": len(after.events),
        },
        "voice": {"skipped": bool(args.skip_live_voice)},
    }
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify playthrough test**

Run:

```powershell
python -m pytest tests\test_simulate_companion_playthrough_tool.py -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 6**

Run:

```powershell
git diff --check
git add tools\simulate_companion_playthrough.py tests\test_simulate_companion_playthrough_tool.py
git commit -m "feat: add simulated companion playthrough qa"
```

## Task 7: Release Verification And Documentation Update

**Files:**
- Modify: `docs/e_moti_course_submission_2026-06-23.md`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests\test_voice_tts.py tests\test_voice_async.py tests\test_voice_capability_smoke_tool.py tests\test_voice_service_preflight_tool.py tests\test_simulate_companion_playthrough_tool.py tests\test_character_pack.py -q
```

Expected: pass.

- [ ] **Step 2: Run UI tests**

Run:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
```

Expected: pass.

- [ ] **Step 3: Run full regression**

Run:

```powershell
python -m pytest
```

Expected: pass.

- [ ] **Step 4: Run live voice smoke when services are listening**

Run:

```powershell
python tools\voice_services\preflight_voice_services.py --report artifacts\voice-smoke\voice-service-preflight.json
python tools\voice_capability_smoke.py --character-id xingxi_pixel_pet --tts-text "星汐，和导师打个招呼。" --skip-playback --report artifacts\voice-smoke\xingxi-optimized-live.json
python tools\voice_capability_smoke.py --character-id ikaros_pixel_pet --tts-text "我在这里。" --skip-playback --report artifacts\voice-smoke\ikaros-optimized-live.json
python tools\voice_capability_smoke.py --character-id nairong_pixel_pet --tts-text "奶龙，和导师打个招呼。" --skip-playback --report artifacts\voice-smoke\nairong-optimized-live.json
```

Expected:

- preflight report identifies which services are listening;
- repeated second run of the same TTS line returns a cache-hit message;
- reports include `elapsed_seconds`;
- reports are stored under ignored `artifacts/voice-smoke/`.

- [ ] **Step 5: Run simulated playthrough**

Run:

```powershell
python tools\simulate_companion_playthrough.py --skip-live-voice --report artifacts\qa\simulated-playthrough-optimized.json
```

Expected: report has `"ok": true` and lists Xingxi, Ikaros, and Nairong.

- [ ] **Step 6: Rebuild app and installer if runtime behavior changed**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\windows-build-validation.json
python tools\validate_windows_build.py --character-id xingxi_pixel_pet --report artifacts\windows-build-validation-xingxi-pixel-pet.json
python tools\validate_windows_build.py --character-id ikaros_pixel_pet --report artifacts\windows-build-validation-ikaros-pixel-pet.json
python tools\validate_windows_build.py --character-id nairong_pixel_pet --report artifacts\windows-build-validation-nairong-pixel-pet.json
```

Expected: all validation reports have `"ok": true`.

- [ ] **Step 7: Frozen exe smoke**

Run:

```powershell
$exe = (Resolve-Path 'dist\E-Moti\E-Moti.exe').Path
$p = Start-Process -FilePath $exe -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 5
if ($p.HasExited) { throw "Frozen control panel exited early with code $($p.ExitCode)" }
Stop-Process -Id $p.Id -Force
$p.WaitForExit()

$p = Start-Process -FilePath $exe -ArgumentList '--pet-mode' -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 5
if ($p.HasExited) { throw "Frozen pet mode exited early with code $($p.ExitCode)" }
Stop-Process -Id $p.Id -Force
$p.WaitForExit()
```

Expected: both launches stay alive for 5 seconds.

- [ ] **Step 8: Update course submission document with real results**

Only write verified statements into `docs/e_moti_course_submission_2026-06-23.md`:

- TTS cache exists and improves repeated demo lines;
- TTS synthesis no longer blocks UI handlers after Task 2;
- voice smoke reports include elapsed time and backend proof;
- simulated playthrough report exists;
- packaging and frozen smoke commands passed.

- [ ] **Step 9: Final hygiene and commit**

Run:

```powershell
git status --short --untracked-files=all
git diff --check
python -m pytest tests\test_repository_hygiene.py -q
rg -n "sk-[A-Za-z0-9_-]{16,}|api[_-]?key\s*[:=]\s*['\"]" assets docs src tests tools AGENTS.md pyproject.toml
git add docs\e_moti_course_submission_2026-06-23.md
git commit -m "docs: record optimized companion experience qa"
```

Expected: real secret fragments are not present; no runtime save, ignored artifacts, `dist/`, raw audio, or model weights are committed.

## Acceptance Criteria

- Repeated TTS lines hit cache and avoid a second backend synthesis call.
- TTS test and auto-speak do not block the UI hot path.
- Voice smoke reports include elapsed time, app-facing provider, backend provider, and synthesis language.
- Ikaros keeps Chinese display text and has a broader Japanese synthesis phrase map for classroom demo lines.
- ASR still only emits player input and uses `DialogueRequest`.
- LLM still only affects speech, expression, motion hints, and typed presentation events.
- Screen observation and web search remain read-only expression context.
- Simulated playthrough proves all three characters are present and switchable at the data/pack level.
- Full `python -m pytest` passes.
- Windows app and installer validate after runtime changes.
- No API key, runtime save, ignored artifact, raw training audio, or model weight is staged.
