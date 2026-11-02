import copy
from concurrent.futures import Future, CancelledError
from hashlib import sha256
import json
import threading
from uuid import uuid4

from PySide6.QtCore import QObject, Signal, Slot, Qt, QTimer

from .dialogue import DialogueRequest
from .controller import HostDialogueStaleError
from .desktop_dialogue_service import DesktopDialogueService
from .host_auth import AuthenticationError, DeviceCredentials
from .memory_album_controller import MemoryAlbumStaleError
from .plugin_enabled_controller import PluginEnabledCompanionController


class HostError(ValueError):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status


class CompanionHost(QObject):
    dispatch = Signal(object)
    snapshot_changed = Signal(object)

    def __init__(self, controller: PluginEnabledCompanionController, credentials: DeviceCredentials):
        super().__init__()
        if not isinstance(controller, PluginEnabledCompanionController):
            raise TypeError("host requires the existing plugin-enabled controller")
        self.controller, self.credentials = controller, credentials
        self._thread = threading.get_ident()
        self._session_id = uuid4().hex
        self._version = None
        self._revision = 0
        self._events = []
        self._requests = {}
        self._active = None
        self._closed = False
        self._dialogue = DesktopDialogueService(controller, self)
        self._dialogue.memory_committed.connect(self._memory_committed)
        self.dispatch.connect(self._execute, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._sync)
        self._timer.start()
        self._sync()

    def _owner_thread(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError("host operation requires the controller owner thread")

    def create_invitation(self):
        self._owner_thread()
        return self.credentials.invite(owner_id=self.controller.story_runtime.memory.owner_id,
                                       character_ids=[self.controller.state.character_id])

    def revoke_device(self, device_id):
        self._owner_thread()
        self.credentials.revoke(device_id)
        if self._active is not None and self._active[0] == device_id:
            self._dialogue.cancel()
        for key, item in self._requests.items():
            if key[0] == device_id:
                item["result"] = {"request_id": key[1], "status": "revoked"}
        self._sync()

    def submit(self, token, action, payload=None):
        future = Future()
        self.dispatch.emit((future, lambda: self._command(token, action, payload or {})))
        return future

    @Slot(object)
    def _execute(self, work):
        future, operation = work
        if not future.set_running_or_notify_cancel():
            return
        try:
            future.set_result(operation())
        except Exception as exc:
            future.set_exception(exc)

    def _identity(self, token):
        try:
            identity = self.credentials.authenticate(token)
        except AuthenticationError as exc:
            raise HostError("unauthorized", "device credential expired or revoked", 401) from exc
        memory = self.controller.story_runtime.memory
        if identity.owner_id != memory.owner_id or self.controller.state.character_id not in identity.character_ids:
            raise HostError("character_forbidden", "device is not paired to the current character", 403)
        return identity

    def _sync(self, preserve_request=None):
        self._owner_thread()
        if self._closed:
            return
        c = self.controller
        c.story_runtime.memory.store.expire_memories(now=int(c.now))
        if c._memory_epoch_seen != c.story_runtime.memory.store.context_epoch:
            c._on_memory_invalidated()
        version = (c.state.character_id, c.story_runtime.memory.store.context_epoch,
                   c.host_context_generation)
        if self._version != version:
            self._version = version
            self._revision += 1
            for key, item in self._requests.items():
                if key != preserve_request:
                    item["result"] = {"request_id": key[1], "status": "stale"}
            self._events.append({"sequence": self._revision, "type": "context_invalidated",
                                 "character_id": version[0], "context_epoch": version[1],
                                 "clear_cached_content": True})
            self._events = self._events[-128:]
            self.snapshot_changed.emit(c.get_snapshot())

    def _session(self):
        return {"session_id": self._session_id, "revision": self._revision,
                "character_id": self._version[0], "context_epoch": self._version[1],
                "owner_id": self.controller.story_runtime.memory.owner_id,
                "capabilities": {"chat": True, "memory": True, "observations": False,
                                 "relay": False, "network_model_cancel": False}}

    def _require_version(self, payload):
        if payload.get("session_id") != self._session_id:
            raise HostError("session_changed", "host session changed; refresh before submitting")
        if payload.get("expected_epoch") != self._version[1]:
            raise HostError("stale_context", "stale context; refresh before submitting")
        if payload.get("expected_revision") is not None and payload["expected_revision"] != self._revision:
            raise HostError("stale_context", "stale session revision; refresh before submitting")

    def _command(self, token, action, payload):
        self._owner_thread()
        if self._closed:
            raise HostError("host_closed", "host is stopped", 503)
        identity = self._identity(token)
        self._sync()
        c = self.controller
        if action == "session":
            return self._session()
        if action == "events":
            cursor = payload.get("after", 0)
            return {**self._session(), "events": [e for e in self._events if e["sequence"] > cursor],
                    "resync_required": cursor > self._revision or cursor < self._events[0]["sequence"] - 1}
        if action == "memory":
            return {**self._session(), "album": c.memory_album_controller.snapshot(now=int(c.now))}
        if action == "source":
            return {**self._session(), "source": c.memory_album_controller.source_details(payload["memory_id"], now=int(c.now))}
        key = (identity.device_id, payload.get("request_id"))
        if action == "message_result":
            if key not in self._requests:
                raise HostError("request_not_found", "request not found in this host session", 404)
            return copy.deepcopy(self._requests[key]["result"])
        if action == "cancel":
            self._require_version(payload)
            if key not in self._requests:
                raise HostError("request_not_found", "request not found", 404)
            if self._active == key:
                self._dialogue.cancel()
                self._sync()
                self._requests[key]["result"] = {"request_id": key[1], "status": "cancelled",
                                                 "remote_compute_cancelled": False}
            return copy.deepcopy(self._requests[key]["result"])
        digest = sha256(json.dumps([action, payload], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if key in self._requests:
            item = self._requests[key]
            if item["digest"] != digest:
                raise HostError("request_conflict", "request_id already used with different content")
            if item["result"]["status"] == "stale":
                raise HostError("stale_context", "stale request; refresh before submitting")
            return copy.deepcopy(item["result"])
        self._require_version(payload)
        if len(self._requests) >= 2048:
            raise HostError("session_capacity", "host session request capacity reached", 429)
        if action == "message":
            if self._active is not None:
                raise HostError("session_busy", "another reply is still running")
            result = {**self._session(), "request_id": key[1], "status": "running",
                      "input_version": self._revision, "committed_version": None}
            self._requests[key] = {"digest": digest, "result": result}
            self._active = key
            try:
                worker = self._dialogue.submit(DialogueRequest(payload["text"], source="mobile"))
            except Exception:
                self._active = None
                self._requests.pop(key)
                raise
            self._requests[key]["worker"] = worker
            worker.add_done_callback(lambda done: self.dispatch.emit(
                (Future(), lambda: self._finish(key, token, done))))
            return copy.deepcopy(self._requests[key]["result"])
        if action != "memory_edit":
            raise HostError("unknown_operation", "unsupported operation", 400)
        album = c.memory_album_controller
        input_version = self._revision
        common = {"now": int(c.now), "expected_epoch": payload["expected_epoch"]}
        operation = payload["operation"]
        try:
            if operation == "remember":
                result = album.remember_explicit(payload["text"], **common)
            elif operation == "confirm":
                result = album.confirm_pending(payload["pending_id"], **common)
            elif operation == "correct":
                result = album.correct(payload["memory_id"], title=payload.get("title", ""),
                                       summary=payload["text"], **common)
            elif operation == "forget":
                result = album.forget(payload["memory_id"], **common)
            else:
                raise HostError("unknown_operation", "unsupported memory operation", 400)
        except MemoryAlbumStaleError as exc:
            raise HostError("stale_context", "stale memory album; refresh") from exc
        self._sync()
        result = {**self._session(), "request_id": key[1], "status": "completed", "album": result,
                  "input_version": input_version, "committed_version": self._revision}
        self._requests[key] = {"digest": digest, "result": result}
        self.snapshot_changed.emit(c.get_snapshot())
        return copy.deepcopy(result)

    @Slot(object)
    def _memory_committed(self, worker):
        self._owner_thread()
        key = self._active
        if key is None or self._requests[key].get("worker") is not worker:
            return
        self._sync(preserve_request=key)
        self._requests[key]["result"].update(committed_version=self._revision,
            context_epoch=self._version[1], revision=self._revision)

    def _finish(self, key, token, worker):
        self._owner_thread()
        try:
            self._identity(token)
        except HostError:
            self._active = None
            return
        try:
            worker.result()
            self._sync()
            previous = self._requests[key]["result"]
            if previous["status"] in {"stale", "revoked", "cancelled"}:
                return
            meta = worker.dialogue_metadata
            self._requests[key]["result"] = {**self._session(), "request_id": key[1], "status": "completed",
                "input_version": previous["input_version"], "committed_version": previous["committed_version"],
                "events": meta["events"], "expression_mode": meta["expression_mode"],
                "fallback_reason": meta["fallback_reason"]}
            self.snapshot_changed.emit(self.controller.get_snapshot())
        except Exception as exc:
            if self._requests[key]["result"]["status"] not in {"stale", "revoked", "cancelled"}:
                self._requests[key]["result"] = {"request_id": key[1],
                    "status": "cancelled" if isinstance(exc, (CancelledError, HostDialogueStaleError)) else "failed",
                    "error": type(exc).__name__}
        finally:
            self._active = None

    def close(self):
        self._owner_thread()
        self._dialogue.close()
        self._closed = True
        self._timer.stop()
