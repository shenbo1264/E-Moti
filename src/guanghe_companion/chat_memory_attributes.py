import re


ATTRIBUTE_DOMAIN = "对象属性"
_FIELD_ALIASES = {"位置": ("位置", "放在", "放哪里", "放在哪里", "存放"),
    "名字": ("名字", "名称", "叫什么", "命名", "叫"),
    "颜色": ("颜色", "色"), "偏好": ("偏好", "喜欢", "偏爱", "最常"),
    "容量": ("容量", "毫升", "升", "ml", "mL", "容量大小"), "内容": ("内容", "是")}
_UNSAFE = re.compile(r"[？?]|假如|假设|如果|可能|也许|据说|他说|她说|朋友说|故事里|游戏里|梦里|不确定|[‘’“”\"「」]")


def attribute_slot(fact):
    return "attribute:" + fact["subject"] + ":" + fact["field"]


def validate_attribute(proposal, current, text):
    fact = proposal.fact
    if (not isinstance(fact, dict) or set(fact) != {"subject", "field"}
            or any(not isinstance(value, str) or not 1 <= len(value) <= 40 for value in fact.values())
            or fact["subject"] in {"我", "你", "他", "她", "它", "这个", "那个"}
            or _UNSAFE.search(proposal.quote)):
        raise ValueError("attribute requires a literal subject and bounded field")
    field = fact["field"]
    explicit_field = any(term in proposal.quote for term in _FIELD_ALIASES.get(field, (field,)))
    related = [entry for entry in current.values() if entry.metadata.get("fact_slot") == attribute_slot(fact)]
    if proposal.action == "correct":
        if len(related) != 1 or proposal.target_ids != (related[0].memory_id,):
            return False
        if fact["subject"] in proposal.quote and explicit_field:
            return True
        attributes = [entry for entry in current.values() if entry.metadata.get("attribute_subject")]
        old_value = related[0].metadata.get("fact_value")
        old_matches = [entry for entry in attributes if entry.metadata.get("fact_value") == old_value]
        # 省略对象的更正必须明确引用唯一旧值；只有库中一条也不足以证明新句属于同一对象。
        return bool(re.search(r"改成|改为|换成|换了|说错|更正|现在", text) and
            isinstance(old_value, str) and old_value in text and len(old_matches) == 1)
    if fact["subject"] not in proposal.quote or not explicit_field:
        raise ValueError("attribute subject or field is not supported by the original claim")
    return not proposal.target_ids or all(target in {entry.memory_id for entry in related} for target in proposal.target_ids)


def attribute_metadata(fact):
    return {"fact_subject": "object:" + fact["subject"], "fact_predicate": fact["field"],
        "attribute_subject": fact["subject"], "attribute_field": fact["field"],
        "subject_aliases": [fact["subject"]]}


def matches_attribute_forget(target, metadata):
    subject, field = metadata.get("attribute_subject"), metadata.get("attribute_field")
    if not subject or not field or subject not in target:
        return False
    prefix = target[:target.index(subject)]
    if prefix and not re.search(r"(?:的|我|关于|听|用|选|挑|买)$", prefix):
        return False
    remainder = target.replace(subject, "", 1).strip("我的关于全部信息事情 ")
    return not remainder or any(term in remainder for term in _FIELD_ALIASES.get(field, (field,)))
