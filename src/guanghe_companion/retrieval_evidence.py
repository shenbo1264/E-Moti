"""Category-specific evidence gates, separate from lexical/vector ranking."""
from __future__ import annotations

import re

from .emotional_memory import EmotionalMemoryEntry
from .emotional_memory_reflection import is_shared_experience
from .emotional_memory_retrieval import lexical_similarity
from .retrieval_contract import EvidenceDecision, RetrievalIntent
from .retrieval_fact_schema import read_fact_view
from .retrieval_literal import has_fact_value, literal_field_support, literal_subject_match


_MODEL_SOURCES = {"model", "assistant", "llm", "llm_generated", "model_generated", "assistant_generated"}
_UNFINISHED = {"planned", "proposed", "pending", "queued", "running", "in_progress",
               "awaiting_confirmation", "cancelled", "canceled"}
_QUESTION_WORDS = re.compile(
    r"还记得|记不记得|能不能|可不可以|请你|告诉我|说说|讲讲|聊聊|详细|具体|展开|一下|"
    r"我们|咱们|一起|共同|第一次|上一次|上次|那一次|那次|当时|后来|然后|"
    r"最近|以前|之前|现在|过去|曾经|发生了什么|发生什么|做了什么|是什么|为什么|怎么|如何|"
    r"什么颜色|什么部分|多少|多久|哪家店|哪个选项|几[个次天本盆杯辆只件页张台]|[一二两三四五六七八九十]+次|什么|哪些|哪个|哪里|是否|回事|经历|回忆|事情|记忆|"
    r"验证过程|修好|过程|最后|结果|回顾|之后|以前|来着|那只|那个|那台|那本|这只|我|给|还|的|了|吗|呢|呀|啊"
)


def fact_view(entry: EmotionalMemoryEntry) -> EmotionalMemoryEntry:
    # Shared with write-side legacy support; no free-form model extraction.
    return read_fact_view(entry)


def is_unfinished_event(entry: EmotionalMemoryEntry) -> bool:
    return entry.metadata.get("planned") is True or any(
        isinstance(entry.metadata.get(key), str) and entry.metadata[key] in _UNFINISHED
        for key in ("event_status", "plan_status", "task_status", "status"))


def grounded_shared_event(entry: EmotionalMemoryEntry) -> bool:
    if not entry.source_ids or entry.source.casefold() in _MODEL_SOURCES:
        return False
    if is_unfinished_event(entry):
        return False
    # 执行回执证明执行者的报告；共同经历还需要用户验收。
    if (entry.source in {"executor", "relay", "task_executor"}
            or entry.metadata.get("user_accepted") is False):
        if entry.metadata.get("user_accepted") is not True:
            return False
    if is_shared_experience(entry):
        return True
    participants = entry.metadata.get("participants", ())
    return (entry.kind in {"共同经历", "共同日常", "shared_experience"}
            and entry.metadata.get("event_status") in {"completed", "succeeded", "failed"}
            and isinstance(participants, (tuple, list))
            and "user:self" in participants and "character:self" in participants)


def topic_terms(query: str) -> tuple[str, ...]:
    # Dates are enforced by structured occurrence/validity constraints. They
    # need not also appear verbatim in the saved narrative's body.
    query = re.sub(r"(?:20\d{2}年)?\d{1,2}月(?:\d{1,2}[日号])?|20\d{2}-\d{1,2}-\d{1,2}", " ", query)
    stripped = _QUESTION_WORDS.sub(" ", query.casefold())
    terms = []
    for word in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9_]+", stripped):
        if len(word) == 1:
            if word not in {"我", "你", "他", "她", "它", "用", "去", "来", "说", "问", "想", "在", "和", "与", "个"}:
                terms.append(word)
        elif all("\u4e00" <= c <= "\u9fff" for c in word):
            terms.extend(word[i:i + 2] for i in range(len(word) - 1))
        else:
            terms.append(word)
    return tuple(dict.fromkeys(terms))


def _legacy_literal_support(entry: EmotionalMemoryEntry, intent: RetrievalIntent) -> bool:
    """Verify a narrow literal attribute in an old untyped explicit save.

    This is the bounded raw-source verification path, not another authoritative
    extractor. It requires an exact normalized attribute/context match. Neither
    embeddings nor a broad shared noun can turn an unknown slot into evidence.
    """
    from .chat_memory import _UNSUPPORTED
    if (intent.subjects != ("user:self",) or not entry.source_ids
            or entry.source not in {"explicit_user_request", "user_correction", "profile_edit"}
            or _UNSUPPORTED.search(entry.summary)
            or re.search(r"可能|大概|也许|不确定|如果|假设", entry.summary)):
        return False
    text = re.split(r"[，,。；;]", entry.summary.strip(), maxsplit=1)[0]
    query = re.sub(r"^(?:帮我|请你|请)?(?:回想|回忆|告诉我)?(?:一下)?", "", intent.query)
    query = re.sub(r"^(?:现在|目前|如今)", "", query)

    def attribute(value):
        value = re.sub(r"^(?:我|用户)(?:的)?", "", value)
        return re.sub(r"哪[一种个家本]|什么|是|的|[?？。 ]", "", value)

    # “我 + attribute + 是/已改成 + literal value”. The full attribute is
    # matched, including time/activity modifiers; a friend's fact differs.
    statement = re.fullmatch(r"(?:我|用户)(?P<attribute>[^，。；;]{2,28}?)(?:已经改成|已经改为|已改成|已改为|改成|改为|是|为)(?P<value>[^，。；;]{1,60})", text)
    if statement and (intent.predicates == ("unresolved_field",)
                      or "habit" in intent.predicates):
        return bool(re.match(r"^(?:我|用户)", query)
                    and attribute(statement["attribute"]) == attribute(query))
    # Contextual preferences are only valid for the same stated context and
    # object, e.g. train-seat preferences cannot answer plane-seat preferences.
    preference = re.fullmatch(r"(?P<context>[^，。；;]{2,20}(?:时|时候))(?:我|用户)(?:偏爱|偏好|喜欢)(?P<value>[^，。；;]{1,60})", text)
    requested = re.fullmatch(r"(?P<context>[^，。；;]{2,20}(?:时|时候))(?:我|用户)?(?:的)?(?P<object>[\u4e00-\u9fff]{2,12})偏好(?:是什么|什么)?[?？]?", query)
    return bool(preference and requested and preference["context"] == requested["context"]
                and requested["object"] in preference["value"]
                and set(intent.predicates).intersection({"个人偏好", "preference:个人偏好:like"}))


def _field_matches(intent: RetrievalIntent, entry: EmotionalMemoryEntry) -> bool:
    meta = entry.metadata
    fields = {str(meta.get(key, "")) for key in ("fact_predicate", "fact_slot", "fact_domain")}
    if not fields.intersection(intent.predicates):
        return literal_field_support(entry, intent.query)
    pet_species = next((field.split(":", 1)[1] for field in intent.predicates if field.startswith("宠物称呼:")), "")
    if pet_species:
        # Old extraction used the broad `pet` slot. It is only a name answer
        # when the saved literal actually connects this species to that name.
        species = r"猫|狗|兔子|鹦鹉|仓鼠|宠物" if pet_species == "宠物" else re.escape(pet_species)
        named = re.search(r"(?:" + species + r")(?:的)?(?:名字)?叫([^，。；！!?？]{1,20})", entry.summary)
        if named is None:
            return False
        value = str(meta.get("fact_value", ""))
        return bool(value and (value == named[1].strip() or named[1].strip() in value))
    # Domain alone cannot convert dislike into allergy, or a street address
    # request into a city-level fact. These are separate evidence claims.
    if "过敏" in intent.query and not re.search(r"(?:不能|不应|不要|别).*(?:当成|等同).*过敏", intent.query) and not fields.intersection({"过敏", "allergy"}):
        return False
    if re.search(r"街道|门牌|详细地址|具体地址", intent.query):
        return bool(fields.intersection({"street_address", "街道地址", "详细地址"}))
    if re.search(r"最喜欢|最爱", intent.query) and meta.get("preference_strength") not in {"favorite", "most"}:
        return bool(re.search(r"最喜欢|最爱|最偏爱", entry.summary))
    if fields.intersection({"device", "device_model", "device_brand", "设备", "price", "purchase_price", "purchase_date", "serial_number"}):
        obj = re.search(r"(?:我那台|我的?|用户的)([\u4e00-\u9fff]{1,10}?)(?:是什么|是|的|型号|序列号|花了|买)", intent.query)
        if obj and obj[1] not in {"名字", "姓名"} and obj[1] not in entry.summary and obj[1] != meta.get("fact_object"):
            return False
    if fields.intersection({"style_preference", "互动偏好"}):
        return True
    if re.search(r"(?:不能|不应|不要|别).*(?:当成|等同).*过敏", intent.query):
        return any("avoid" in field for field in fields) or "长期忌口" in fields
    if re.search(r"不喜欢|讨厌|别放|不要加|不想加", intent.query):
        return (any("avoid" in field for field in fields) or bool(re.search(r"不喜欢|讨厌|不吃|不要|忌口", entry.summary)))
    if re.search(r"喜欢|偏爱", intent.query) and not re.search(r"不喜欢|讨厌", intent.query):
        return not (any("avoid" in field for field in fields) or bool(re.search(r"不喜欢|讨厌", entry.summary)))
    # A narrow activity request must match that activity, not merely the wide
    # preference/habit/schedule bucket (e.g. swimming vs guitar lessons).
    if fields.intersection({"每周安排", "习惯", "habit", "个人偏好"}):
        query_terms = topic_terms(re.sub(r"我|用户|每周|星期|周几|哪天|习惯|爱好|兴趣|喜欢|偏好|安排", " ", intent.query))
        if query_terms and not any(term in (entry.summary + " " + str(meta.get("fact_value", ""))).casefold()
                                   for term in query_terms):
            return False
    return True


def _supported_details(entry: EmotionalMemoryEntry, intent: RetrievalIntent) -> tuple[str, ...]:
    text, meta = entry.summary, entry.metadata
    signals = {
        "cause": bool(meta.get("cause") or meta.get("root_cause") or re.search(r"因为|由于|原因是|因.{1,24}(?:导致|失败)|导致|日志(?:确认|指出|表明|显示)|故障是", text)),
        "color": bool(meta.get("color") or re.search(r"(?:红|橙|黄|绿|青|蓝|紫|黑|白|灰|粉|棕|金|银|透明)(?:色|釉)|颜色(?:是|为)", text)),
        "quantity": bool(meta.get("quantity") or meta.get("duration") or re.search(r"[0-9零一二三四五六七八九十百两]+(?:个|次|分钟|秒|小时|天|本|张|盆|杯|辆|只|件|页|台|公里|米)", text)),
        "location": bool(meta.get("location") or meta.get("venue") or re.search(r"(?:在|去了|到)[^，。]{1,24}(?:店|馆|园|宿舍|家|广场|餐厅|书房)", text)),
        "participant": bool(any(p not in {"user:self", "character:self"} for p in meta.get("participants", ())
                                if isinstance(p, str)) or meta.get("participant_names")),
        "title": bool(meta.get("work_title") or meta.get("book_title") or re.search(r"《[^》]+》|(?:电影|书|游戏)(?:叫|名为)", text)),
        "procedure": bool(meta.get("procedure") or re.search(r"更新|重启|开启|选择|配置|替换|清理|执行|重装|关闭|修正|添加|删除|改为|统一为|调整为|换成", text)),
    }
    # An explanation for a different outcome is not evidence of the requested
    # emotion/action, even when the two happened around the same object.
    if "cause" in intent.details:
        for action in ("哭", "笑", "生气", "难过", "坏", "失败"):
            if action in intent.query and action not in text and action not in str(meta.get("outcome", "")):
                if action != "失败" or meta.get("outcome") not in {"failed", "failure"}:
                    signals["cause"] = False
    return tuple(detail for detail in intent.details if signals.get(detail, False))


def check_eligibility(entry: EmotionalMemoryEntry, intent: RetrievalIntent, *, now: int,
                      owner_id: str, character_id: str) -> EvidenceDecision | None:
    supported = _supported_details(entry, intent)
    def result(ok: bool, reason: str):
        return EvidenceDecision(entry.memory_id, ok, reason, intent.route, supported,
                                tuple(d for d in intent.details if d not in supported))
    if entry.owner_id != owner_id or entry.character_id != character_id or entry.scope not in intent.scopes:
        return result(False, "wrong_owner_character_or_scope")
    if entry.deleted or entry.confidence <= 0 or entry.source.casefold() in _MODEL_SOURCES:
        return result(False, "revoked_or_untrusted_source")
    if intent.temporal_mode == "unresolved":
        return result(False, "unresolved_time_basis_or_date")
    if entry.valid_from > now:
        return result(False, "not_yet_valid")
    expired = bool(entry.valid_until and now >= entry.valid_until)
    if intent.temporal_mode == "history":
        if not expired and entry.metadata.get("fact_status") != "historical":
            return result(False, "current_fact_not_historical")
    elif intent.temporal_mode == "as_of" or (intent.temporal_mode == "planned" and intent.as_of is not None):
        as_of = intent.as_of
        end = intent.as_of_end
        if intent.temporal_mode == "planned":
            from zoneinfo import ZoneInfo
            from .retrieval_router import _temporal
            # 计划发生日来自原文，不拿记录时间代替；档案时区与日历查询一致。
            basis = entry.metadata.get("time_basis")
            mode, target, target_end = _temporal(entry.summary, now=entry.created_at,
                calendar_zone=ZoneInfo(entry.metadata.get("timezone") or "UTC"))
            date_parts = re.findall(
                r"(?:\d{4}[-/年])?[0-9零〇一二三四五六七八九十两]{1,3}(?:月|[-/])[0-9零〇一二三四五六七八九十两]{1,3}(?:日|号)?",
                entry.summary)
            dates = {_temporal(part, now=entry.created_at,
                calendar_zone=ZoneInfo(entry.metadata.get("timezone") or "UTC")) for part in date_parts}
            # 一段原文同时有登记日、改期日等时，不把第一个日期猜成计划发生日。
            if len(dates) > 1:
                return result(False, "ambiguous_plan_dates")
            if (basis == "logical" or mode != "as_of" or target is None or target_end is None
                    or target < as_of or (end is not None and target_end > end)):
                return result(False, "outside_requested_plan_date_or_unproved")
            if (entry.valid_from and entry.valid_from >= (end or as_of + 1)) or (entry.valid_until and as_of >= entry.valid_until):
                return result(False, "outside_requested_valid_time")
        elif intent.route in {"episode", "task"}:
            if as_of is None or entry.occurred_at < as_of or (end is not None and entry.occurred_at >= end):
                return result(False, "outside_requested_event_time")
        else:
            starts_after = ((entry.valid_from or entry.occurred_at) >= end if end is not None
                            else (entry.valid_from or entry.occurred_at) > as_of) if as_of is not None else True
            if as_of is None or starts_after or (entry.valid_until and as_of >= entry.valid_until):
                return result(False, "outside_requested_valid_time")
    elif intent.temporal_mode != "timeline" and expired:
        return result(False, "expired_current_evidence")
    planned = (entry.metadata.get("planned") is True or entry.metadata.get("plan_status") == "planned"
               or entry.metadata.get("event_status") in {"planned", "proposed"})
    if intent.temporal_mode == "planned":
        if not planned:
            return result(False, "not_a_plan")
    elif planned:
        return result(False, "plan_is_not_completed_event_or_current_fact")
    elif intent.route in {"episode", "task", "bounded"} and is_unfinished_event(entry):
        return result(False, "unfinished_event_is_not_completed_experience")
    if intent.requires_shared_event and not grounded_shared_event(entry) and intent.temporal_mode != "planned":
        return result(False, "missing_completed_shared_event_evidence")
    if intent.route == "task":
        allowed_outcomes = {"planned"} if intent.temporal_mode == "planned" else {"completed", "succeeded", "success", "failed", "failure"}
        if not entry.source_ids or entry.metadata.get("outcome") not in allowed_outcomes:
            return result(False, "missing_execution_outcome")
        if intent.app and str(entry.metadata.get("app", "")).casefold() != intent.app.casefold():
            return result(False, "application_mismatch")
        if intent.version and str(entry.metadata.get("version", "")).lstrip("v") != intent.version:
            return result(False, "application_version_mismatch")
    return None


def check_evidence(entry: EmotionalMemoryEntry, intent: RetrievalIntent, *, now: int,
                   owner_id: str, character_id: str) -> EvidenceDecision:
    hard_rejection = check_eligibility(entry, intent, now=now, owner_id=owner_id, character_id=character_id)
    if hard_rejection is not None:
        return hard_rejection
    supported = _supported_details(entry, intent)
    def result(ok: bool, reason: str):
        return EvidenceDecision(entry.memory_id, ok, reason, intent.route, supported,
                                tuple(d for d in intent.details if d not in supported))
    planned = intent.temporal_mode == "planned"
    view = fact_view(entry)
    if (view.metadata.get("fact_subject") or view.metadata.get("fact_slot")) and not literal_subject_match(view, intent.subjects, intent.query):
        return result(False, "subject_mismatch_or_unproved")
    if intent.route == "fact":
        if (not view.metadata.get("fact_slot") and not view.metadata.get("fact_predicate")
                and _legacy_literal_support(entry, intent)):
            return result(True, "verified_legacy_literal_attribute")
        subject = str(view.metadata.get("fact_subject") or ("user:self" if view.metadata.get("fact_slot") else ""))
        entity = str(view.metadata.get("entity_id", ""))
        if intent.subjects and subject not in intent.subjects and entity not in intent.subjects:
            return result(False, "subject_mismatch_or_unproved")
        if intent.predicates and not _field_matches(intent, view):
            return result(False, "field_mismatch_or_unproved")
        if not has_fact_value(view.metadata) and not planned:
            return result(False, "missing_literal_fact_value")
        return result(True, "structured_subject_field_time_match")
    if intent.route == "bounded" and (view.metadata.get("fact_predicate") or view.metadata.get("fact_slot")):
        return result(literal_field_support(view, intent.query), "bounded_literal_attribute_verification")
    searchable = " ".join((entry.title, entry.summary, *entry.tags)).casefold()
    quoted = re.findall(r"《([^》]+)》|[“\"]([^”\"]+)[”\"]", intent.query)
    if any((a or b).casefold() not in searchable for a, b in quoted):
        return result(False, "explicit_named_topic_mismatch")
    if intent.details and not supported:
        return result(False, "requested_detail_not_supported")
    if (intent.route == "episode" and "title" in supported and not quoted
            and re.search(r"(?:读|看).*(?:哪本书|哪部电影|什么电影)", intent.query)
            and re.search(r"读|阅读|看|观影", entry.summary)):
        return result(True, "grounded_media_title")
    if (intent.route == "task" and intent.app and "失败后" in intent.query
            and supported and entry.metadata.get("app") == intent.app):
        return result(True, "same_application_execution_evidence")
    terms = topic_terms(intent.query)
    matching = [term for term in terms if term in searchable]
    if not terms:
        if intent.route == "episode" and grounded_shared_event(entry):
            return result(True, "grounded_general_episode_request")
        return result(False, "no_resolved_topic")
    # Lexical anchors substantiate a topic, not factual correctness. The
    # structured/event gates above do that. Semantic signals rank this set and
    # can propose a second bounded set, but cannot bypass these checks.
    coverage = len(matching) / len(terms) if terms else 0
    if matching and (coverage >= .5 or (len(terms) <= 2 and len(matching) == len(terms))):
        return result(True, "category_and_topic_supported")
    if matching and coverage >= .4 and lexical_similarity(intent.query, searchable) >= .18:
        return result(True, "category_and_lexical_support")
    return result(False, "topic_not_supported")

