from __future__ import annotations

"""Redacted append-only journal for plugin lifecycle and failures."""

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import time

_SECRET_KEYS = {"api_key", "apikey", "authorization", "token", "access_token", "password", "secret", "client_secret", "vision_api_key"}


def redact(value: object) -> object:
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, child in value.items():
            name = str(key)
            normalized = name.lower().replace("-", "_")
            result[name] = "[REDACTED]" if normalized in _SECRET_KEYS and str(child).strip() else redact(child)
        return result
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        text = " ".join(value.split())
        return text[:2000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


@dataclass(slots=True)
class PluginJournal:
    path: Path | str
    max_bytes: int = 2 * 1024 * 1024

    def append(self, event_type: str, *, plugin_id: str = "", payload: Mapping[str, object] | None = None, now: int | None = None) -> None:
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._rotate_if_needed(target)
        row = {
            "schema_version": 1,
            "at": int(time.time() if now is None else now),
            "event_type": str(event_type)[:120],
            "plugin_id": str(plugin_id)[:100],
            "payload": redact(dict(payload or {})),
        }
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    def tail(self, limit: int = 100) -> tuple[dict[str, object], ...]:
        target = Path(self.path)
        if not target.exists():
            return ()
        try:
            lines = target.read_text(encoding="utf-8-sig").splitlines()[-max(1, min(int(limit), 500)):]
        except (OSError, UnicodeDecodeError):
            return ()
        rows: list[dict[str, object]] = []
        for line in lines:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
        return tuple(rows)

    def clear(self) -> None:
        Path(self.path).unlink(missing_ok=True)

    def _rotate_if_needed(self, target: Path) -> None:
        try:
            if target.stat().st_size < self.max_bytes:
                return
        except FileNotFoundError:
            return
        backup = target.with_suffix(target.suffix + ".1")
        backup.unlink(missing_ok=True)
        target.replace(backup)
