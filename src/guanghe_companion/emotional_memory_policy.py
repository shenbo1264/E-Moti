from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .emotional_memory import EmotionalMemoryEntry, EmotionalSignal, make_memory_id


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    character_id: str
    owner_id: str
    kind: str
    title: str
    summary: str
    source: str
    occurred_at: int
    source_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    emotion: EmotionalSignal = field(default_factory=EmotionalSignal)
    importance: float = 0.5
    relationship_delta: float = 0.0
    pinned: bool = False
    requires_user_confirmation: bool = False
    metadata: dict[str, object] = field(default_factory=dict)

    def to_memory(self, *, now: int, user_confirmed: bool = False) -> EmotionalMemoryEntry:
        memory_id = make_memory_id(
            self.character_id,
            self.owner_id,
            self.kind,
            self.title,
            self.summary,
            self.occurred_at,
            *self.source_ids,
        )
        return EmotionalMemoryEntry(
            memory_id=memory_id,
            character_id=self.character_id,
            owner_id=self.owner_id,
            kind=self.kind,
            title=self.title,
            summary=self.summary,
            source=self.source,
            occurred_at=max(0, int(self.occurred_at)),
            created_at=max(0, int(now)),
            updated_at=max(0, int(now)),
            source_ids=self.source_ids,
            tags=self.tags,
            emotion=self.emotion,
            importance=self.importance,
            relationship_delta=self.relationship_delta,
            pinned=self.pinned,
            user_confirmed=user_confirmed,
            metadata=dict(self.metadata),
        ).normalized()


class EmotionalMemoryPolicy:
    """Deterministic write policy for emotionally meaningful game memories.

    The LLM may propose a candidate, but this policy owns whether the runtime is
    allowed to persist it. Raw screen summaries are never persisted here.
    """

    def from_event(
        self,
        event: object,
        *,
        character_id: str,
        owner_id: str = "local_user",
        now: int,
    ) -> MemoryCandidate | None:
        row = _event_to_mapping(event)
        if not row:
            return None
        event_type = str(row.get("event_type", ""))
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        source_id = str(row.get("event_id") or payload.get("event_id") or "")
        source_ids = (source_id,) if source_id else ()

        if event_type == "relationship":
            message = _clean(payload.get("message") or row.get("speech"))
            unlock_id = _clean(payload.get("unlock_id"))
            if not message or not unlock_id:
                return None
            return MemoryCandidate(
                character_id=character_id,
                owner_id=owner_id,
                kind="关系里程碑",
                title="我们之间多了一点默契",
                summary=message,
                source="relationship_unlock",
                occurred_at=now,
                source_ids=source_ids,
                tags=("关系", "第一次", "共同日常"),
                emotion=EmotionalSignal("靠近", 0.8, 0.9),
                importance=0.96,
                relationship_delta=0.9,
                pinned=True,
                metadata={"unlock_id": unlock_id},
            )

        if event_type == "inventory":
            action = _clean(payload.get("action"))
            item_name = _clean(payload.get("item_name"))
            item_id = _clean(payload.get("item_id"))
            first_time = bool(payload.get("first_time", False))
            milestone = bool(payload.get("milestone", False))
            if action not in {"feed", "gift"} or not item_name:
                return None
            # Routine repeats remain in the recent event log. Long-term memory
            # keeps firsts and explicit milestones, otherwise the album quickly
            # becomes a receipt list.
            if not first_time and not milestone:
                return None
            kind = "赠礼" if action == "gift" else "投喂"
            character_name = _clean(payload.get("character_name")) or (
                "星汐" if character_id == "xingxi_pixel_pet" else character_id
            )
            title = f"第一次{item_name}" if first_time else f"关于{item_name}的小纪念"
            importance = 0.84 if first_time else 0.72
            action_summary = (
                f"你给{character_name}喂了{item_name}。"
                if action == "feed"
                else f"你把{item_name}送给了{character_name}。"
            )
            return MemoryCandidate(
                character_id=character_id,
                owner_id=owner_id,
                kind=kind,
                title=title,
                summary=action_summary,
                source="game_event",
                occurred_at=now,
                source_ids=source_ids,
                tags=(kind, "第一次" if first_time else "小默契", item_name),
                emotion=EmotionalSignal("开心", 0.75, 0.72 if first_time else 0.5),
                importance=importance,
                relationship_delta=0.35 if first_time else 0.12,
                pinned=first_time,
                metadata={"item_id": item_id, "action": action},
            )

        if event_type == "memory":
            kind = _clean(payload.get("kind"))
            summary = _clean(payload.get("summary") or row.get("speech"))
            motion = _clean(payload.get("motion"))
            first_time = bool(payload.get("first_time", False))
            if not kind or not summary:
                return None
            # Inventory events are the authoritative source for feed/gift
            # memories; the paired generic memory event would duplicate them.
            if kind in {"赠礼", "投喂", "使用"}:
                return None
            if kind == "互动" and not first_time and not bool(payload.get("milestone", False)):
                return None
            return MemoryCandidate(
                character_id=character_id,
                owner_id=owner_id,
                kind=kind,
                title=_memory_title(kind, summary, first_time),
                summary=summary,
                source="game_event",
                occurred_at=now,
                source_ids=source_ids,
                tags=(kind, "第一次" if first_time else "共同日常"),
                emotion=_emotion_for_kind(kind),
                importance=0.78 if first_time else 0.62,
                relationship_delta=0.28 if first_time else 0.12,
                pinned=first_time,
                metadata={"motion": motion},
            )

        if event_type == "proactive":
            # A read-only perception summary is transient context. Only the
            # completed, user-accepted companion moment is memory-eligible.
            completed = bool(payload.get("completed", False))
            user_accepted = bool(payload.get("user_accepted", False))
            raw_screen = bool(payload.get("contains_screen_content", False))
            if not completed or not user_accepted or raw_screen:
                return None
            summary = _clean(payload.get("summary") or row.get("speech"))
            if not summary:
                return None
            return MemoryCandidate(
                character_id=character_id,
                owner_id=owner_id,
                kind="主动陪伴",
                title="星汐在合适的时候探出了头",
                summary=summary,
                source="confirmed_companion_skill",
                occurred_at=now,
                source_ids=source_ids,
                tags=("主动陪伴", "被确认的行动"),
                emotion=EmotionalSignal("安心", 0.55, 0.58),
                importance=0.66,
                relationship_delta=0.18,
                metadata={"skill_id": _clean(payload.get("skill_id"))},
            )

        return None

    def explicit_user_memory(
        self,
        text: str,
        *,
        character_id: str,
        owner_id: str = "local_user",
        now: int,
    ) -> MemoryCandidate | None:
        cleaned = _clean(text)
        markers = ("请记住", "记住这件事", "帮我记住", "你要记得")
        marker = next((item for item in markers if cleaned.startswith(item)), "")
        if not marker:
            return None
        content = cleaned[len(marker) :].lstrip("：:，, ")
        if not content:
            return None
        return MemoryCandidate(
            character_id=character_id,
            owner_id=owner_id,
            kind="玩家希望被记住",
            title="你亲口交给她的一件事",
            summary=content,
            source="explicit_user_request",
            occurred_at=now,
            tags=("用户确认", "关于你"),
            emotion=EmotionalSignal("认真", 0.25, 0.55),
            importance=0.82,
            relationship_delta=0.1,
            pinned=True,
            requires_user_confirmation=True,
        )


def _event_to_mapping(event: object) -> Mapping[str, object]:
    if isinstance(event, Mapping):
        return event
    event_type = getattr(event, "event_type", None)
    if not isinstance(event_type, str):
        return {}
    payload = getattr(event, "payload", {})
    return {
        "event_type": event_type,
        "speech": getattr(event, "speech", ""),
        "payload": payload if isinstance(payload, Mapping) else {},
    }


def _clean(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\n", " ").replace("\r", " ").strip().split())[:240]


def _memory_title(kind: str, summary: str, first_time: bool) -> str:
    if first_time:
        return f"第一次{kind}"
    if kind == "共同学习":
        return "一起安静学习的一小段时间"
    if kind == "互动":
        return "又一次靠近"
    return summary[:28]


def _emotion_for_kind(kind: str) -> EmotionalSignal:
    if kind in {"共同学习", "学习"}:
        return EmotionalSignal("专注", 0.45, 0.55)
    if kind in {"玩耍", "娱乐"}:
        return EmotionalSignal("开心", 0.8, 0.75)
    if kind in {"安抚", "休息"}:
        return EmotionalSignal("安心", 0.55, 0.65)
    return EmotionalSignal("靠近", 0.4, 0.45)
