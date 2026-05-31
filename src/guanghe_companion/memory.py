from __future__ import annotations

from dataclasses import dataclass


def memory_kind_for_inventory_usage(usage: str) -> str:
    if usage == "feed":
        return "投喂"
    if usage == "gift":
        return "赠礼"
    return "使用"


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    at: int
    kind: str
    summary: str
    motion: str
    item_id: str | None = None

    def to_legacy_dict(self) -> dict[str, object]:
        row: dict[str, object] = {
            "at": self.at,
            "kind": self.kind,
            "summary": self.summary,
            "motion": self.motion,
        }
        if self.item_id is not None:
            row["item_id"] = self.item_id
        return row


class MemoryLogService:
    def __init__(self, memory_log: list[dict[str, object]], max_entries: int = 12) -> None:
        self.memory_log = memory_log
        self.max_entries = max_entries

    def append(self, at: int, kind: str, summary: str, motion: str, item_id: str | None = None) -> None:
        entry = MemoryEntry(at=at, kind=kind, summary=summary, motion=motion, item_id=item_id)
        self.memory_log.insert(0, entry.to_legacy_dict())
        del self.memory_log[self.max_entries :]

    def append_drafts(self, at: int, drafts: list[dict[str, object]]) -> None:
        for draft in drafts:
            self.append(
                at=at,
                kind=str(draft["kind"]),
                summary=str(draft["summary"]),
                motion=str(draft["motion"]),
                item_id=str(draft["item_id"]) if "item_id" in draft else None,
            )
