from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from itertools import count

from .voice_tts import TTSResult


@dataclass(slots=True)
class VoiceAsyncRunner:
    speak: Callable[[str], TTSResult]
    on_finished: Callable[[int, TTSResult], None]
    executor_class: type[ThreadPoolExecutor] | None = ThreadPoolExecutor
    _ids: count = field(init=False, repr=False)
    _latest_job_id: int = field(default=0, init=False, repr=False)
    _executor: ThreadPoolExecutor | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._ids = count(1)
        if self.executor_class is not None:
            self._executor = self.executor_class(max_workers=1, thread_name_prefix="voice-tts")

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

