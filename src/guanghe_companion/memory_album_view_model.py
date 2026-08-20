from __future__ import annotations

"""Player-facing view model for the Starshard Memory Album.

The storage layer keeps technical fields and traceability. This module turns
those records into a game-readable collection without exposing database jargon
or raw observation data to the player.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .emotional_memory import EmotionalMemoryEntry, MemoryChapter

CATEGORY_ORDER = ("第一次", "小默契", "礼物与纪念", "共同日常", "关于你", "关系章节")


@dataclass(frozen=True, slots=True)
class MemoryAlbumCard:
    card_id: str
    category: str
    title: str
    body: str
    when_label: str
    mood_label: str
    icon_key: str
    pinned: bool
    source_count: int = 1
    actions: tuple[str, ...] = ("固定", "纠正", "忘记")

    def to_dict(self) -> dict[str, object]:
        return {
            "card_id": self.card_id,
            "category": self.category,
            "title": self.title,
            "body": self.body,
            "when_label": self.when_label,
            "mood_label": self.mood_label,
            "icon_key": self.icon_key,
            "pinned": self.pinned,
            "source_count": self.source_count,
            "actions": list(self.actions),
        }


@dataclass(frozen=True, slots=True)
class MemoryAlbumSection:
    category: str
    cards: tuple[MemoryAlbumCard, ...]

    def to_dict(self) -> dict[str, object]:
        return {"category": self.category, "cards": [card.to_dict() for card in self.cards]}


def build_memory_album(
    memories: Iterable[EmotionalMemoryEntry],
    chapters: Iterable[MemoryChapter] = (),
) -> tuple[MemoryAlbumSection, ...]:
    buckets: dict[str, list[MemoryAlbumCard]] = {category: [] for category in CATEGORY_ORDER}
    for memory in memories:
        if memory.deleted:
            continue
        category = _memory_category(memory)
        buckets[category].append(_memory_card(memory, category))
    for chapter in chapters:
        buckets["关系章节"].append(_chapter_card(chapter))

    sections: list[MemoryAlbumSection] = []
    for category in CATEGORY_ORDER:
        cards = sorted(
            buckets[category],
            key=lambda card: (card.pinned, card.when_label, card.title),
            reverse=True,
        )
        if cards:
            sections.append(MemoryAlbumSection(category=category, cards=tuple(cards)))
    return tuple(sections)


def _memory_category(memory: EmotionalMemoryEntry) -> str:
    tags = set(memory.tags)
    if "第一次" in tags or memory.title.startswith("第一次"):
        return "第一次"
    if memory.kind == "关系里程碑" or "小默契" in tags:
        return "小默契"
    if memory.kind in {"赠礼", "投喂"}:
        return "礼物与纪念"
    if memory.kind == "玩家希望被记住" or "关于你" in tags:
        return "关于你"
    return "共同日常"


def _memory_card(memory: EmotionalMemoryEntry, category: str) -> MemoryAlbumCard:
    return MemoryAlbumCard(
        card_id=memory.memory_id,
        category=category,
        title=memory.title,
        body=_short(memory.summary, 88),
        when_label=_when_label(memory.occurred_at),
        mood_label=_mood_label(memory),
        icon_key=_icon_key(memory),
        pinned=memory.pinned,
        source_count=max(1, len(memory.source_ids)),
    )


def _chapter_card(chapter: MemoryChapter) -> MemoryAlbumCard:
    return MemoryAlbumCard(
        card_id=chapter.chapter_id,
        category="关系章节",
        title=chapter.title,
        body=_short(chapter.summary, 110),
        when_label=_when_label(chapter.created_at),
        mood_label="共同故事",
        icon_key="chapter",
        pinned=True,
        source_count=max(1, len(chapter.source_memory_ids)),
        actions=("查看来源", "固定", "忘记"),
    )


def _when_label(value: int) -> str:
    timestamp = max(0, int(value))
    # Real-world timestamps are shown as dates. The deterministic demo clock
    # starts at zero, so it is shown as relationship time instead.
    if timestamp >= 946_684_800:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y.%m.%d")
    if timestamp <= 0:
        return "刚刚"
    return f"相处第 {timestamp // 86_400 + 1} 天"


def _mood_label(memory: EmotionalMemoryEntry) -> str:
    mood = memory.emotion.label or "平静"
    if memory.pinned:
        return f"{mood} · 已珍藏"
    return mood


def _icon_key(memory: EmotionalMemoryEntry) -> str:
    item_id = str(memory.metadata.get("item_id", "")).strip()
    if item_id:
        return item_id
    if memory.kind == "共同学习":
        return "study"
    if memory.kind == "主动陪伴":
        return "heartbeat"
    if memory.kind == "关系里程碑":
        return "bond"
    return "starshard"


def _short(value: str, limit: int) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: max(1, limit - 1)] + "…"
