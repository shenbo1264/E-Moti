"""The explainable ledger view of memory: what is held, why, and until when.

A read-only projection of the one memory authority. Retired cards deliberately
carry no title or body, so old text cannot linger in the album after a user
corrects or forgets it.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from zoneinfo import ZoneInfo

from .emotional_memory import EmotionalMemoryEntry

_SECTIONS = (
    ("pending", "待你确认", "还没有记住。确认后才会长期保存。"),
    ("fact", "当前有效的事实", "聊天时可以直接用。"),
    ("plan", "计划", "还没有发生，不会被说成已经做过。"),
    ("episode", "共同经历", "真实发生过、有来源的事。"),
    ("task", "任务经验", "过去做事的结果。不能保证这次也一样。"),
    ("external", "外部实时状态", "未接入。任务、游戏等当前状态由各自系统负责，E-Moti 不保存。"),
    ("history", "历史事实", "曾经成立，现在已结束。只在问起过去时使用。"),
    ("retired", "已更正或忘记", "不再用于聊天，这里也不再显示原来的内容。"),
)

SOURCE_LABELS = {
    "explicit_user_request": "你亲口要求记住",
    "user_correction": "你的纠正",
    "user_change": "你说明情况变了",
    "game_event": "你们一起经历的事",
    "relationship_unlock": "关系里程碑",
    "confirmed_companion_skill": "你确认完成的陪伴",
    "user_chat": "普通聊天",
}
_SCOPE_LABELS = {"companion": "陪伴", "task_experience": "任务经验"}
_EPISODE_SOURCES = {"game_event", "relationship_unlock", "confirmed_companion_skill"}
_FACT_SOURCES = {"user_chat", "explicit_user_request", "user_correction", "user_change"}
_LIVE_ACTIONS = ("固定", "修改", "忘记", "彻底删除")


def time_label(value: int, basis: str, timezone_name: str = "") -> str:
    """Never guess a calendar date from a number: the basis decides."""
    stamp = int(value)
    if stamp <= 0:
        return "未记录"
    if basis == "unix":
        zone = ZoneInfo(timezone_name or "UTC")
        return datetime.fromtimestamp(stamp, tz=zone).strftime("%Y-%m-%d")
    return f"相处第 {stamp // 86_400 + 1} 天（逻辑时间）"


def classify_memory(entry: EmotionalMemoryEntry, *, now: int) -> str:
    if entry.deleted:
        return "retired"
    if entry.scope == "task_experience":
        return "task"
    ended = bool(entry.valid_until) and now >= entry.valid_until
    if ended:
        return "history"
    meta = entry.metadata
    if meta.get("plan_status") == "planned" or meta.get("planned") is True or entry.valid_from > now:
        return "plan"
    if entry.source in _EPISODE_SOURCES:
        return "episode"
    if (entry.source in _FACT_SOURCES or entry.kind == "玩家希望被记住" or "关于你" in entry.tags
            or meta.get("fact_subject") or meta.get("fact_slot")):
        return "fact"
    return "episode"


def build_memory_ledger(memories: Iterable[EmotionalMemoryEntry], *, now: int, time_basis: str = "logical",
                        timezone_name: str = "",
                        pending: Iterable[dict[str, object]] = ()) -> list[dict[str, object]]:
    entries = tuple(memories)
    successors: dict[str, list[EmotionalMemoryEntry]] = {}
    for entry in entries:
        if entry.supersedes:
            successors.setdefault(entry.supersedes, []).append(entry)
    buckets: dict[str, list[dict[str, object]]] = {key: [] for key, _, _ in _SECTIONS}
    for candidate in pending:
        buckets["pending"].append(_pending_card(candidate, time_basis, timezone_name))
    for entry in entries:
        key = classify_memory(entry, now=now)
        if key != "retired":
            buckets[key].append(_card(entry, key, now, time_basis, timezone_name))
            continue
        replaced_by = successors.get(entry.memory_id, ())
        # 一条修订链只留链头，遗忘整条链时不重复列出每个旧版本。
        if any(row.deleted for row in replaced_by):
            continue
        buckets["retired"].append(_retired_card(entry, bool(replaced_by), time_basis, timezone_name))
    return [{"key": key, "label": label, "hint": hint,
             "cards": sorted(buckets[key], key=lambda card: (card["pinned"], card["sort_at"]), reverse=True)}
            for key, label, hint in _SECTIONS]


def _card(entry, section, now, basis, zone) -> dict[str, object]:
    entry_basis = str(entry.metadata.get("time_basis") or basis)
    entry_zone = str(entry.metadata.get("timezone") or zone)
    recorded = entry.metadata.get("recorded_time")
    recorded = recorded if type(recorded) is int else entry.created_at
    actions = {"history": ("忘记", "彻底删除")}.get(section, _LIVE_ACTIONS)
    return {
        "card_id": entry.memory_id, "section": section, "title": entry.title, "body": entry.summary,
        "subject": _subject(entry, section), "field": _field(entry),
        "source_label": SOURCE_LABELS.get(entry.source, entry.source),
        "occurred_label": time_label(entry.occurred_at, entry_basis, entry_zone),
        "recorded_label": time_label(recorded, entry_basis, entry_zone),
        "valid_label": _valid_label(entry, entry_basis, entry_zone),
        "version": entry.version, "scope_label": _SCOPE_LABELS.get(entry.scope, entry.scope),
        "status_label": _status(entry, section), "pinned": entry.pinned, "sort_at": entry.occurred_at,
        "actions": list(actions),
    }


def _retired_card(entry, corrected, basis, zone) -> dict[str, object]:
    label = "已更正" if corrected else "已忘记"
    body = ("已被新版本取代。" if corrected
            else "已停止使用，正文仍在本机存档里，可以彻底删除。")
    return {
        "card_id": entry.memory_id, "section": "retired", "title": f"一条{label}的记录", "body": body,
        "subject": "", "field": "", "source_label": "",
        "occurred_label": "", "recorded_label": time_label(entry.updated_at, basis, zone), "valid_label": "不再使用",
        "version": entry.version, "scope_label": _SCOPE_LABELS.get(entry.scope, entry.scope),
        "status_label": label, "pinned": False, "sort_at": entry.updated_at,
        # 彻底删除作用于整条修订链，已更正的旧版本上提供它会连当前事实一起删掉。
        "actions": [] if corrected else ["彻底删除"],
    }


def _pending_card(candidate, basis, zone) -> dict[str, object]:
    return {
        **candidate, "card_id": candidate["pending_id"], "section": "pending", "pending": True,
        "body": candidate.get("summary", ""),
        "source_label": SOURCE_LABELS.get(str(candidate.get("source", "")), str(candidate.get("source", ""))),
        "occurred_label": time_label(int(candidate.get("occurred_at") or 0), basis, zone),
        "status_label": "待确认", "pinned": False, "sort_at": int(candidate.get("occurred_at") or 0), "actions": [],
    }


def _subject(entry, section) -> str:
    subject = str(entry.metadata.get("fact_subject", ""))
    if subject == "user:self":
        return "你"
    if subject.startswith("relation:"):
        return "你的" + subject.split(":", 1)[1]
    if subject:
        return subject
    return "你们" if section == "episode" else "你" if section == "fact" else ""


def _field(entry) -> str:
    meta = entry.metadata
    slot = str(meta.get("fact_slot") or meta.get("fact_predicate") or meta.get("fact_domain") or "")
    if slot.startswith("preference:"):
        return "偏好 · " + slot.split(":", 1)[1]
    return slot


def _valid_label(entry, basis, zone) -> str:
    start = time_label(entry.valid_from, basis, zone) if entry.valid_from else ""
    end = time_label(entry.valid_until, basis, zone) if entry.valid_until else ""
    if start and end:
        return f"从 {start} 到 {end}"
    if end:
        return f"到 {end}"
    if start:
        return f"从 {start} 起，直到你修改"
    return "一直有效，直到你修改"


def _status(entry, section) -> str:
    return {"fact": "当前有效", "plan": "计划中", "episode": "已发生", "task": "过去的结果",
            "history": "已结束"}.get(section, section)
