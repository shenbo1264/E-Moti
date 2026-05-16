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
