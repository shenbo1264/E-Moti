"""Conservative typed read views for trusted legacy literal statements.

These fields are derived from the exact saved sentence, not new facts inferred
by a model. The canonical record, its original fingerprint and lifecycle stay
unchanged. Unsupported forms remain untyped and cannot answer precise slots.
"""
from dataclasses import replace
import re


def read_fact_view(entry):
    from .chat_memory import _fact_view, _parse_fact, _UNSUPPORTED
    view = _fact_view(entry)
    trusted = entry.source in {"explicit_user_request", "user_correction", "profile_edit"}
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
