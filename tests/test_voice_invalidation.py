"""Cancellation tests use local fakes: no model, network or audio device."""

from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from guanghe_companion.capability_settings import TTSSettings
from guanghe_companion.voice_async import VoiceAsyncRunner
from guanghe_companion.voice_tts import EdgeNeuralTTSProvider, HttpGPTSoVITSProvider, HttpQwen3TTSProvider, TTSResult


def test_cancel_pending_skips_queued_speech_and_accepts_next_new_job():
    started, release, fresh_finished = Event(), Event(), Event()
    spoken, finished = [], []

    def speak(text):
        spoken.append(text)
        if text == "active":
            started.set()
            assert release.wait(2)
        return TTSResult(True, text)

    def complete(job_id, result):
        finished.append(result.message)
        if result.message == "fresh":
            fresh_finished.set()

    runner = VoiceAsyncRunner(speak=speak, on_finished=complete)
    try:
        runner.run("active")
        assert started.wait(2)
        runner.run("must not start")
        runner.cancel_pending()
        runner.run("fresh")
        release.set()
        assert fresh_finished.wait(2)
        assert spoken == ["active", "fresh"]
        assert finished == ["fresh"]
    finally:
        release.set()
        runner.shutdown()


def test_cancel_after_dequeue_before_provider_start_still_blocks_old_audio(tmp_path):
    entered, release, fresh_finished = Event(), Event(), Event()
    played, posts = [], []

    def post(url, payload, timeout):
        posts.append(payload["text"])
        return b"RIFF" + b"0" * 100

    provider = HttpQwen3TTSProvider(post=post, cache_dir=tmp_path, audio_player=lambda path: played.append(path))
    settings = TTSSettings(enabled=True, provider="http_qwen3tts")

    def speak(text):
        if text == "revoked":
            entered.set()
            assert release.wait(2)
        return provider.speak(text, settings)

    runner = VoiceAsyncRunner(speak=speak, on_finished=lambda *_: fresh_finished.set())
    try:
        runner.run("revoked")
        assert entered.wait(2)
        runner.cancel_pending()
        provider.stop()
        runner.run("fresh")
        release.set()
        assert fresh_finished.wait(2)
        assert posts == ["fresh"]
        assert len(played) == 1
    finally:
        release.set()
        runner.shutdown()


@pytest.mark.parametrize("provider_class", [HttpQwen3TTSProvider, HttpGPTSoVITSProvider])
def test_http_stop_during_synthesis_blocks_late_playback_but_allows_new_speech(tmp_path, provider_class):
    played, posts = [], []

    def post(url, payload, timeout):
        posts.append(payload["text"])
        if len(posts) == 1:
            provider.stop()
        return b"RIFF" + b"0" * 100

    provider = provider_class(post=post, cache_dir=tmp_path, audio_player=lambda path: played.append(path))
    settings = TTSSettings(enabled=True, reference_audio=("reference.wav",), reference_text="reference")
    cancelled = provider.speak("revoked", settings)
    assert not cancelled.ok
    assert not played

    fresh = provider.speak("fresh", settings)
    assert fresh.ok
    assert len(played) == 1


def test_stop_during_cache_read_does_not_replay_cached_revoked_speech(tmp_path, monkeypatch):
    played = []
    provider = HttpQwen3TTSProvider(post=lambda *_: b"RIFFcached", cache_dir=tmp_path,
                                   audio_player=lambda path: played.append(path))
    settings = TTSSettings(enabled=True)
    assert provider.speak("cached", settings).ok
    original_read = Path.read_bytes

    def read_then_stop(path):
        data = original_read(path)
        provider.stop()
        return data

    monkeypatch.setattr(Path, "read_bytes", read_then_stop)
    result = provider.speak("cached", settings)
    assert not result.ok
    assert len(played) == 1


def test_edge_stop_during_synthesis_blocks_late_playback(tmp_path):
    played = []

    class Synthesis:
        def __init__(self, text, voice):
            self.text = text

        async def save(self, path):
            if self.text == "revoked":
                provider.stop()
            Path(path).write_bytes(b"fake-mp3")

    provider = EdgeNeuralTTSProvider(communicate_factory=Synthesis, cache_dir=tmp_path,
                                    audio_player=lambda path: played.append(path))
    settings = TTSSettings(enabled=True)
    assert not provider.speak("revoked", settings).ok
    assert not played
    assert provider.speak("fresh", settings).ok
    assert len(played) == 1


def test_sapi_stop_before_process_launch_blocks_old_spawn_and_allows_new_one(monkeypatch):
    from guanghe_companion import voice_tts

    spawned, terminated = [], []
    provider = voice_tts.WindowsSapiTTSProvider()

    class Process:
        def poll(self):
            return None

        def terminate(self):
            terminated.append(True)

    def prepare_script(**kwargs):
        if kwargs["text"] == "revoked":
            provider.stop()
        return "fake script; never executed"

    def start(*args, **kwargs):
        spawned.append(args)
        return Process()

    monkeypatch.setattr(voice_tts, "_windows_sapi_script", prepare_script)
    monkeypatch.setattr(voice_tts.subprocess, "Popen", start)
    assert not provider.speak("revoked", TTSSettings(enabled=True)).ok
    assert not spawned
    assert provider.speak("fresh", TTSSettings(enabled=True)).ok
    assert len(spawned) == 1
    provider.stop()
    assert terminated == [True]


@pytest.fixture
def window(tmp_path):
    from PySide6.QtWidgets import QApplication
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController

    app = QApplication.instance() or QApplication([])
    controller = PluginEnabledCompanionController(save_path=tmp_path / "save.json", user_data_root=tmp_path,
                                                  auto_load=False)
    widget = CompanionWindow(controller=controller)
    widget.voice_async_runner.shutdown()

    class Runner:
        def __init__(self):
            self.cancel_count = 0
            self.texts = []

        def run(self, text):
            self.texts.append(text)
            return len(self.texts)

        def cancel_pending(self):
            self.cancel_count += 1

        def shutdown(self):
            pass

    class Manager:
        def __init__(self):
            self.stops = []

        def stop(self, settings=None):
            self.stops.append(settings)
            return TTSResult(True, "已停止朗读")

    widget.voice_async_runner = Runner()
    widget.tts_manager = Manager()
    yield widget
    widget.close()
    app.processEvents()


def _speech_snapshot(window, text):
    snapshot = window.controller.get_snapshot()
    snapshot["events"] = [{"character_name": snapshot["character_name"], "speech": text,
                           "sprite": "1", "effect": "ATTENTION"}]
    return snapshot


def test_ui_memory_revocation_cancels_and_stops_without_replaying_snapshot(window):
    service = window.controller.story_runtime.memory
    entry = service.remember(kind="玩家希望被记住", title="偏好", summary="旧偏好", source="explicit_user_request", now=10)
    settings = window.controller.get_capability_settings()
    window.controller.update_capability_settings(replace(settings, tts=replace(settings.tts, enabled=True, auto_speak=True)))
    old = _speech_snapshot(window, "旧语音")
    window._apply_snapshot(old)
    assert window.voice_async_runner.texts == ["旧语音"]

    window.controller.memory_album_controller.forget(entry.memory_id, now=20)
    window._apply_snapshot(old)

    assert window.voice_async_runner.cancel_count == 1
    assert window.tts_manager.stops == [None]
    assert window.voice_async_runner.texts == ["旧语音"]
    window._apply_snapshot(_speech_snapshot(window, "新的合法语音"))
    assert window.voice_async_runner.texts == ["旧语音", "新的合法语音"]


def test_ui_character_change_stops_all_providers_and_plain_refresh_does_not(window, monkeypatch):
    # A controller without the V2 epoch hook still receives character fences.
    monkeypatch.setattr(window.controller, "_dialogue_context_epoch", None)
    snapshot = window.controller.get_snapshot()
    window._apply_snapshot(snapshot)
    assert not window.tts_manager.stops
    changed = dict(snapshot, character_id="another-character")
    window._apply_snapshot(changed)
    assert window.voice_async_runner.cancel_count == 1
    assert window.tts_manager.stops == [None]


def test_ui_manual_stop_also_cancels_not_yet_started_speech(window):
    window._handle_tts_stop()
    assert window.voice_async_runner.cancel_count == 1
    assert len(window.tts_manager.stops) == 1


def test_ui_queued_completion_cannot_override_status_after_cancel(window):
    runner = VoiceAsyncRunner(speak=lambda _: TTSResult(True, "unused"), on_finished=lambda *_: None,
                              executor_class=None)
    window.voice_async_runner = runner
    job_id = runner.run("old")
    window._handle_tts_stop()
    before = window.voice_status_label.text()
    window._handle_async_tts_finished(job_id, TTSResult(True, "stale completion"))
    assert window.voice_status_label.text() == before
