"""One transactional local memory document; legacy JSON is migration input only.

SQLite is used for crash-safe commits and process locking, not vector search.
All content and its revocation metadata commit together, including on Windows.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import sqlite3
from typing import Callable, Iterator


class MemoryStorageError(RuntimeError):
    """The authoritative store cannot be read; never fall back to old facts."""


def _reject_json_constant(value: str) -> None:
    raise MemoryStorageError(f"Non-finite JSON number {value}; refusing lossy memory normalization")


def _finite_json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        _reject_json_constant(value)
    return number


def _strict_json_loads(value: str) -> object:
    return json.loads(value, parse_constant=_reject_json_constant, parse_float=_finite_json_float)


def _validate_document(document: object) -> None:
    if not isinstance(document, dict) or document.get("schema_version") != 2:
        raise MemoryStorageError("Unsupported or invalid memory state; original files were not changed")


def _write_initialization_receipt(path: Path) -> None:
    """Persist only initialization metadata, never facts or an owner profile."""
    try:
        with path.open("x", encoding="ascii") as stream:
            stream.write('{"schema_version":2,"initialized":true}\n')
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        pass


@contextmanager
def memory_document(path: Path, initial: Callable[[], dict]) -> Iterator[dict]:
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = path.with_suffix(".initialized")
    database_existed = path.exists()
    if receipt.exists() and not database_existed:
        raise MemoryStorageError("Initialized memory database is missing; refusing legacy fallback")
    # Validate migration input before creating a database. A failed first import
    # leaves no misleading empty SQLite file and can be fixed and retried.
    initial_payload = None
    if not database_existed:
        initial_document = initial()
        _validate_document(initial_document)
        initial_payload = json.dumps(initial_document, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    connection = None
    try:
        connection = sqlite3.connect(path, timeout=5, isolation_level=None)
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("BEGIN IMMEDIATE")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 2):
            raise MemoryStorageError("Unsupported memory database version; refusing legacy fallback")
        has_table = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_state'").fetchone()
        if not has_table:
            if database_existed or receipt.exists() or version != 0:
                raise MemoryStorageError("Authoritative memory table is missing; refusing legacy fallback")
            connection.execute("CREATE TABLE memory_state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
            connection.execute("INSERT INTO memory_state(id,payload) VALUES(1,?)", (initial_payload,))
            connection.execute("PRAGMA user_version = 2")
            # Receipt precedes the first commit. A crash here fails closed on
            # retry instead of silently replaying retained legacy JSON files.
            _write_initialization_receipt(receipt)
            connection.commit()
            version = 2
            connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT payload FROM memory_state WHERE id=1").fetchone()
        if row is None:
            raise MemoryStorageError("Authoritative memory state is missing; refusing legacy fallback")
        before = row[0]
        document = _strict_json_loads(before)
        _validate_document(document)
        _write_initialization_receipt(receipt)
        if version != 2:
            connection.execute("PRAGMA user_version = 2")
        yield document
        after = json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        if after != before:
            connection.execute("INSERT INTO memory_state(id,payload) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", (after,))
        connection.commit()
    except (OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        if connection is not None:
            connection.rollback()
        raise MemoryStorageError("Cannot read authoritative memory state; refusing legacy fallback") from exc
    except BaseException:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if connection is not None:
            connection.close()


def read_legacy_json(path: Path) -> object:
    if not path.exists():
        return {}
    try:
        return _strict_json_loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MemoryStorageError(f"Cannot migrate {path.name}; source file was not changed") from exc
