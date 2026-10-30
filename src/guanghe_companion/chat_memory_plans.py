from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from uuid import uuid4

from .emotional_memory import MAX_SOURCE_IDS
from .emotional_memory_policy import MemoryCandidate


# 这是活跃使用时钟上的记忆新鲜度上限，不是计划的日历截止日。
PLAN_RETENTION_SECONDS = 30 * 24 * 60 * 60
_UNSUPPORTED = re.compile(
    r"假如|假设|如果|也许|可能|据说|朋友说|他说|她说|小说|故事里|游戏里|游戏中|角色扮演|"
    r"原本|本来|曾经|已经|不打算|不准备|不计划|取消|不再|才怪|开玩笑|反话|举例|原话|"
    r"密码|验证码|银行卡|私钥|[？?‘’“”\"「」]|吗")
_TIME = re.compile(
    r"(?:今年|明年|后年|\d{4}年)?(?:[一二三四五六七八九十]{1,3}|\d{1,2})月(?:\d{1,2}[日号])?"
    r"|下(?:个)?(?:月|周|星期)(?:[一二三四五六日天])?|明天|后天|周末|今年|明年|后年")
_INTENTION = re.compile(r"^我(?:现在|最近|正在)?(?:计划|打算|准备|在备考|正备考|备考|在筹备|正在筹备)")
_FUTURE = re.compile(r"^我(?:现在|已经)?(?:下|明|后|今年|\d|[一二三四五六七八九十]).{0,18}?(?:要|将|会)")


@dataclass(frozen=True, slots=True)
class PlanStatement:
    original_text: str
    quote: str
    time_expression: str


def prepare_plan(text: str) -> PlanStatement | None:
    if not isinstance(text, str) or _UNSUPPORTED.search(text):
        return None
    # 以句子隔离闲聊与计划；保留同句后半段的原始月份，不由当前年份补全。
    for sentence in re.split(r"[。！!\n]", text):
        statement = re.sub(r"^(?:对了|另外|还有|顺便说一下)[，, ]*", "", sentence.strip())
        if not statement.startswith("我"):
            continue
        if not (_INTENTION.match(statement) or (_FUTURE.match(statement) and _TIME.search(statement))):
            continue
        if any(word in statement for word in ("我朋友", "我同事", "我妈妈", "我爸爸", "我的朋友")):
            continue
        if len(statement) > 240 or len(statement) < 5:
            continue
        times = tuple(dict.fromkeys(match.group() for match in _TIME.finditer(statement)))
        return PlanStatement(text, statement, "、".join(times))
    return None


def plan_view(entry) -> PlanStatement | None:
    if entry.deleted or entry.source not in {"user_chat", "explicit_user_request", "user_correction"}:
        return None
    if entry.metadata.get("plan_status") == "planned":
        return PlanStatement(str(entry.metadata.get("original_quote", entry.summary)), entry.summary,
                             str(entry.metadata.get("time_expression", "")))
    if entry.source == "explicit_user_request" and entry.user_confirmed:
        return prepare_plan(entry.summary)
    return None


def correct_plan(memory, entry, *, summary: str, value: str, text: str, now: int, mode: str):
    from .chat_memory import ChatMemoryResult

    if mode not in {"auto", "review", "off"}:
        raise ValueError("invalid memory mode")
    if mode == "off":
        return ChatMemoryResult()
    old = next((m for m in memory.store.load_memories() if m.memory_id == entry.memory_id), None)
    if old is None or old.evidence_fingerprint() != entry.evidence_fingerprint() or not old.is_active(now=now):
        raise ValueError("plan correction requires current evidence")
    plan = plan_view(old)
    new_times = tuple(dict.fromkeys(m.group() for m in _TIME.finditer(text)))
    if (plan is None or not value or value not in text or value not in summary or _UNSUPPORTED.search(text)
            or not re.search(r"不对|说错|记错|更正|纠正|改为|改去|改成|不是", text)
            or (new_times and "、".join(new_times) != plan.time_expression)):
        return ChatMemoryResult("clarify", "请明确要纠正的计划内容和时间；计划尚未视为完成。")
    deadline = old.valid_until or old.occurred_at + PLAN_RETENTION_SECONDS
    if deadline <= now:
        return ChatMemoryResult("clarify", "这项计划已超过记忆有效期，请重新说明当前计划。")
    reference = f"chat-plan-correction:{uuid4().hex}"
    sources = tuple(dict.fromkeys((*old.source_ids, reference)))
    if len(sources) > MAX_SOURCE_IDS:
        raise ValueError("plan correction source references exceed the supported limit")
    # 只把新的字面目标与原时间交给 prompt，旧目标留在已退役事实和来源审计中。
    topic = "迁居地点" if "搬" in plan.quote or "迁居" in plan.quote else "计划内容"
    revised_summary = f"用户计划（未确认完成）：{topic}改为{value}"
    if plan.time_expression:
        revised_summary += f"；时间表述：{plan.time_expression}"
    metadata = {**old.metadata, "speaker": "user", "scene": "companion_chat", "original_quote": text,
                "evidence_quote": text, "message_id": reference, "recorded_at": datetime.now(timezone.utc).isoformat(),
                "plan_status": "planned", "time_expression": plan.time_expression,
                "fact_domain": "计划", "fact_slot": "plan", "fact_value": value, "corrected_by_user": True,
                "confidence_reason": "明确纠正计划目标；保留原时间表述，尚未确认完成",
                "expiry_basis": "logical_memory_freshness", "expiry_note": "有效期仅用于记忆新鲜度，不代表计划日期"}
    epoch = memory.store.context_epoch
    valid_from = old.valid_from or old.occurred_at
    if mode == "review":
        metadata.update(source_memory_ids=[old.memory_id], supersedes_memory_id=old.memory_id)
        candidate = MemoryCandidate(character_id=memory.character_id, owner_id=memory.owner_id,
            kind="用户计划", title="待进行的计划", summary=revised_summary, source="user_correction",
            occurred_at=old.occurred_at, source_ids=sources, tags=("关于你", "计划"), metadata=metadata,
            valid_from=valid_from, valid_until=deadline, requires_user_confirmation=True)
        memory.propose_candidate(candidate, pending_id=reference, expected_epoch=epoch, now=now)
        return ChatMemoryResult("pending", "计划纠正已放入待确认，尚未视为完成。")
    replacement = memory.remember(kind="用户计划", title="待进行的计划", summary=revised_summary,
        source="user_correction", now=now, source_ids=sources, metadata=metadata, tags=("关于你", "计划"),
        user_confirmed=True, supersedes=old.memory_id, preserve_occurred_at=True,
        valid_from=valid_from, valid_until=deadline, expected_epoch=epoch)
    return ChatMemoryResult("saved", memory_ids=(replacement.memory_id,))


def record_plan(memory, statement: PlanStatement, *, now: int, mode: str):
    from .chat_memory import ChatMemoryResult

    if mode not in {"auto", "review", "off"}:
        raise ValueError("invalid memory mode")
    if mode == "off":
        return ChatMemoryResult()
    if prepare_plan(statement.original_text) != statement:
        raise ValueError("plan must be grounded in an explicit user statement")
    summary = f"用户计划（未确认完成）：{statement.quote}"
    existing = [m for m in memory.store.load_memories() if m.is_active(now=now)
                and m.metadata.get("plan_status") == "planned" and m.summary == summary]
    if existing:
        return ChatMemoryResult("saved", memory_ids=tuple(m.memory_id for m in existing))
    message_id = f"chat-plan:{uuid4().hex}"
    metadata = {"speaker": "user", "scene": "companion_chat", "original_quote": statement.original_text,
                "evidence_quote": statement.quote, "message_id": message_id,
                "recorded_at": datetime.now(timezone.utc).isoformat(), "plan_status": "planned",
                "time_expression": statement.time_expression, "fact_domain": "计划", "fact_slot": "plan",
                "fact_value": statement.quote, "confidence_reason": "明确计划自述，尚未确认执行或完成",
                "expiry_basis": "logical_memory_freshness", "expiry_note": "有效期仅用于记忆新鲜度，不代表计划日期"}
    epoch = memory.store.context_epoch
    if mode == "review":
        candidate = MemoryCandidate(character_id=memory.character_id, owner_id=memory.owner_id,
            kind="用户计划", title="待进行的计划", summary=summary, source="user_chat", occurred_at=now,
            source_ids=(message_id,), metadata=metadata, tags=("关于你", "计划"),
            valid_from=now, valid_until=now + PLAN_RETENTION_SECONDS, requires_user_confirmation=True)
        memory.propose_candidate(candidate, pending_id=message_id, expected_epoch=epoch)
        return ChatMemoryResult("pending", "这项计划已放入待确认，尚未视为完成。")
    entry = memory.remember(kind="用户计划", title="待进行的计划", summary=summary, source="user_chat", now=now,
        source_ids=(message_id,), metadata=metadata, tags=("关于你", "计划"), user_confirmed=False,
        valid_from=now, valid_until=now + PLAN_RETENTION_SECONDS, expected_epoch=epoch)
    return ChatMemoryResult("saved", memory_ids=(entry.memory_id,))
