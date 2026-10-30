"""Opt-in, transient observations for a future authenticated device adapter.

This module does not capture a device, authenticate a network peer, grant an OS
permission, schedule work, or write memory. A trusted host calls ``grant`` only
after the user selects capabilities/apps. Its tickets fence already-authorized
collector sessions; they are not a replacement for transport authentication.

Before sending a snapshot to a model AND before presenting a derived result,
the host must call ``is_current``. The desktop conversation/history/TTS pipeline
is deliberately not auto-wired: its derived history needs the same revocation
contract before passive phone context may be enabled there.
"""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
import json
from threading import RLock
from uuid import uuid4


OBSERVATION_KINDS = frozenset({
    "user_share", "app_activity", "notification", "accessibility_text", "screen_summary",
})
MAX_BUFFERED_OBSERVATIONS = 24
MAX_CONTEXT_OBSERVATIONS = 2
MAX_CONTEXT_CHARACTERS = 2100


def _text(value: str, field: str, limit: int, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > limit:
        raise ValueError(f"invalid {field}")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"control character in {field}")
    return value


def _integer(value: int, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"invalid {field}")
    return value


@dataclass(frozen=True, slots=True)
class ObservationPolicy:
    kinds: frozenset[str] = frozenset()
    allowed_apps: frozenset[str] = frozenset()
    retention_seconds: int = 300

    def __post_init__(self) -> None:
        if isinstance(self.kinds, str) or isinstance(self.allowed_apps, str):
            raise ValueError("kinds and allowed_apps must be collections")
        object.__setattr__(self, "kinds", frozenset(self.kinds))
        object.__setattr__(self, "allowed_apps", frozenset(self.allowed_apps))
        if not self.kinds <= OBSERVATION_KINDS:
            raise ValueError("unsupported observation kind")
        if len(self.allowed_apps) > 100:
            raise ValueError("too many allowed apps")
        for app in self.allowed_apps:
            _text(app, "app_id", 160)
        _integer(self.retention_seconds, "retention_seconds", minimum=1)
        if self.retention_seconds > 3600:
            raise ValueError("retention_seconds exceeds one hour")


@dataclass(frozen=True, slots=True)
class ObservationTicket:
    device_id: str
    token: str
    memory_epoch: int


@dataclass(frozen=True, slots=True)
class Observation:
    event_id: str
    device_id: str
    owner_id: str
    character_id: str
    kind: str
    app_id: str
    captured_at: int
    text: str
    source_method: str
    grant_token: str
    memory_epoch: int
    sensitive: bool = False
    schema_version: int = 1

    def __post_init__(self) -> None:
        for field in ("event_id", "device_id", "owner_id", "character_id", "source_method", "grant_token"):
            _text(getattr(self, field), field, 120)
        _text(self.app_id, "app_id", 160, empty=self.kind == "user_share")
        _text(self.text, "text", 360, empty=True)
        _integer(self.captured_at, "captured_at")
        _integer(self.memory_epoch, "memory_epoch")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported observation schema")
        if self.kind not in OBSERVATION_KINDS or type(self.sensitive) is not bool:
            raise ValueError("invalid observation kind/sensitivity")
        if self.kind == "app_activity" and self.text:
            raise ValueError("app_activity may carry app usage metadata, not screen/chat text")


class DeviceContextBuffer:
    """Bounded RAM only. Scope identifiers are asserted by an authenticated host.

    ``now`` and capture timestamps are Unix seconds, not the desktop pet's game
    clock. At most five seconds of device clock skew is accepted. The host must
    call ``advance_memory_epoch`` when its authoritative memory epoch changes.
    """

    def __init__(self, *, owner_id: str, character_id: str, memory_epoch: int) -> None:
        self._owner_id = _text(owner_id, "owner_id", 120)
        self._character_id = _text(character_id, "character_id", 120)
        self._memory_epoch = _integer(memory_epoch, "memory_epoch")
        self._session_id = uuid4().hex
        self._revision = 0
        self._grants: dict[str, tuple[ObservationTicket, ObservationPolicy]] = {}
        self._events: OrderedDict[tuple[str, str], tuple[Observation, int]] = OrderedDict()
        self._lock = RLock()
        self._closed = False

    @property
    def owner_id(self) -> str:
        return self._owner_id

    @property
    def character_id(self) -> str:
        return self._character_id

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._events)

    def grant(self, device_id: str, policy: ObservationPolicy) -> ObservationTicket:
        """Trusted host/user action, never a field accepted from observed text."""
        _text(device_id, "device_id", 120)
        if not isinstance(policy, ObservationPolicy):
            raise ValueError("ObservationPolicy required")
        with self._lock:
            if self._closed:
                raise ValueError("observation buffer is closed")
            self._drop_device(device_id)
            ticket = ObservationTicket(device_id, uuid4().hex, self._memory_epoch)
            self._grants[device_id] = (ticket, policy)
            self._revision += 1
            return ticket

    def ticket(self, device_id: str) -> ObservationTicket:
        """Host reissues this after epoch changes, under existing user consent."""
        with self._lock:
            return self._grants[device_id][0]

    def revoke(self, device_id: str) -> None:
        with self._lock:
            if device_id in self._grants:
                del self._grants[device_id]
                self._drop_device(device_id)
                self._revision += 1

    def advance_memory_epoch(self, epoch: int) -> None:
        _integer(epoch, "memory_epoch")
        with self._lock:
            if epoch < self._memory_epoch:
                raise ValueError("memory epoch cannot go backwards")
            if epoch == self._memory_epoch:
                return
            self._memory_epoch = epoch
            self._events.clear()
            self._revision += 1
            self._grants = {device: (ObservationTicket(device, uuid4().hex, epoch), policy)
                            for device, (_, policy) in self._grants.items()}

    def ingest(self, observation: Observation, *, now: int) -> bool:
        _integer(now, "now")
        if not isinstance(observation, Observation):
            raise ValueError("Observation required")
        with self._lock:
            self._expire(now)
            grant = self._grants.get(observation.device_id)
            if self._closed or grant is None:
                return False
            ticket, policy = grant
            if (observation.owner_id != self.owner_id or observation.character_id != self.character_id
                    or observation.grant_token != ticket.token
                    or observation.memory_epoch != self._memory_epoch
                    or observation.kind not in policy.kinds or observation.sensitive):
                return False
            if observation.kind != "user_share" and observation.app_id not in policy.allowed_apps:
                return False
            expires_at = observation.captured_at + policy.retention_seconds
            if observation.captured_at > now + 5 or expires_at <= now:
                return False
            key = (observation.device_id, observation.event_id)
            existing = self._events.get(key)
            if existing is not None:
                if existing[0] != observation:
                    raise ValueError("observation event_id conflict")
                return False
            self._events[key] = (observation, expires_at)
            while len(self._events) > MAX_BUFFERED_OBSERVATIONS:
                self._events.popitem(last=False)
            return True

    def context(self, *, now: int) -> dict[str, object]:
        """Return a data-only snapshot; caller decides if/where to use it."""
        _integer(now, "now")
        with self._lock:
            self._expire(now)
            rows = sorted(self._events.values(), key=lambda item: item[0].captured_at,
                          reverse=True)[:MAX_CONTEXT_OBSERVATIONS]
            while rows:
                result = self._view(rows)
                if len(json.dumps(result, ensure_ascii=False, separators=(",", ":"))) <= MAX_CONTEXT_CHARACTERS:
                    return result
                rows.pop()
            return {}

    def is_current(self, view: Mapping[str, object], *, now: int) -> bool:
        """Use both before model dispatch and before displaying its result.

        This cannot recall data already sent to a model, erase a caller's copied
        chat history, or stop audio. Those consumers must implement revocation.
        """
        _integer(now, "now")
        if not isinstance(view, Mapping) or not view:
            return False
        with self._lock:
            self._expire(now)
            observations = view.get("observations")
            if not isinstance(observations, list) or not 1 <= len(observations) <= MAX_CONTEXT_OBSERVATIONS:
                return False
            rows = []
            seen = set()
            for item in observations:
                if not isinstance(item, Mapping):
                    return False
                device_id, event_id = item.get("device_id"), item.get("event_id")
                if not isinstance(device_id, str) or not isinstance(event_id, str):
                    return False
                key = (device_id, event_id)
                if key in seen or key not in self._events:
                    return False
                seen.add(key)
                rows.append(self._events[key])
            return dict(view) == self._view(rows)

    def close(self) -> None:
        with self._lock:
            self._grants.clear()
            self._events.clear()
            self._revision += 1
            self._closed = True

    def _drop_device(self, device_id: str) -> None:
        for key in tuple(self._events):
            if key[0] == device_id:
                del self._events[key]

    def _expire(self, now: int) -> None:
        expired = [key for key, (_, expires) in self._events.items() if expires <= now]
        for key in expired:
            del self._events[key]
        # is_current checks the actual rows included in a snapshot. Expiring an
        # unused row must not cancel a response about other, still-valid rows.

    def _view(self, rows: list[tuple[Observation, int]]) -> dict[str, object]:
        return {
            "schema_version": 1,
            "owner_id": self.owner_id,
            "character_id": self.character_id,
            "context_epoch": self._memory_epoch,
            "view_token": f"{self._session_id}:{self._revision}",
            "scope": "observation",
            "trust": "untrusted_observation",
            "memory_write_allowed": False,
            "valid_until": min(expires for _, expires in rows),
            "observations": [
                {"event_id": row.event_id, "device_id": row.device_id, "kind": row.kind,
                 "app_id": row.app_id, "captured_at": row.captured_at, "expires_at": expires,
                 "source_method": row.source_method, "text": row.text}
                for row, expires in rows
            ],
        }
