"""Conservative typed read views for trusted legacy literal statements.

These fields are derived from the exact saved sentence, not new facts inferred
by a model. The canonical record, its original fingerprint and lifecycle stay
unchanged. Unsupported forms remain untyped and cannot answer precise slots.
"""
from dataclasses import replace
import re


def owned_pet_name(text):
    text = text.strip().rstrip("。！! ")
    reverse = re.fullmatch(r"(?:我|用户)(?:养|拥有)(?:了)?(?:一[只条个])?叫(?P<name>[^，。；！!?？的]{1,20})的(?P<kind>[^，。；！!?？的]{1,16})", text)
    forward = re.fullmatch(r"(?:我|用户)(?:的|养的|拥有的)(?P<kind>[^，。；！!?？的]{1,16}?)(?:的名字)?叫(?P<name>[^，。；！!?？]{1,20})", text)
    match = reverse or forward
    if match is None:
        return None
    # 复用现有宠物字段支持的物种；毛色等修饰语不能变成用户姓名。
    species = re.search(r"(兔子|鹦鹉|仓鼠|宠物|猫|狗)$", match["kind"])
    if species is None:
        return None
    return species[1], match["name"].strip()


def read_fact_view(entry):
    from .chat_memory import _fact_view, _parse_fact, _UNSUPPORTED
    trusted = entry.source in {"explicit_user_request", "user_correction", "profile_edit"}
    if trusted and not entry.metadata.get("fact_slot") and not entry.metadata.get("fact_predicate"):
        named = owned_pet_name(entry.summary)
        if named is not None:
            species, name = named
            return replace(entry, metadata={**entry.metadata, "fact_subject": "user:self",
                "fact_predicate": "宠物称呼:" + species, "fact_slot": "宠物称呼:" + species,
                "fact_domain": "宠物称呼", "fact_value": name})
    view = _fact_view(entry)
    # Original structured fields remain authoritative. A known literal title
    # can disambiguate an untyped, explicitly saved preference (named blends
    # need not contain a hard-coded drink noun).
    if (trusted and not entry.metadata.get("fact_slot") and not entry.metadata.get("fact_predicate")
            and entry.title in {"饮品偏好", "饮料偏好"}
            and str(view.metadata.get("fact_slot", "")).startswith("preference:")):
        return replace(view, metadata={**view.metadata, "fact_subject": "user:self", "fact_domain": "饮料偏好",
            "fact_slot": "preference:饮料偏好:" + view.metadata["fact_slot"].rsplit(":", 1)[-1]})
    if view.metadata.get("fact_slot") or view.metadata.get("fact_predicate"):
        return view
    if not trusted:
        return entry
    text = entry.summary.strip().rstrip("。！! ")
    if _UNSUPPORTED.search(text):
        return entry
    # A separate non-factual trailing clause such as “觉得很放松” does not
    # invalidate the preceding explicit preference. We expose that clause only.
    first = re.split(r"[，,。；;]", text, maxsplit=1)[0]
    # 已确认更正可以沿用原卡片的明确偏好领域，值仍只取当前更正文。
    if entry.supersedes and entry.user_confirmed and entry.title in {"饮品偏好", "饮料偏好", "个人偏好"}:
        changed = re.fullmatch(r"(?:现在|最近|目前)?(?:只)?(?:喜欢|偏爱|喝|吃|用)([^，。；;]{1,40})", first)
        if changed:
            domain = "饮料偏好" if entry.title in {"饮品偏好", "饮料偏好"} else entry.title
            return replace(entry, metadata={**entry.metadata, "fact_subject": "user:self",
                "fact_domain": domain, "fact_slot": f"preference:{domain}:like", "fact_value": changed[1]})
    english = re.fullmatch(r"My ([A-Za-z][A-Za-z -]{1,40}?) is ([^.;]{1,60})[.]?", first, re.I)
    if english and english[1].casefold() == entry.title.casefold():
        return replace(entry, metadata={**entry.metadata, "fact_subject": "user:self",
            "fact_predicate": entry.title, "fact_value": english[2]})
    labelled = re.fullmatch(r"(.{2,30}?)(?:已经改成|已经改为|已改成|已改为|改成|改为|是|为)([^，。；;]{1,60})", first)
    if labelled and labelled[1] == entry.title:
        # 标题与原文直接绑定字段和值，但没有主语时不推断属于用户本人。
        return replace(entry, metadata={**entry.metadata, "fact_predicate": entry.title,
                                        "fact_value": labelled[2]})
    activity = re.match(r"^(?:我|用户)(?:正在|最近|现在)(.+)$", first)
    if activity and entry.title.endswith("目标"):
        verbs = [activity[1][:length] for length in range(2, min(8, len(activity[1])))
                 if entry.title.endswith(activity[1][:length] + "目标")]
        if verbs:
            verb = max(verbs, key=len)
            return replace(entry, metadata={**entry.metadata, "fact_subject": "user:self",
                "fact_predicate": entry.title, "fact_value": activity[1][len(verb):]})
    drink = re.fullmatch(r"(?:用户|我)(?:的|喜欢的|偏好的|常喝的)(?:饮品|饮料)(?:是|为)([^，,。；;]{1,60})", first)
    if drink:
        return replace(entry, metadata={**entry.metadata, "fact_subject": "user:self",
            "fact_value": drink[1].strip(), "fact_domain": "饮料偏好", "fact_slot": "preference:饮料偏好:like"})
    parsed = _parse_fact(re.sub(r"^用户", "我", first))
    if parsed:
        value, domain, slot, _, _, _ = parsed
        return replace(entry, metadata={**entry.metadata, "fact_subject": "user:self",
            "fact_value": value, "fact_domain": domain, "fact_slot": slot})
    match = re.fullmatch(r"(?:用户|我)(?:的|用的|使用的)?(?P<object>[\u4e00-\u9fffA-Za-z]{1,16}?)"
        r"(?:的)?(?P<field>型号|品牌|序列号|生日|手机号|电话号码|联系电话)(?:是|为)(?P<value>[^，,。；;]{1,60})", first)
    if not match:
        return entry
    mapping = {"型号": ("device_model", "设备"), "品牌": ("device_brand", "设备"),
               "序列号": ("serial_number", "序列号"), "生日": ("birthday", "生日"),
               "手机号": ("phone", "手机号"), "电话号码": ("phone", "电话"), "联系电话": ("phone", "电话")}
    predicate, domain = mapping[match["field"]]
    return replace(entry, metadata={**entry.metadata, "fact_subject": "user:self",
        "fact_predicate": predicate, "fact_domain": domain, "fact_slot": predicate,
        "fact_value": match["value"].strip(), "fact_object": match["object"]})
