from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from uuid import uuid4

from .emotional_memory_policy import MemoryCandidate
from .emotional_memory_service import EmotionalMemoryService


@dataclass(frozen=True, slots=True)
class ChatMemoryResult:
    status: str = "ignored"
    message: str = ""
    memory_ids: tuple[str, ...] = ()


def spoken_memory_result(result) -> str:
    """Words the companion says; the plain status text stays in the receipt."""
    if result is not None and result.status == "forgotten":
        return "……嗯，这件事我不记了。"
    if result is not None and result.status == "pending":
        return "这件事我先放进待确认了，你看一眼回忆册？"
    return getattr(result, "message", "") or "这件事先放进待确认了，你可以在回忆册里确认或放弃。"


# 仅接受可由原话直接证明的自述；含推测、引用、虚构和临时状态的消息不自动变成事实。
_UNSUPPORTED = re.compile(
    r"假如|假设|如果|也许|可能|不确定|据说|他说|她说|朋友说|小说|主角|角色扮演|游戏里|游戏中|"
    r"故事里|梦里|今天|此刻|暂时|打算|准备|计划|[？?]|吗|呢|还是|什么|那个人|那件事|[‘’“”\"「」]"
    r"|才怪|原话|举例|假话|的话|不是|仅仅|这句话|反话"
)
_PREFERENCE = re.compile(r"^我(?:一直|平时|更|最|比较|现在)?(?P<verb>不再喜欢|不太喜欢|不喜欢|讨厌|喜欢|偏爱)(?:的是|是)?(?P<value>[^，。；！!?？]{1,40})$")
_CHANGE = re.compile(r"^我(?:现在|以后|已经)?改(?:喝|吃|用)(?P<value>[^，。；！!?？]{1,40}?)(?:了)?$")
_FACT = re.compile(r"^我(?:现在|目前)?(?P<verb>住在|从事|的职业是|的工作是)(?P<value>[^，。；！!?？]{1,40})$")
_DRINK = re.compile(r"茶|咖啡|饮料|饮品|汽水|果汁|牛奶|可乐|豆浆|白开水")
_CORRECTION = re.compile(r"^(?:刚才说错了|之前说错了|我说错了|我记错了|更正一下|纠正一下)[，,:： ]*")
_COMMON_FACTS = (
    (re.compile(r"^我对(?P<value>[^，。；！!?？]{1,30})过敏$"), "过敏", "用户对{value}过敏", False),
    (re.compile(r"^我(?:长期|一直|从来)(?:都)?不吃(?P<value>[^，。；！!?？]{1,30})$"), "长期忌口", "用户长期不吃{value}", False),
    (re.compile(r"^我(?:现在|已经)?搬(?:家)?到了?(?P<value>[^，。；！!?？]{1,30}?)(?:了)?$"), "居住地", "用户住在{value}", True),
    (re.compile(r"^我从[^，。；！!?？]{1,30}搬到了?(?P<value>[^，。；！!?？]{1,30}?)(?:了)?$"), "居住地", "用户住在{value}", True),
    (re.compile(r"^我是一名(?P<value>[^，。；！!?？]{1,20})$"), "职业", "用户的职业是{value}", False),
    (re.compile(r"^(?:请叫我|以后叫我|你可以叫我)(?P<value>[^，。；！!?？]{1,20})$"), "称呼", "用户希望被称呼为{value}", False),
    (re.compile(r"^我的名字是(?P<value>[^，。；！!?？]{1,20})$"), "姓名", "用户的名字是{value}", False),
    (re.compile(r"^我叫(?P<value>(?!你|他|她|了)[\u4e00-\u9fffA-Za-z·]{2,12})$"), "姓名", "用户的名字是{value}", False),
    (re.compile(r"^我的(?P<pet>猫|狗|兔子|鹦鹉|仓鼠|宠物)叫(?P<value>[^，。；！!?？]{1,20})$"), "宠物称呼", "用户的{pet}叫{value}", False),
    (re.compile(r"^我养了?(?:一只)?(?P<pet>猫|狗|兔子|鹦鹉|仓鼠)(?:[，,]?叫(?P<value>[^，。；！!?？]{1,20}))?$"), "宠物", "用户养了{pet}", False),
)


def forget_target(text: str) -> str | None:
    # 先识别命令而不是按人称触发；话题可以位于动词前，且不必含“我”。
    if re.search(r"假如|假设|如果|也许|可能|不确定|据说|他说|她说|朋友说|小说|故事里|梦里|游戏里|游戏中|角色扮演|"
                 r"举例|假话|反话|的话|[？?]|吗|呢|什么意思|原话|这句话|不是|[‘’“”\"「」]|(?:不要|别|不能)忘", text):
        return None
    body = text.strip().rstrip("。！! ")
    match = re.fullmatch(r"(?:请)?(?:忘记|忘掉|别再记|别记|不要再记|不要记|删掉|删除)(.+)", body)
    if match:
        target = match[1]
    else:
        match = re.fullmatch(r"(?:请)?(?:把)?(.+?)(?:请)?(?:忘了|忘掉|忘记|别再记|别记|不要再记|不要记|删掉|删除)(?:了|吧|就好)*", body)
        if not match:
            return None
        target = match[1]
    target = re.sub(r"^(?:我的?|关于)", "", target)
    target = re.sub(r"(?:那件事|这件事|的事情|的事|这条信息|这条记忆)$", "", target)
    return target.rstrip("了吧 ")


def matches_forget_target(target: str, entry) -> bool:
    if not target or target in {"这件事", "那件事", "那个事情", "事情", "刚才", "这条"}:
        return False
    if len(target) == 1 and target not in {"猫", "狗", "茶"}:
        return False
    summary = re.sub(r"^(?:用户|我)的?", "", entry.summary)
    return target in summary or target in str(entry.metadata.get("fact_domain", ""))


def _parse_fact(clause):
    preference = _PREFERENCE.fullmatch(clause)
    change = _CHANGE.fullmatch(clause)
    fact = _FACT.fullmatch(clause)
    match = preference or change or fact
    if match:
        value = match["value"].strip().removesuffix("了")
        verb = match["verb"] if not change else "喜欢"
        domain = "饮料偏好" if _DRINK.search(value) else "个人偏好"
        polarity = "avoid" if verb in {"不再喜欢", "不太喜欢", "不喜欢", "讨厌"} else "like"
        slot = f"preference:{domain}:{polarity}"
        if fact:
            domain = "居住地" if verb == "住在" else "职业"
            slot = domain
        return value, domain, slot, f"用户{verb}{value}", bool(preference), bool(change)
    for pattern, domain, template, change in _COMMON_FACTS:
        match = pattern.fullmatch(clause)
        if match:
            values = match.groupdict()
            value = values.get("value") or values.get("pet")
            summary = template.format(**values)
            if domain == "宠物" and values.get("value"):
                summary += f"，叫{value}"
            slot = domain + (":" + values["pet"] if "pet" in values else "")
            return value, domain, slot, summary, False, change
    return None


def _fact_view(entry):
    if entry.metadata.get("fact_slot"):
        return entry
    # 只读取既有用户明确授权的事实，不从聊天历史或外部观察重新提取。
    if entry.source not in {"explicit_user_request", "user_correction"}:
        return entry
    text = re.sub(r"^用户", "我", entry.summary.strip().rstrip("。！!"))
    parsed = None if _UNSUPPORTED.search(text) else _parse_fact(text)
    if parsed is None:
        return entry
    value, domain, slot, _, _, _ = parsed
    return replace(entry, metadata={**entry.metadata, "fact_value": value,
                                   "fact_domain": domain, "fact_slot": slot})


class ChatMemory:
    def __init__(self, memory: EmotionalMemoryService, settings_path: Path):
        self.memory = memory
        self.settings_path = settings_path
        self.mode = "auto"
        if settings_path.exists():
            self.mode = json.loads(settings_path.read_text(encoding="utf-8"))["mode"]
            if self.mode not in {"auto", "review", "off"}:
                raise ValueError("invalid chat memory mode")

    def set_mode(self, mode: str) -> None:
        if mode not in {"auto", "review", "off"}:
            raise ValueError("chat memory mode must be auto, review or off")
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        pending = self.settings_path.with_suffix(".pending")
        pending.write_text(json.dumps({"mode": mode}), encoding="utf-8")
        pending.replace(self.settings_path)
        self.mode = mode

    def process(self, text: str, *, now: int) -> ChatMemoryResult:
        text = text.strip()
        active = [_fact_view(m) for m in self.memory.store.load_memories()
                  if m.is_active(now=now) and (m.metadata.get("speaker") == "user"
                    or (m.user_confirmed and m.source in {"explicit_user_request", "user_correction"}))]
        if forget_target(text) is not None:
            return self._forget(text, active, now=now)
        from .chat_memory_plans import prepare_plan, record_plan
        plan = prepare_plan(text)
        if plan is not None:
            return record_plan(self.memory, plan, now=now, mode=self.mode)
        if _UNSUPPORTED.search(text):
            return ChatMemoryResult()
        if self.mode == "off":
            return ChatMemoryResult()
        correction = bool(_CORRECTION.match(text))
        body = _CORRECTION.sub("", text)
        complete = body.rstrip("。！!")
        clauses = ([complete] if _parse_fact(complete) else
                   [part.strip() for part in re.split(r"[，。；！]", body) if part.strip()])
        source_id = f"chat:{uuid4().hex}"
        written: list[str] = []
        pending: list[str] = []
        inherited_subject = False
        for index, clause in enumerate(clauses):
            if inherited_subject and clause.startswith(("喜欢", "不喜欢", "不太喜欢", "讨厌", "偏爱")):
                clause = "我" + clause
            parsed = _parse_fact(clause)
            if parsed is None:
                inherited_subject = False
                continue
            inherited_subject = True
            value, domain, slot, summary, preference, change = parsed
            # 复句、转述及未解析的指代不落为独立原子事实。
            if any(word in value for word in ("但是", "因为", "所以", "他说", "她说", "觉得", "希望", "喜欢", "不喜欢", "不叫", "不是")):
                continue
            related = [m for m in active if m.metadata.get("fact_slot") == slot]
            reversal = [m for m in active if preference and m.metadata.get("fact_value") == value
                        and str(m.metadata.get("fact_slot", "")).startswith(f"preference:{domain}:")
                        and m.metadata.get("fact_slot") != slot]
            if reversal:
                related = reversal
            if any(m.summary == summary for m in related):
                continue
            target = related[0] if len(related) == 1 else None
            metadata = {"speaker": "user", "scene": "companion_chat", "original_quote": text,
                        "message_id": source_id, "recorded_at": datetime.now(timezone.utc).isoformat(),
                        "fact_slot": slot, "fact_domain": domain, "fact_value": value,
                        "confidence_reason": "明确第一人称自述，原话直接支持；未推断共同经历"}
            references = (f"{source_id}:{index}",)
            if ((related and not (correction or change or reversal)) or (correction and target is None)
                    or len(related) > 1 or self.mode == "review" or clause.startswith("我叫")):
                metadata["source_memory_ids"] = [m.memory_id for m in related]
                if target is not None:
                    metadata["supersedes_memory_id"] = target.memory_id
                candidate = MemoryCandidate(character_id=self.memory.character_id, owner_id=self.memory.owner_id,
                    kind="用户自述", title=domain, summary=summary, source="user_chat", occurred_at=now,
                    source_ids=references, tags=("关于你", domain), importance=0.72,
                    requires_user_confirmation=True, metadata=metadata)
                pending.append(self.memory.propose_candidate(candidate,
                    pending_id=candidate.to_memory(now=now).memory_id, expected_epoch=self.memory.store.context_epoch))
                continue
            epoch = self.memory.store.context_epoch
            if correction and target is not None:
                entry = self.memory.correct(target.memory_id, title=domain, summary=summary, now=now,
                    expected_epoch=epoch, source_ids=references, metadata=metadata)
            else:
                entry = self.memory.remember(kind="用户自述", title=domain, summary=summary, source="user_chat",
                    now=now, tags=("关于你", domain), user_confirmed=False, confidence=0.95,
                    supersedes=target.memory_id if (change or reversal) and target is not None else "",
                    preserve_occurred_at=not bool(change or reversal),
                    source_ids=references, metadata=metadata, expected_epoch=epoch)
            written.append(entry.memory_id)
            self.memory.promote_sourced_alias(entry, now=now)
            active = [m for m in active if target is None or m.memory_id != target.memory_id] + [entry]
            # 画像直接引用获准事实，每项绑定原记忆；模型不能自创画像证据。
            if slot.startswith("preference:"):
                self.memory.update_bond_profile(new_preference=entry.summary,
                    source_memory_ids=(entry.memory_id,), now=now, expected_epoch=self.memory.store.context_epoch)
        if pending:
            return ChatMemoryResult("pending", "这条信息需要确认或澄清，已放入回忆册待确认。", tuple(written))
        return ChatMemoryResult("saved" if written else "ignored", memory_ids=tuple(written))

    def _forget(self, text, active, *, now: int) -> ChatMemoryResult:
        target = forget_target(text)
        candidates = {key: _fact_view(candidate) for key, candidate in self.memory.pending_candidates.items()}
        domains = {m.metadata.get("fact_domain") for m in [*active, *candidates.values()]}
        requested = {domain for domain in domains if domain and domain in text}
        if any(term in text for term in ("饮料", "饮品", "喝什么")):
            requested.add("饮料偏好")
        selected = [m for m in active if m.metadata.get("fact_domain") in
                    requested]
        pending_ids = [key for key, candidate in candidates.items()
                       if candidate.metadata.get("fact_domain") in requested
                       or (candidate.metadata.get("fact_value") and candidate.metadata["fact_value"] in text)]
        if not selected:
            selected = [m for m in active if m.metadata.get("fact_value")
                        and m.metadata["fact_value"] in text]
        selected = list({m.memory_id: m for m in [*selected, *(m for m in active
                         if matches_forget_target(target, m))]}.values())
        pending_ids = list(dict.fromkeys([*pending_ids, *(key for key, candidate in candidates.items()
                                         if matches_forget_target(target, candidate))]))
        if not selected and any(term in text for term in ("饮料", "饮品", "喝什么")):
            selected = [m for m in active if m.metadata.get("fact_domain") == "饮料偏好"]
        if not selected and any(term in text for term in ("这件事", "刚才", "这条")) and len(active) == 1:
            selected = active
        if not selected and not pending_ids:
            return ChatMemoryResult("clarify", "你想忘记哪条信息？可以说出内容或在回忆册里选择。")
        for pending_id in pending_ids:
            self.memory.reject_candidate(pending_id, revoke_context=True)
        for entry in selected:
            self.memory.forget(entry.memory_id, now=now, expected_epoch=self.memory.store.context_epoch)
        return ChatMemoryResult("forgotten", "已经忘记了，这些内容也不会再用于画像和回忆。")
