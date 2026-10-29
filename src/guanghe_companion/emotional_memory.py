from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Mapping

CURRENT_EMOTIONAL_MEMORY_SCHEMA_VERSION = 2
MAX_EMOTIONAL_MEMORY_ENTRIES = 300
MAX_MEMORY_TEXT_LENGTH = 240
MAX_MEMORY_TITLE_LENGTH = 60
MAX_MEMORY_TAGS = 8
MAX_SOURCE_IDS = 8


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _clean_text(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    normalized = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value)
    return " ".join(normalized.strip().split())[:max_length]


def _clean_timestamp(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _clean_string_sequence(value: object, *, limit: int, item_length: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for raw in value:
        item = _clean_text(raw, item_length)
        if not item or item in seen:
            continue
        result.append(item)
        seen.add(item)
        if len(result) >= limit:
            break
    return tuple(result)


def make_memory_id(*parts: object) -> str:
    normalized = "|".join(str(part) for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True, slots=True)
class EmotionalSignal:
    label: str = "平静"
    valence: float = 0.0
    intensity: float = 0.0

    def normalized(self) -> "EmotionalSignal":
        return EmotionalSignal(
            label=_clean_text(self.label, 24) or "平静",
            valence=max(-1.0, min(1.0, float(self.valence))),
            intensity=_clamp(self.intensity),
        )

    def to_dict(self) -> dict[str, object]:
        signal = self.normalized()
        return {
            "label": signal.label,
            "valence": signal.valence,
            "intensity": signal.intensity,
        }

    @classmethod
    def from_dict(cls, value: object) -> "EmotionalSignal":
        if not isinstance(value, Mapping):
            return cls()
        try:
            valence = float(value.get("valence", 0.0))
        except (TypeError, ValueError):
            valence = 0.0
        try:
            intensity = float(value.get("intensity", 0.0))
        except (TypeError, ValueError):
            intensity = 0.0
        return cls(
            label=_clean_text(value.get("label"), 24) or "平静",
            valence=valence,
            intensity=intensity,
        ).normalized()


@dataclass(frozen=True, slots=True)
class EmotionalMemoryEntry:
    memory_id: str
    character_id: str
    owner_id: str
    kind: str
    title: str
    summary: str
    source: str
    occurred_at: int
    created_at: int
    updated_at: int
    source_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    emotion: EmotionalSignal = field(default_factory=EmotionalSignal)
    importance: float = 0.5
    relationship_delta: float = 0.0
    access_count: int = 0
    last_accessed_at: int = 0
    pinned: bool = False
    user_confirmed: bool = False
    deleted: bool = False
    supersedes: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    scope: str = "companion"
    confidence: float = 1.0
    valid_from: int = 0
    valid_until: int = 0
    version: int = 1

    def normalized(self) -> "EmotionalMemoryEntry":
        # Validate before clamping/cleaning: NaN confidence must not become 1,
        # and a malformed expiry must never become the no-expiry sentinel 0.
        for name in ("confidence", "valid_from", "valid_until"):
            value = getattr(self, name)
            try:
                finite = math.isfinite(float(value))
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"memory {name} must be finite") from exc
            if isinstance(value, bool) or not finite:
                raise ValueError(f"memory {name} must be finite")
        return EmotionalMemoryEntry(
            memory_id=_clean_text(self.memory_id, 80),
            character_id=_clean_text(self.character_id, 80),
            owner_id=_clean_text(self.owner_id, 80) or "local_user",
            kind=_clean_text(self.kind, 40),
            title=_clean_text(self.title, MAX_MEMORY_TITLE_LENGTH),
            summary=_clean_text(self.summary, MAX_MEMORY_TEXT_LENGTH),
            source=_clean_text(self.source, 40),
            occurred_at=_clean_timestamp(self.occurred_at),
            created_at=_clean_timestamp(self.created_at),
            updated_at=_clean_timestamp(self.updated_at),
            source_ids=_clean_string_sequence(self.source_ids, limit=MAX_SOURCE_IDS, item_length=80),
            tags=_clean_string_sequence(self.tags, limit=MAX_MEMORY_TAGS, item_length=32),
            emotion=self.emotion.normalized(),
            importance=_clamp(self.importance),
            relationship_delta=max(-1.0, min(1.0, float(self.relationship_delta))),
            access_count=max(0, int(self.access_count)),
            last_accessed_at=_clean_timestamp(self.last_accessed_at),
            pinned=bool(self.pinned),
            user_confirmed=bool(self.user_confirmed),
            deleted=bool(self.deleted),
            supersedes=_clean_text(self.supersedes, 80),
            metadata=_sanitize_metadata(self.metadata),
            scope=_clean_text(self.scope, 40) or "companion",
            confidence=_clamp(self.confidence),
            valid_from=_clean_timestamp(self.valid_from),
            valid_until=_clean_timestamp(self.valid_until),
            version=max(1, int(self.version)),
        )

    def validate(self) -> None:
        memory = self.normalized()
        required = (
            memory.memory_id,
            memory.character_id,
            memory.owner_id,
            memory.kind,
            memory.title,
            memory.summary,
            memory.source,
        )
        if not all(required):
            raise ValueError("emotional memory requires id, character, owner, kind, title, summary, and source")
        if memory.valid_until and memory.valid_until <= memory.valid_from:
            raise ValueError("memory validity interval must have positive duration")

    def is_active(self, *, now: int, scope: str = "companion") -> bool:
        return (not self.deleted and self.scope == scope and self.confidence > 0
                and self.valid_from <= now and (not self.valid_until or now < self.valid_until))

    def evidence_fingerprint(self) -> str:
        """Content revision, independent of access counters and retrieval touches."""
        fields = (self.memory_id, self.character_id, self.owner_id, self.kind,
                  self.title, self.summary, self.source, self.source_ids, self.tags,
                  self.occurred_at, self.scope, self.confidence, self.valid_from,
                  self.valid_until, self.version)
        return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode("utf-8")).hexdigest()

    def touch(self, now: int) -> "EmotionalMemoryEntry":
        timestamp = _clean_timestamp(now)
        return replace(
            self,
            access_count=self.access_count + 1,
            last_accessed_at=timestamp,
            updated_at=max(self.updated_at, timestamp),
        )

    def to_dict(self) -> dict[str, object]:
        memory = self.normalized()
        memory.validate()
        return {
            "memory_id": memory.memory_id,
            "character_id": memory.character_id,
            "owner_id": memory.owner_id,
            "kind": memory.kind,
            "title": memory.title,
            "summary": memory.summary,
            "source": memory.source,
            "occurred_at": memory.occurred_at,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "source_ids": list(memory.source_ids),
            "tags": list(memory.tags),
            "emotion": memory.emotion.to_dict(),
            "importance": memory.importance,
            "relationship_delta": memory.relationship_delta,
            "access_count": memory.access_count,
            "last_accessed_at": memory.last_accessed_at,
            "pinned": memory.pinned,
            "user_confirmed": memory.user_confirmed,
            "deleted": memory.deleted,
            "supersedes": memory.supersedes,
            "metadata": memory.metadata,
            "scope": memory.scope,
            "confidence": memory.confidence,
            "valid_from": memory.valid_from,
            "valid_until": memory.valid_until,
            "version": memory.version,
        }

    @classmethod
    def from_dict(cls, value: object) -> "EmotionalMemoryEntry | None":
        if not isinstance(value, Mapping):
            return None
        try:
            memory = cls(
                memory_id=_clean_text(value.get("memory_id"), 80),
                character_id=_clean_text(value.get("character_id"), 80),
                owner_id=_clean_text(value.get("owner_id"), 80) or "local_user",
                kind=_clean_text(value.get("kind"), 40),
                title=_clean_text(value.get("title"), MAX_MEMORY_TITLE_LENGTH),
                summary=_clean_text(value.get("summary"), MAX_MEMORY_TEXT_LENGTH),
                source=_clean_text(value.get("source"), 40),
                occurred_at=_clean_timestamp(value.get("occurred_at")),
                created_at=_clean_timestamp(value.get("created_at")),
                updated_at=_clean_timestamp(value.get("updated_at")),
                source_ids=_clean_string_sequence(value.get("source_ids"), limit=MAX_SOURCE_IDS, item_length=80),
                tags=_clean_string_sequence(value.get("tags"), limit=MAX_MEMORY_TAGS, item_length=32),
                emotion=EmotionalSignal.from_dict(value.get("emotion")),
                importance=float(value.get("importance", 0.5)),
                relationship_delta=float(value.get("relationship_delta", 0.0)),
                access_count=int(value.get("access_count", 0)),
                last_accessed_at=_clean_timestamp(value.get("last_accessed_at")),
                pinned=bool(value.get("pinned", False)),
                user_confirmed=bool(value.get("user_confirmed", False)),
                deleted=bool(value.get("deleted", False)),
                supersedes=_clean_text(value.get("supersedes"), 80),
                metadata=_sanitize_metadata(value.get("metadata")),
                scope=_clean_text(value.get("scope"), 40) or "companion",
                confidence=float(value.get("confidence", 1.0)),
                valid_from=value.get("valid_from", 0),
                valid_until=value.get("valid_until", 0),
                version=max(1, int(value.get("version", 1))),
            ).normalized()
            memory.validate()
            return memory
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True, slots=True)
class CoreBondProfile:
    character_id: str
    owner_id: str = "local_user"
    player_alias: str = ""
    relationship_stage: str = "初识"
    stable_preferences: tuple[str, ...] = ()
    boundaries: tuple[str, ...] = ()
    shared_rituals: tuple[str, ...] = ()
    active_story_threads: tuple[str, ...] = ()
    updated_at: int = 0
    # Each key is "field:value". Values are source id -> content fingerprint.
    evidence: dict[str, dict[str, str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "character_id": _clean_text(self.character_id, 80),
            "owner_id": _clean_text(self.owner_id, 80) or "local_user",
            "player_alias": _clean_text(self.player_alias, 20),
            "relationship_stage": _clean_text(self.relationship_stage, 40) or "初识",
            "stable_preferences": list(_clean_string_sequence(self.stable_preferences, limit=12, item_length=80)),
            "boundaries": list(_clean_string_sequence(self.boundaries, limit=12, item_length=100)),
            "shared_rituals": list(_clean_string_sequence(self.shared_rituals, limit=8, item_length=100)),
            "active_story_threads": list(
                _clean_string_sequence(self.active_story_threads, limit=8, item_length=120)
            ),
            "updated_at": _clean_timestamp(self.updated_at),
            "evidence": _clean_evidence(self.evidence),
        }

    @classmethod
    def from_dict(cls, value: object, *, fallback_character_id: str = "") -> "CoreBondProfile":
        if not isinstance(value, Mapping):
            return cls(character_id=fallback_character_id)
        return cls(
            character_id=_clean_text(value.get("character_id"), 80) or fallback_character_id,
            owner_id=_clean_text(value.get("owner_id"), 80) or "local_user",
            player_alias=_clean_text(value.get("player_alias"), 20),
            relationship_stage=_clean_text(value.get("relationship_stage"), 40) or "初识",
            stable_preferences=_clean_string_sequence(value.get("stable_preferences"), limit=12, item_length=80),
            boundaries=_clean_string_sequence(value.get("boundaries"), limit=12, item_length=100),
            shared_rituals=_clean_string_sequence(value.get("shared_rituals"), limit=8, item_length=100),
            active_story_threads=_clean_string_sequence(
                value.get("active_story_threads"), limit=8, item_length=120
            ),
            updated_at=_clean_timestamp(value.get("updated_at")),
            evidence=_clean_evidence(value.get("evidence")),
        )


@dataclass(frozen=True, slots=True)
class MemoryChapter:
    chapter_id: str
    character_id: str
    title: str
    summary: str
    source_memory_ids: tuple[str, ...]
    created_at: int
    tags: tuple[str, ...] = ()
    source_fingerprints: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "chapter_id": _clean_text(self.chapter_id, 80),
            "character_id": _clean_text(self.character_id, 80),
            "title": _clean_text(self.title, 80),
            "summary": _clean_text(self.summary, 320),
            "source_memory_ids": list(
                _clean_string_sequence(self.source_memory_ids, limit=16, item_length=80)
            ),
            "created_at": _clean_timestamp(self.created_at),
            "tags": list(_clean_string_sequence(self.tags, limit=8, item_length=32)),
            "source_fingerprints": _clean_fingerprints(self.source_fingerprints),
        }

    @classmethod
    def from_dict(cls, value: object) -> "MemoryChapter | None":
        if not isinstance(value, Mapping):
            return None
        chapter = cls(
            chapter_id=_clean_text(value.get("chapter_id"), 80),
            character_id=_clean_text(value.get("character_id"), 80),
            title=_clean_text(value.get("title"), 80),
            summary=_clean_text(value.get("summary"), 320),
            source_memory_ids=_clean_string_sequence(
                value.get("source_memory_ids"), limit=16, item_length=80
            ),
            created_at=_clean_timestamp(value.get("created_at")),
            tags=_clean_string_sequence(value.get("tags"), limit=8, item_length=32),
            source_fingerprints=_clean_fingerprints(value.get("source_fingerprints")),
        )
        if not chapter.chapter_id or not chapter.character_id or not chapter.title or not chapter.summary:
            return None
        if not chapter.source_memory_ids:
            return None
        return chapter


@dataclass(frozen=True, slots=True)
class MemoryContextBundle:
    bond_profile: CoreBondProfile
    memories: tuple[EmotionalMemoryEntry, ...] = ()
    chapter: MemoryChapter | None = None
    context_epoch: int = 0

    def to_prompt_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "bond_profile": self.bond_profile.to_dict(),
            "context_epoch": self.context_epoch,
        }
        if self.memories:
            payload["shared_memories"] = [
                {
                    "memory_id": memory.memory_id,
                    "kind": memory.kind,
                    "title": memory.title,
                    "summary": memory.summary,
                    "emotion": memory.emotion.to_dict(),
                    "source": memory.source,
                    "source_ids": list(memory.source_ids),
                    "confidence": memory.confidence,
                    "version": memory.version,
                    "occurred_at": memory.occurred_at,
                    "valid_until": memory.valid_until,
                    "scope": memory.scope,
                }
                for memory in self.memories
            ]
        if self.chapter is not None:
            payload["relationship_chapter"] = self.chapter.to_dict()
        return payload

    def to_prompt_text(self) -> str:
        payload = self.to_prompt_payload()
        return json.dumps(payload, ensure_ascii=False, indent=2)


@dataclass(frozen=True, slots=True)
class EmotionalMemoryStore:
    """Existing public API backed by a single transactional lifecycle document.

    The old three JSON files remain untouched migration inputs. They are never
    consulted again after a successful SQLite commit, even if it later corrupts.
    """
    root: Path | str
    character_id: str
    owner_id: str = "local_user"
    max_entries: int = MAX_EMOTIONAL_MEMORY_ENTRIES

    @property
    def character_root(self) -> Path:
        from .character_session import is_safe_character_id
        if not is_safe_character_id(self.character_id):
            raise ValueError("unsafe memory character_id")
        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            raise ValueError("memory owner_id must be non-empty")
        base = Path(self.root) / "characters" / self.character_id
        if self.owner_id != "local_user":
            base = base / "owners" / hashlib.sha256(self.owner_id.encode("utf-8")).hexdigest()
        return base / "memory_v2"

    @property
    def memories_path(self) -> Path:
        """Read-only v1 migration source; use load_memories for current state."""
        return self.character_root / "emotional_memories.json"

    @property
    def profile_path(self) -> Path:
        return self.character_root / "bond_profile.json"

    @property
    def chapters_path(self) -> Path:
        return self.character_root / "memory_chapters.json"

    @property
    def state_path(self) -> Path:
        return self.character_root / "memory_state.sqlite3"

    def _document(self):
        from .memory_document import memory_document
        return memory_document(self.state_path, self._migrate_v1)

    def _migrate_v1(self) -> dict:
        from .memory_document import read_legacy_json, MemoryStorageError

        def read_source(path: Path) -> Mapping:
            # V1 used a shared character directory even for non-default owners.
            # Dedicated legacy files take precedence; shared files are read-only
            # migration input and every imported object is scoped below.
            if self.owner_id != "local_user" and not path.exists():
                path = Path(self.root) / "characters" / self.character_id / "memory_v2" / path.name
            payload = read_legacy_json(path)
            if not isinstance(payload, Mapping):
                raise MemoryStorageError(f"Invalid legacy document {path.name}; source file was not changed")
            if payload.get("schema_version", 1) not in (1, 2):
                raise MemoryStorageError("Unsupported legacy memory schema; refusing a lossy migration")
            return payload

        memories = read_source(self.memories_path)
        profile = read_source(self.profile_path)
        chapters = read_source(self.chapters_path)
        rows = memories.get("entries", [])
        if not isinstance(rows, list):
            raise MemoryStorageError("Legacy memory entries must be a list; refusing a lossy migration")
        entries = []
        for index, row in enumerate(rows):
            entry = EmotionalMemoryEntry.from_dict(row)
            if entry is None:
                raise MemoryStorageError(f"Invalid legacy memory row {index}; source file was not changed")
            if entry.character_id == self.character_id and entry.owner_id == self.owner_id:
                entries.append(entry)
        raw_profile = profile.get("profile")
        if raw_profile is not None and not isinstance(raw_profile, Mapping):
            raise MemoryStorageError("Invalid legacy profile; source file was not changed")
        bond = CoreBondProfile.from_dict(raw_profile, fallback_character_id=self.character_id)
        if bond.character_id != self.character_id or bond.owner_id != self.owner_id:
            bond = CoreBondProfile(self.character_id, self.owner_id)
        chapter_rows = chapters.get("chapters", [])
        if not isinstance(chapter_rows, list):
            raise MemoryStorageError("Legacy chapters must be a list; source file was not changed")
        migration_time = int(time.time())
        active_sources = {entry.memory_id: entry for entry in entries if entry.is_active(now=migration_time)}
        clean_chapters = []
        for index, row in enumerate(chapter_rows):
            chapter = MemoryChapter.from_dict(row)
            if chapter is None:
                raise MemoryStorageError(f"Invalid legacy chapter row {index}; source file was not changed")
            raw_sources = row.get("source_memory_ids")
            if (not isinstance(raw_sources, list)
                    or any(key not in chapter.source_memory_ids for key in raw_sources)):
                # Normalization must not hide a foreign or omitted dependency
                # beyond the display limit. Keep such chapters in legacy only.
                continue
            # Do not certify old summaries with invented fingerprints. Missing
            # revision evidence remains absent and is rejected by prompt reads.
            if (chapter.character_id == self.character_id
                    and all(key in active_sources for key in chapter.source_memory_ids)
                    and (not chapter.source_fingerprints or all(
                        chapter.source_fingerprints.get(key) == active_sources[key].evidence_fingerprint()
                        for key in chapter.source_memory_ids
                    ))):
                clean_chapters.append(chapter)
        deleted = [entry for entry in entries if entry.deleted]
        return {
            "schema_version": 2, "character_id": self.character_id, "owner_id": self.owner_id,
            "context_epoch": int(bool(deleted)), "entries": [entry.to_dict() for entry in entries],
            "profile": bond.to_dict(), "chapters": [chapter.to_dict() for chapter in clean_chapters],
            "retired_ids": [entry.memory_id for entry in deleted],
            "retired_origins": list({origin for entry in deleted for origin in self._origins(entry)}),
            "migrations": {"emotional_json_v1": True},
        }

    def _check_document(self, document: dict) -> None:
        from .memory_document import MemoryStorageError
        if document.get("character_id") != self.character_id or document.get("owner_id") != self.owner_id:
            raise MemoryStorageError("Memory document belongs to a different character or owner")

    def _entries(self, document: dict) -> list[EmotionalMemoryEntry]:
        self._check_document(document)
        retired = set(document.get("retired_ids", []))
        entries = []
        for row in document.get("entries", []):
            entry = EmotionalMemoryEntry.from_dict(row)
            if entry is not None and entry.character_id == self.character_id and entry.owner_id == self.owner_id:
                entries.append(replace(entry, deleted=True) if entry.memory_id in retired else entry)
        return entries

    def _validate(self, entry: EmotionalMemoryEntry) -> EmotionalMemoryEntry:
        memory = entry.normalized()
        memory.validate()
        if memory.character_id != self.character_id or memory.owner_id != self.owner_id:
            raise ValueError("memory character_id or owner_id does not match store")
        return memory

    @staticmethod
    def _origins(entry: EmotionalMemoryEntry) -> set[str]:
        origins = {"source:" + value for value in entry.source_ids}
        for key in ("legacy_key", "plugin_proposal_id", "plugin_event_id"):
            value = entry.metadata.get(key)
            if isinstance(value, str) and value:
                origins.add(f"{key}:{value}")
        return origins

    @staticmethod
    def _invalidate_derived(document: dict, ids: set[str]) -> None:
        document["chapters"] = [row for row in document.get("chapters", [])
                                if not ids.intersection(row.get("source_memory_ids", []))]
        profile = dict(document.get("profile", {}))
        evidence = _clean_evidence(profile.get("evidence"))
        for key, refs in list(evidence.items()):
            if not ids.intersection(refs):
                continue
            name, _, value = key.partition(":")
            if name == "player_alias" and profile.get(name) == value:
                profile[name] = ""
            elif isinstance(profile.get(name), list):
                profile[name] = [item for item in profile[name] if item != value]
            evidence.pop(key, None)
        profile["evidence"] = evidence
        document["profile"] = profile

    def _retire(self, document: dict, entries: list[EmotionalMemoryEntry], *, now: int) -> None:
        ids = {entry.memory_id for entry in entries}
        if not ids:
            return
        document["retired_ids"] = sorted(set(document.get("retired_ids", [])) | ids)
        document["retired_origins"] = sorted(set(document.get("retired_origins", [])) |
                                            {origin for entry in entries for origin in self._origins(entry)})
        document["entries"] = [replace(entry, deleted=True, updated_at=now).to_dict()
                               if entry.memory_id in ids else entry.to_dict() for entry in self._entries(document)]
        self._invalidate_derived(document, ids)
        document["context_epoch"] = int(document.get("context_epoch", 0)) + 1

    @property
    def context_epoch(self) -> int:
        with self._document() as document:
            self._check_document(document)
            return int(document.get("context_epoch", 0))

    def expire_memories(self, *, now: int) -> None:
        """Invalidate dependent context once per expired content revision.

        Expiry is not deletion: the historical card remains inspectable. It
        still needs a generation barrier so old dialogue cannot bypass TTL.
        """
        with self._document() as document:
            expired = [entry for entry in self._entries(document)
                       if not entry.deleted and entry.valid_until and now >= entry.valid_until]
            seen = set(document.get("expired_revisions", []))
            changed = [entry for entry in expired if entry.evidence_fingerprint() not in seen]
            if changed:
                self._invalidate_derived(document, {entry.memory_id for entry in changed})
                document["context_epoch"] += 1
                document["expired_revisions"] = sorted(seen | {entry.evidence_fingerprint() for entry in changed})

    def is_retired_origin(self, *, legacy_key: str = "", entry: EmotionalMemoryEntry | None = None) -> bool:
        with self._document() as document:
            self._check_document(document)
            origins = self._origins(entry) if entry is not None else {"legacy_key:" + legacy_key}
            return bool(origins.intersection(document.get("retired_origins", [])))

    def load_memories(self) -> tuple[EmotionalMemoryEntry, ...]:
        with self._document() as document:
            return tuple(self._entries(document))

    def save_memories(self, entries: Iterable[EmotionalMemoryEntry]) -> None:
        incoming = [self._validate(entry) for entry in entries]
        with self._document() as document:
            current = {entry.memory_id: entry for entry in self._entries(document)}
            # Deletions take precedence over replayed copies within one batch.
            for entry in sorted(incoming, key=lambda entry: not entry.deleted):
                self._write_memory(document, current, entry)
            document["entries"] = [entry.to_dict() for entry in list(current.values())[:self.max_entries]]

    def _write_memory(self, document: dict, current: dict[str, EmotionalMemoryEntry],
                      memory: EmotionalMemoryEntry) -> EmotionalMemoryEntry:
        """Apply the same revocation rules for individual and batch writes."""
        old = current.get(memory.memory_id)
        if memory.memory_id in document.get("retired_ids", []):
            return old if old is not None else replace(memory, deleted=True)

        if memory.deleted:
            # Public deleted writes are revocations too. Retain the authoritative
            # old content and sources rather than trusting stale edited copies.
            target = old if old is not None else memory
            current[target.memory_id] = target
            document["entries"] = [entry.to_dict() for entry in current.values()]
            self._retire(document, [target], now=memory.updated_at)
            retired = replace(target, deleted=True, updated_at=memory.updated_at)
            current[target.memory_id] = retired
            return retired

        # Corrections can legitimately retain their original event's source id.
        # Only already-held origins of an active row are exempt from the fence.
        new_origins = self._origins(memory) - (self._origins(old) if old is not None else set())
        if new_origins.intersection(document.get("retired_origins", [])):
            return old if old is not None else replace(memory, deleted=True)
        if old is not None:
            if old.version > memory.version:
                return old
            if old.evidence_fingerprint() != memory.evidence_fingerprint():
                memory = replace(memory, version=old.version + 1)
                self._invalidate_derived(document, {old.memory_id})
                document["context_epoch"] += 1
        current[memory.memory_id] = memory
        return memory

    def upsert_memory(self, entry: EmotionalMemoryEntry, *, expected_epoch: int | None = None) -> EmotionalMemoryEntry:
        memory = self._validate(entry)
        with self._document() as document:
            current = {entry.memory_id: entry for entry in self._entries(document)}
            if expected_epoch is not None and expected_epoch != document["context_epoch"]:
                raise ValueError("stale memory proposal epoch")
            result = self._write_memory(document, current, memory)
            rows = list(current.values())
            if result.memory_id in current and not result.deleted:
                rows = [current[result.memory_id], *(entry for entry in rows if entry.memory_id != result.memory_id)]
            document["entries"] = [entry.to_dict() for entry in rows[:self.max_entries]]
            return result

    def update_memory(self, entry: EmotionalMemoryEntry) -> EmotionalMemoryEntry:
        return self.upsert_memory(entry)

    def replace_memory(self, memory_id: str, replacement: EmotionalMemoryEntry, *, now: int,
                       expected_epoch: int | None = None) -> EmotionalMemoryEntry:
        memory = self._validate(replacement)
        with self._document() as document:
            entries = self._entries(document)
            if expected_epoch is not None and expected_epoch != document["context_epoch"]:
                raise ValueError("stale memory correction epoch")
            old = next((entry for entry in entries
                        if entry.memory_id == memory_id and not entry.deleted), None)
            if old is None:
                raise KeyError(f"active memory not found: {memory_id}")
            if (memory.memory_id in document.get("retired_ids", [])
                    or any(entry.memory_id == memory.memory_id for entry in entries)):
                raise ValueError("correction must have an unused memory id")
            if memory.deleted:
                raise ValueError("correction must supply an active replacement")
            memory = replace(memory, version=old.version + 1, supersedes=old.memory_id,
                             occurred_at=old.occurred_at, created_at=now, updated_at=now)
            self._retire(document, [old], now=now)
            document["entries"] = [memory.to_dict(), *document["entries"]][:self.max_entries]
            return memory

    def forget_memory(self, memory_id: str, *, now: int,
                      expected_epoch: int | None = None) -> EmotionalMemoryEntry | None:
        with self._document() as document:
            entries = self._entries(document)
            if expected_epoch is not None and expected_epoch != document["context_epoch"]:
                raise ValueError("stale memory forget epoch")
            target = next((entry for entry in entries if entry.memory_id == memory_id), None)
            if target is None:
                return None
            # Forgetting a superseded card must also revoke its current descendants.
            ids = {memory_id}
            while True:
                descendants = {entry.memory_id for entry in entries if entry.supersedes in ids}
                if descendants <= ids:
                    break
                ids.update(descendants)
            affected = [entry for entry in entries if entry.memory_id in ids]
            if any(not entry.deleted for entry in affected):
                self._retire(document, affected, now=_clean_timestamp(now))
            return replace(target, deleted=True, updated_at=_clean_timestamp(now))

    def touch_memories(self, memory_ids: Iterable[str], *, now: int) -> tuple[EmotionalMemoryEntry, ...]:
        ids = tuple(memory_ids)
        with self._document() as document:
            entries = self._entries(document)
            updated = {entry.memory_id: entry.touch(now) if entry.memory_id in ids and not entry.deleted else entry
                       for entry in entries}
            document["entries"] = [entry.to_dict() for entry in updated.values()]
            return tuple(updated[key] for key in ids if key in updated and not updated[key].deleted)

    def save_profile(self, profile: CoreBondProfile, *, expected_epoch: int | None = None) -> None:
        if profile.character_id != self.character_id or profile.owner_id != self.owner_id:
            raise ValueError("profile character_id or owner_id does not match store")
        with self._document() as document:
            self._check_document(document)
            if expected_epoch is not None and expected_epoch != document["context_epoch"]:
                raise ValueError("stale memory profile epoch")
            previous = {key: value for key, value in document.get("profile", {}).items() if key != "updated_at"}
            payload = profile.to_dict()
            visible = {key: value for key, value in payload.items() if key != "updated_at"}
            if visible != previous:
                document["context_epoch"] += 1
            document["profile"] = payload

    def load_profile(self) -> CoreBondProfile:
        with self._document() as document:
            self._check_document(document)
            return CoreBondProfile.from_dict(document.get("profile"), fallback_character_id=self.character_id)

    def save_chapters(self, chapters: Iterable[MemoryChapter]) -> None:
        normalized = [chapter for chapter in chapters if chapter.character_id == self.character_id]
        with self._document() as document:
            self._check_document(document)
            document["chapters"] = [chapter.to_dict() for chapter in normalized[:50]]

    def load_chapters(self) -> tuple[MemoryChapter, ...]:
        with self._document() as document:
            self._check_document(document)
            return tuple(chapter for row in document.get("chapters", [])
                         if (chapter := MemoryChapter.from_dict(row)) is not None
                         and chapter.character_id == self.character_id)

    def upsert_chapter(self, chapter: MemoryChapter, *, expected_epoch: int | None = None) -> MemoryChapter:
        if chapter.character_id != self.character_id:
            raise ValueError("chapter character_id does not match store")
        with self._document() as document:
            entries = {entry.memory_id: entry for entry in self._entries(document) if not entry.deleted}
            if expected_epoch is not None and expected_epoch != document["context_epoch"]:
                raise ValueError("stale chapter proposal epoch")
            if not chapter.source_memory_ids or any(
                key not in entries or chapter.source_fingerprints.get(key) != entries[key].evidence_fingerprint()
                for key in chapter.source_memory_ids
            ):
                raise ValueError("chapter requires current source fingerprints")
            rest = [row for row in document.get("chapters", []) if row.get("chapter_id") != chapter.chapter_id]
            document["chapters"] = [chapter.to_dict(), *rest][:50]
            return chapter

    def migration_done(self, key: str) -> bool:
        with self._document() as document:
            self._check_document(document)
            return bool(document.get("migrations", {}).get(key))

    def mark_migration_done(self, key: str) -> None:
        with self._document() as document:
            self._check_document(document)
            document.setdefault("migrations", {})[key] = True


def _clean_fingerprints(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {_clean_text(key, 80): _clean_text(fingerprint, 64)
            for key, fingerprint in list(value.items())[:64]
            if isinstance(key, str) and isinstance(fingerprint, str) and key and fingerprint}


def _clean_evidence(value: object) -> dict[str, dict[str, str]]:
    if not isinstance(value, Mapping):
        return {}
    return {_clean_text(key, 200): _clean_fingerprints(refs)
            for key, refs in list(value.items())[:64] if isinstance(key, str)}


def _sanitize_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, object] = {}
    for raw_key, raw_value in value.items():
        key = _clean_text(raw_key, 40)
        if not key:
            continue
        if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            result[key] = raw_value
        elif isinstance(raw_value, (list, tuple)):
            result[key] = [
                item
                for item in raw_value[:16]
                if isinstance(item, (str, int, float, bool)) or item is None
            ]
    return result


def _read_json(path: Path) -> object:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
