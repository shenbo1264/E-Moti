from __future__ import annotations

"""Failure tracking and quarantine state for E-Moti plugins."""

from dataclasses import dataclass, replace
import json
from pathlib import Path
import time
from typing import Mapping

DEFAULT_QUARANTINE_THRESHOLD = 3


def _clean(value: object, limit: int = 400) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join("".join(" " if ord(ch) < 32 or ord(ch) == 127 else ch for ch in value).split())[:limit]


@dataclass(frozen=True, slots=True)
class PluginHealthStatus:
    plugin_id: str
    consecutive_failures: int = 0
    quarantined: bool = False
    last_error_type: str = ""
    last_error: str = ""
    last_failure_at: int = 0
    last_success_at: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "consecutive_failures": self.consecutive_failures,
            "quarantined": self.quarantined,
            "last_error_type": self.last_error_type,
            "last_error": self.last_error,
            "last_failure_at": self.last_failure_at,
            "last_success_at": self.last_success_at,
        }

    @classmethod
    def from_dict(cls, plugin_id: str, value: object) -> "PluginHealthStatus":
        row = value if isinstance(value, Mapping) else {}
        return cls(
            plugin_id=plugin_id,
            consecutive_failures=max(0, int(row.get("consecutive_failures", 0) or 0)),
            quarantined=bool(row.get("quarantined", False)),
            last_error_type=_clean(row.get("last_error_type"), 100),
            last_error=_clean(row.get("last_error"), 400),
            last_failure_at=max(0, int(row.get("last_failure_at", 0) or 0)),
            last_success_at=max(0, int(row.get("last_success_at", 0) or 0)),
        )


class PluginHealthStore:
    def __init__(self, path: Path | str, *, quarantine_threshold: int = DEFAULT_QUARANTINE_THRESHOLD) -> None:
        self.path = Path(path)
        self.quarantine_threshold = max(1, int(quarantine_threshold))
        self._rows = self._load()

    def status(self, plugin_id: str) -> PluginHealthStatus:
        return self._rows.get(plugin_id, PluginHealthStatus(plugin_id))

    def all(self) -> tuple[PluginHealthStatus, ...]:
        return tuple(sorted(self._rows.values(), key=lambda row: row.plugin_id))

    def record_success(self, plugin_id: str, *, now: int | None = None) -> PluginHealthStatus:
        current = self.status(plugin_id)
        row = replace(
            current,
            consecutive_failures=0,
            last_error_type="",
            last_error="",
            last_success_at=int(time.time() if now is None else now),
        )
        self._rows[plugin_id] = row
        self._save()
        return row

    def record_failure(self, plugin_id: str, error: BaseException | str, *, now: int | None = None) -> PluginHealthStatus:
        current = self.status(plugin_id)
        count = current.consecutive_failures + 1
        error_type = type(error).__name__ if isinstance(error, BaseException) else "PluginError"
        message = str(error)
        row = replace(
            current,
            consecutive_failures=count,
            quarantined=current.quarantined or count >= self.quarantine_threshold,
            last_error_type=_clean(error_type, 100),
            last_error=_clean(message, 400),
            last_failure_at=int(time.time() if now is None else now),
        )
        self._rows[plugin_id] = row
        self._save()
        return row

    def clear_quarantine(self, plugin_id: str) -> PluginHealthStatus:
        current = self.status(plugin_id)
        row = replace(current, quarantined=False, consecutive_failures=0, last_error_type="", last_error="")
        self._rows[plugin_id] = row
        self._save()
        return row

    def remove(self, plugin_id: str) -> None:
        self._rows.pop(plugin_id, None)
        self._save()

    def _load(self) -> dict[str, PluginHealthStatus]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        rows = payload.get("plugins", {}) if isinstance(payload, Mapping) else {}
        if not isinstance(rows, Mapping):
            return {}
        return {str(plugin_id): PluginHealthStatus.from_dict(str(plugin_id), value) for plugin_id, value in rows.items()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, "plugins": {row.plugin_id: row.to_dict() for row in self.all()}}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)
