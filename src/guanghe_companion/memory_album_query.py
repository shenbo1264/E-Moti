from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal, Slot, QThread

from .memory_album_controller import MemoryAlbumStaleError


class MemoryAlbumQueryService(QObject):
    completed = Signal(object)
    failed = Signal(str)
    _prepared = Signal(object)

    def __init__(self, current_album, parent=None):
        super().__init__(parent)
        self.current_album = current_album
        self._active = None
        self._closed = False
        self._prepared.connect(self._deliver, Qt.ConnectionType.QueuedConnection)

    def submit(self, query: str) -> None:
        if QThread.currentThread() != self.thread():
            raise RuntimeError("album queries must start on their owning Qt thread")
        if self._closed:
            raise RuntimeError("album query service is closed")
        album = self.current_album()
        if album is None:
            raise RuntimeError("memory album is not available")
        now = album.current_time()
        state = {"album": album, "query": query,
                 "epoch": album.story.memory.store.current_context_epoch(now=now)}
        self._active = state
        try:
            future = album.story.memory.prepare_retrieval(query, now=now)
        except Exception as exc:
            self._active = None
            self.failed.emit(str(exc))
            return
        if future is None:
            self._prepared.emit((state, None))
        else:
            # 复用已有 embedding/判据 worker；回调只发信号，不读写 Qt 或角色状态。
            future.add_done_callback(lambda done: self._queue(state, done))

    def _queue(self, state, future):
        if not self._closed:
            self._prepared.emit((state, future))

    @Slot(object)
    def _deliver(self, payload):
        state, future = payload
        if self._closed or state is not self._active:
            return
        self._active = None
        try:
            album = self.current_album()
            if album is not state["album"] or album.story.memory.store.current_context_epoch(
                    now=album.current_time()) != state["epoch"]:
                raise MemoryAlbumStaleError("记忆或角色刚有更新，请重新查找。")
            if future is not None:
                future.result()
            result = album.ask(state["query"])
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.completed.emit(result)

    def cancel(self) -> None:
        # 只撤回本页面的结果；不能取消桌面对话共用的检索准备。
        self._active = None

    def close(self) -> None:
        self._closed = True
        self.cancel()
