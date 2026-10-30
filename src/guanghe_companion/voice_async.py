from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from itertools import count
from threading import Event, RLock

from .voice_tts import TTSResult, _run_cancellable_speech


@dataclass(slots=True)
class VoiceAsyncRunner:
    speak: Callable[[str], TTSResult]
    on_finished: Callable[[int, TTSResult], None]
    executor_class: type[ThreadPoolExecutor] | None = ThreadPoolExecutor
    _ids: count = field(init=False, repr=False)
    _latest_job_id: int = field(default=0, init=False, repr=False)
    _executor: ThreadPoolExecutor | None = field(default=None, init=False, repr=False)
    _futures: dict[int, tuple[Future[TTSResult], Event]] = field(default_factory=dict, init=False, repr=False)
    _lock: object = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._ids = count(1)
        if self.executor_class is not None:
            self._executor = self.executor_class(max_workers=1, thread_name_prefix="voice-tts")

    def run(self, text: str) -> int:
        with self._lock:
            job_id = next(self._ids)
            self._latest_job_id = job_id
            if self._executor is None:
                return job_id
            cancelled = Event()
            future = self._executor.submit(_run_cancellable_speech, self.speak, text, cancelled)
            self._futures[job_id] = (future, cancelled)
            future.add_done_callback(lambda done, current=job_id: self._finish(current, done))
            return job_id

    def cancel_pending(self) -> None:
        """Discard queued jobs and revoke playback permission for active jobs."""
        with self._lock:
            self._latest_job_id = 0
            for future, cancelled in list(self._futures.values()):
                cancelled.set()
                future.cancel()
            self._futures.clear()

    def is_current(self, job_id: int) -> bool:
        with self._lock:
            return job_id != 0 and job_id == self._latest_job_id

    def shutdown(self) -> None:
        self.cancel_pending()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def _finish(self, job_id: int, future: Future[TTSResult]) -> None:
        with self._lock:
            self._futures.pop(job_id, None)
        try:
            result = future.result()
        except Exception as exc:
            result = TTSResult(False, f"TTS 后台朗读失败：{exc}")
        self._finish_for_test(job_id, result)

    def _finish_for_test(self, job_id: int, result: TTSResult) -> None:
        with self._lock:
            if self.is_current(job_id):
                self.on_finished(job_id, result)

