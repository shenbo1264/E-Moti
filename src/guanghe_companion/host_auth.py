from dataclasses import dataclass
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import secrets
import sqlite3
import time
import json
from uuid import uuid4


class AuthenticationError(ValueError):
    pass


@dataclass(frozen=True)
class DeviceIdentity:
    device_id: str
    owner_id: str
    character_ids: tuple[str, ...]


class DeviceCredentials:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS invitations (
                    digest TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    characters TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL, owner TEXT NOT NULL, characters TEXT NOT NULL,
                    expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def invite(self, *, owner_id: str, character_ids: list[str], now=None) -> str:
        if not owner_id or not character_ids or any(not c for c in character_ids):
            raise ValueError("pairing requires a host owner and permitted characters")
        token = secrets.token_urlsafe(32)
        timestamp = time.time() if now is None else now
        with self._connect() as db:
            db.execute("DELETE FROM invitations WHERE expires <= ?", (timestamp,))
            db.execute("INSERT INTO invitations VALUES (?, ?, ?, ?)",
                       (_digest(token), owner_id, json.dumps(character_ids), timestamp + 300))
        return token

    def pair(self, invitation: str, *, device_name: str, now=None) -> dict:
        timestamp = time.time() if now is None else now
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT owner, characters, expires FROM invitations WHERE digest = ?",
                             (_digest(invitation),)).fetchone()
            if row is None or row[2] <= timestamp:
                raise AuthenticationError("invalid or expired invitation")
            db.execute("DELETE FROM invitations WHERE digest = ?", (_digest(invitation),))
            token, device_id = secrets.token_urlsafe(32), uuid4().hex
            expires = timestamp + 30 * 86400
            db.execute("INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, 0)",
                       (device_id, _digest(token), device_name, row[0], row[1], expires))
        return {"access_token": token, "token_type": "bearer", "device_id": device_id,
                "expires_at": expires}

    def authenticate(self, token: str, *, now=None) -> DeviceIdentity:
        timestamp = time.time() if now is None else now
        with self._connect() as db:
            row = db.execute("SELECT device_id, owner, characters, expires, revoked FROM devices WHERE digest = ?",
                             (_digest(token),)).fetchone()
        if row is None or row[4] or row[3] <= timestamp:
            raise AuthenticationError("invalid, expired or revoked device credential")
        return DeviceIdentity(row[0], row[1], tuple(json.loads(row[2])))

    def revoke(self, device_id: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE devices SET revoked = 1 WHERE device_id = ?", (device_id,))


def _digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
