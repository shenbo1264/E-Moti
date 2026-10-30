"""Presentation-only text for chat memory modes, receipts and memory sources."""

from __future__ import annotations

from collections.abc import Mapping

CHAT_MEMORY_MODES = (
    ("auto", "自动记住明确的自述"),
    ("review", "先放进待确认，由我决定"),
    ("off", "不从聊天里记新内容"),
)

MODE_HELP = {
    "auto": "你明确说起自己的事会直接记下，并提示一句；有冲突或说不清时才来问你。",
    "review": "聊天里提到的事都先放进待确认，确认后才会记住。",
    "off": "不再从聊天推断新内容。“请记住”和“忘掉”依然有效。",
}

_SOURCE_LABELS = {
    "explicit_user_request": "你亲口要求记住",
    "user_correction": "你的纠正",
    "game_event": "你们一起经历的事",
    "relationship_unlock": "关系里程碑",
    "confirmed_companion_skill": "你确认完成的陪伴",
    "chat": "普通聊天",
}


def memory_receipt(result: Mapping[str, object] | None) -> str:
    """One line shown after a turn; an empty string means nothing to report."""

    if not result:
        return ""
    status = result.get("status")
    if status == "saved":
        return "记下了。不对的话可以在回忆册里改。"
    if status in {"pending", "clarify", "forgotten"}:
        return str(result.get("message") or "这件事放进待确认了，去回忆册看看。")
    return ""


def semantic_status_text(status: Mapping[str, object] | None) -> str:
    if not status or not status.get("enabled"):
        return "语义召回未开启，目前按字面匹配回忆。"
    state = status.get("state") or status.get("status")
    if state in {"ready", "loaded"}:
        return "语义召回已开启：换种说法也能想起来。"
    if state in {"failed", "error"}:
        return f"语义召回不可用：{status.get('error', '模型加载失败')}。目前按字面匹配。"
    return "语义召回准备中，首次需要下载约 95 MB 模型。"


def source_details_text(details: Mapping[str, object]) -> str:
    lines = [str(details.get("summary", ""))]
    source = str(details.get("source", ""))
    if source:
        lines.append(f"来源：{_SOURCE_LABELS.get(source, source)}")
    provenance = details.get("provenance")
    if isinstance(provenance, Mapping):
        if provenance.get("original_quote"):
            lines.append(f"你的原话：{provenance['original_quote']}")
        if provenance.get("confidence_reason"):
            lines.append(f"记下的理由：{provenance['confidence_reason']}")
    if "user_confirmed" in details:
        lines.append("你已确认" if details["user_confirmed"] else "未经你逐条确认")
    if details.get("version"):
        lines.append(f"版本：{details['version']}")
    if details.get("active") is False:
        lines.append("当前已失效，不会用于聊天")
    memories = details.get("source_memories")
    if isinstance(memories, (list, tuple)) and memories:
        lines.append("来自：" + "、".join(str(row.get("title", "")) for row in memories))
    return "\n".join(line for line in lines if line)
