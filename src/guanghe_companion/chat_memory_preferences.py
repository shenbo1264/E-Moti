import re


_ACTION = r"制作|参加|做|挑|选|买|听|用|喝|吃|看|穿|戴|玩|写|读"


def preference_scope(quote):
    text = re.sub(r"^(?:最近|现在|平时)", "", quote)
    match = re.match(r"^我(?P<prefix>[^，。；!?？]{1,60}?)(?:最喜欢|更喜欢|喜欢|偏爱|最常听|固定听)", text)
    if not match:
        return None
    prefix = match["prefix"]
    actor = "user:self"
    if prefix.startswith("的"):
        related = re.fullmatch(r"的(?P<relation>[^的，。]{1,12}?)(?P<context>(?:" + _ACTION + r").+)", prefix)
        if not related:
            return None
        actor, prefix = "relation:" + related["relation"], related["context"]
    prefix = re.sub(r"^(?:现在|平时|最近|周末|一直|目前|以后|最|更|比较|也|还)+", "", prefix)
    if not re.match(r"^(?:" + _ACTION + r").+", prefix) or len(prefix) > 40:
        return None
    return {"subject": actor, "field": prefix}


def preference_slot(scope, polarity):
    return f"preference:{scope['subject']}:{scope['field']}:{polarity}"


def preference_metadata(scope, polarity):
    return {"fact_subject": scope["subject"], "fact_predicate": polarity,
        "preference_context": scope["field"], "preference_actor": scope["subject"],
        "fact_slot": preference_slot(scope, polarity)}


def scoped_preference_forget(target, metadata):
    context = metadata.get("preference_context")
    actor = metadata.get("preference_actor")
    if not context or context not in target:
        return False
    prefix = target[:target.index(context)]
    if actor == "user:self":
        return prefix.strip("我的自己关于 ") == ""
    relation = str(actor).removeprefix("relation:")
    return prefix.strip("我的关于 ") == relation
