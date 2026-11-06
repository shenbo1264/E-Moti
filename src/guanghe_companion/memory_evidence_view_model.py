"""How each retrieval status reads to a person. Presentation only.

None of these states is an error. In particular ``unknown`` means the current
search found nothing reliable; it does not mean the user never said it.
"""

from __future__ import annotations

from collections.abc import Iterable

_STATES = {
    "sufficient": ("ok", "有依据", "这句话有当前有效的记忆支撑，可以查看依据。"),
    "insufficient": ("partial", "只有部分依据", "只找到了一部分，缺的地方不会靠猜。可以看看已有记录，有不对的直接改。"),
    "unknown": ("quiet", "暂时没找到依据", "这次没有查到可靠记录。这不代表你没说过，也可能是这种说法还没认出来。"),
    "external_unavailable": ("quiet", "暂时看不到实时状态", "外部系统现在连不上或未接入，所以不判断它成功还是失败。"),
    "unavailable": ("pending", "记忆刚更新", "这份内容已经变化或被撤回，旧内容不再显示。刷新后再看。"),
}

_MISSING_LABELS = {"reason": "原因", "cause": "原因", "name": "名字", "color": "颜色", "count": "数量",
                   "location": "地点", "participant": "参与者", "steps": "操作步骤"}


def present_evidence(status: str, *, missing: Iterable[str] = ()) -> dict[str, str] | None:
    """``not_needed`` returns None: an ordinary chat shows no memory state at all."""
    if status not in _STATES:
        return None
    tone, label, detail = _STATES[status]
    named = [_MISSING_LABELS.get(str(item), str(item)) for item in missing if str(item).strip()]
    if status == "insufficient" and named:
        detail = f"有相关记录，但没有提到{'、'.join(dict.fromkeys(named))}。{detail}"
    return {"status": status, "tone": tone, "label": label, "detail": detail}
