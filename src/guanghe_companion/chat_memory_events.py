import re


EVENT_DOMAIN = "日常事件"
EVENT_STATES = frozenset({"planned", "completed", "not_occurred", "cancelled"})
_CONDITIONAL = re.compile(r"假如|假设|如果|也许|可能|据说|他说|她说|朋友说|小说|故事里|游戏里|游戏中|梦里|[？?‘’“”\"「」]|吗|才怪|反话|密码|验证码|私钥")
_NEGATED = re.compile(r"尚未|还没有|还没|从未|未曾|没有")
_PLAN = re.compile(r"约好|约定|预约|打算|准备|计划|将会|将要|要去|要在|要和|要把|明天|后天|下周|下星期|下个月")
_COMPLETE = re.compile(r"已经|已|完成|过|了")
_CANCEL = re.compile(r"取消|作废|撤销|不再")


def validate_event(proposal, current, text):
    event = proposal.event
    fields = {"anchor", "status", "participants", "time_text"}
    if not isinstance(event, dict) or not fields <= set(event) <= fields | {"activity", "context_quote"}:
        raise ValueError("invalid event claim fields")
    context = event.get("context_quote", proposal.quote)
    activity = event.get("activity", event["anchor"])
    if (not isinstance(context, str) or context not in text or proposal.quote not in context
            or event["status"] not in EVENT_STATES or not isinstance(event["anchor"], str)
            or not 2 <= len(event["anchor"]) <= 48 or event["anchor"] not in context
            or not isinstance(activity, str) or not activity or len(activity) > 48 or activity not in proposal.quote
            or not isinstance(event["time_text"], str) or len(event["time_text"]) > 80
            or event["time_text"] not in proposal.quote or proposal.value != proposal.quote
            or _CONDITIONAL.search(context)):
        raise ValueError("event requires a bounded literal source claim")
    participants = event["participants"]
    if (not isinstance(participants, list) or not 1 <= len(participants) <= 8
            or any(not isinstance(value, str) or not value or len(value) > 32
                   or value not in context for value in participants)
            or "我" not in participants):
        raise ValueError("event participants must be explicitly present in the user claim")
    if event["anchor"] in participants:
        raise ValueError("event anchor must identify its object or activity, not only a participant")
    state = event["status"]
    if (state == "planned" and (not (_PLAN.search(proposal.quote) or event["time_text"])
                or (_COMPLETE.search(proposal.quote) and not _PLAN.search(proposal.quote)))
            or state == "completed" and (not _COMPLETE.search(proposal.quote)
                or _NEGATED.search(proposal.quote) or _CANCEL.search(proposal.quote) or _PLAN.search(proposal.quote))
            or state == "not_occurred" and (not _NEGATED.search(proposal.quote)
                or re.search(r"不是|不确定|不知|未确认", proposal.quote))
            or state == "cancelled" and not _CANCEL.search(proposal.quote)):
        raise ValueError("event state is not supported by its source")
    targets = [current[key] for key in proposal.target_ids]
    if proposal.action == "correct":
        matching = [entry for entry in current.values()
            if event["anchor"] in entry.summary
            and entry.metadata.get("event_activity", entry.metadata.get("event_anchor")) == activity
            and set(entry.metadata.get("participant_names", ())) == set(participants)]
        if (len(targets) != 1 or len(matching) != 1 or matching[0].memory_id != targets[0].memory_id
                or event["anchor"] not in targets[0].summary):
            return False
    elif targets:
        return False
    for literal in (event["anchor"], *participants):
        if literal not in proposal.quote and text.count(literal) != 1:
            raise ValueError("event context support is not uniquely located")
    return True


def event_metadata(proposal, text):
    event = proposal.event
    participants = ["user:self" if value == "我" else "character:self" if value == "你"
        else "person:" + value for value in event["participants"]]
    supports = [[text.index(value), text.index(value) + len(value)]
        for value in dict.fromkeys((event["anchor"], *event["participants"])) if value not in proposal.quote]
    activity = event.get("activity", event["anchor"])
    return {"event_anchor": event["anchor"], "event_activity": activity, "event_status": event["status"],
        "participants": list(dict.fromkeys(participants)), "participant_names": event["participants"],
        "time_expression": event["time_text"], "fact_domain": EVENT_DOMAIN,
        "fact_slot": "event:" + event["anchor"] + ":" + activity, "fact_value": proposal.value,
        "source_support_spans": supports,
        "event_time_resolution": "literal_unresolved" if event["time_text"] else "not_stated",
        "profile_eligible": False}


def event_summary(proposal):
    event = proposal.event
    supports = [value for value in (event["anchor"], *event["participants"]) if value not in proposal.quote]
    return proposal.quote + ("（原文主体与对象：" + "、".join(supports) + "）" if supports else "")


def event_kind(proposal):
    if proposal.event["status"] == "completed":
        return "共同经历" if "你" in proposal.event["participants"] else "个人经历"
    return "用户计划" if proposal.event["status"] == "planned" else "日常事件"
