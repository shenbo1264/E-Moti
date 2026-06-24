from __future__ import annotations


def test_voice_async_runner_reports_latest_result_only() -> None:
    from guanghe_companion.voice_async import VoiceAsyncRunner
    from guanghe_companion.voice_tts import TTSResult

    finished: list[tuple[int, TTSResult]] = []

    runner = VoiceAsyncRunner(
        speak=lambda text: TTSResult(True, f"spoken:{text}"),
        on_finished=lambda job_id, result: finished.append((job_id, result)),
        executor_class=None,
    )

    first = runner.run("first")
    second = runner.run("second")
    runner._finish_for_test(first, TTSResult(True, "spoken:first"))
    runner._finish_for_test(second, TTSResult(True, "spoken:second"))

    assert finished == [(second, TTSResult(True, "spoken:second"))]

