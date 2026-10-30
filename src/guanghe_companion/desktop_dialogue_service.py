from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import QObject, Qt, Signal, Slot

from .controller import HostDialogueBusyError, HostDialogueStaleError


class DesktopDialogueService(QObject):
    snapshot_changed = Signal(object)
    failed = Signal(str)
    _dispatch = Signal(object)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="desktop-expression")
        self._active = None
        self._closed = False
        self._dispatch.connect(self._deliver, Qt.ConnectionType.QueuedConnection)

    def submit(self, request, *, include_ai_expression=True) -> Future:
        c = self.controller
        c._require_host_thread()
        if self._closed:
            raise RuntimeError("desktop dialogue service is closed")
        if self._active is not None:
            raise HostDialogueBusyError("desktop dialogue is busy")
        c._require_dialogue_idle()
        # 召回准备期间也保留同一角色的串行权威，禁止另一入口抢先提交对话。
        c._desktop_dialogue_pending = True
        result = Future()
        self._active = {"result": result, "request": request, "include_ai": include_ai_expression,
                        "generation": c.host_context_generation, "character": c.state.character_id,
                        "epoch": c._dialogue_context_epoch(), "ticket": None}
        try:
            prepared = c.prepare_semantic_recall(request)
            self._active.update(generation=c.host_context_generation, epoch=c._dialogue_context_epoch())
        except Exception as exc:
            self._finish_error(exc)
            return result
        if prepared is None:
            self._dispatch.emit(("start", None))
        else:
            prepared.add_done_callback(lambda done: self._dispatch.emit(("start", done)))
        return result

    @Slot(object)
    def _deliver(self, payload):
        if self._active is None:
            return
        operation, future = payload
        try:
            if operation == "start":
                self._start(future)
            elif operation == "extracted":
                self._extracted(future)
            else:
                self._complete(future)
        except Exception as exc:
            self._finish_error(exc)

    def _start(self, prepared):
        c, state = self.controller, self._active
        c._require_host_thread()
        if state["result"].cancelled() or self._closed:
            c._desktop_dialogue_pending = False
            self._active = None
            return
        if prepared is not None:
            # 失败向界面公开；调用者可明确选择词法重试，不静默掩盖下载/推理失败。
            prepared.result()
        if (state["generation"] != c.host_context_generation or state["character"] != c.state.character_id
                or state["epoch"] != c._dialogue_context_epoch()):
            raise HostDialogueStaleError("memory or character changed while preparing recall")
        handled = c._prepare_host_memory(state["request"])
        from .chat_memory_extraction import should_extract, extract_memory
        if (c.last_chat_memory_result.status in {"ignored", "clarify"}
                and state["include_ai"] and c.ai_expressor.enabled and c.ai_expressor.llm_client is not None
                and should_extract(state["request"].normalized_text(), mode=c.chat_memory.mode)):
            state.update(generation=c.host_context_generation, epoch=c._dialogue_context_epoch())
            state["extraction"] = c.chat_memory_extraction.prepare(state["request"].normalized_text(),
                now=int(c.now), mode=c.chat_memory.mode, generation=c.host_context_generation)
            state["extractor"] = c.chat_memory_extraction
            work = self._worker.submit(extract_memory, state["extraction"], c.ai_expressor.llm_client)
            work.add_done_callback(lambda done: self._dispatch.emit(("extracted", done)))
            return
        self._prepare_expression(handled)

    def _extracted(self, work):
        c, state = self.controller, self._active
        if state["result"].cancelled() or self._closed:
            state["extractor"].discard(state["extraction"])
            c._desktop_dialogue_pending = False
            self._active = None
            return
        if (state["generation"] != c.host_context_generation or state["character"] != c.state.character_id
                or state["epoch"] != c._dialogue_context_epoch()):
            raise HostDialogueStaleError("memory or character changed during extraction")
        result = c.chat_memory_extraction.apply(state["extraction"], work.result(), now=int(c.now),
            generation=c.host_context_generation, mode=c.chat_memory.mode)
        c.last_chat_memory_result = result
        if state["epoch"] != c._dialogue_context_epoch():
            c._on_memory_invalidated()
        self._prepare_expression(result.status in {"pending", "clarify", "forgotten"})

    def _prepare_expression(self, handled):
        c, state = self.controller, self._active
        c._desktop_dialogue_pending = False
        ticket = c.prepare_host_dialogue(state["request"], include_ai_expression=state["include_ai"],
                                         memory_prepared=handled)
        state["ticket"] = ticket
        if ticket.expression_request is None:
            self._complete(None)
        else:
            work = self._worker.submit(self._express, ticket)
            work.add_done_callback(lambda done: self._dispatch.emit(("complete", done)))

    @staticmethod
    def _express(ticket):
        if ticket.cancelled.is_set():
            raise HostDialogueStaleError("cancelled before expression")
        return ticket.expressor.express(ticket.expression_request, effect="ATTENTION")

    def _complete(self, work):
        state = self._active
        if state["result"].cancelled():
            self.controller.cancel_host_dialogue()
        events = work.result() if work is not None else None
        snapshot = self.controller.complete_host_dialogue(state["ticket"], events)
        if not state["result"].done():
            state["result"].set_result(snapshot)
            self.snapshot_changed.emit(snapshot)
        self._active = None

    def _finish_error(self, exc):
        c, state = self.controller, self._active
        c._desktop_dialogue_pending = False
        if state is not None:
            if "extraction" in state:
                state["extractor"].discard(state["extraction"])
            ticket = state["ticket"]
            if ticket is not None and c._host_dialogue_ticket is ticket:
                c.cancel_host_dialogue()
                try:
                    c.complete_host_dialogue(ticket)
                except HostDialogueStaleError:
                    pass
            if not state["result"].done():
                state["result"].set_exception(exc)
                self.failed.emit(str(exc))
        self._active = None

    def cancel(self):
        self.controller._require_host_thread()
        if self._active is not None:
            self._active["result"].cancel()
            if self._active["ticket"] is not None:
                self.controller.cancel_host_dialogue()

    def close(self):
        self.cancel()
        self._closed = True
        self._worker.shutdown(wait=False, cancel_futures=True)
