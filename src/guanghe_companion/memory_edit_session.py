"""State of one open memory edit: keeps the draft through failures, never past a revoke."""

from __future__ import annotations

from dataclasses import dataclass

EDIT_INTENTS = (
    ("correct", "之前记错了", "新内容替换旧内容，旧内容不再保留为历史。"),
    ("change", "现在情况变了", "旧内容变成历史事实，只在问起过去时使用。"),
)


@dataclass(slots=True)
class MemoryEditSession:
    """The user's text is theirs until they discard it or the target is revoked."""

    memory_id: str
    character_id: str
    expected_epoch: int
    title: str
    summary: str
    closed_reason: str = ""
    notice: str = ""

    def on_album_changed(self, *, character_id: str, epoch: int, live_ids: set[str]) -> None:
        if self.closed_reason:
            return
        if character_id != self.character_id:
            self._close("角色已切换，这份编辑已关闭。")
        elif self.memory_id not in live_ids:
            self._close("这条记忆已被更正或忘记，这份编辑已关闭。")
        elif epoch != self.expected_epoch:
            # 目标仍有效：保留草稿，但要用户看过新状态后再提交，不自动重放。
            self.expected_epoch = epoch
            self.notice = "记忆刚刚有更新。这条还在，你的修改保留着，检查后再保存。"

    def on_save_failed(self, reason: str) -> None:
        if not self.closed_reason:
            self.notice = f"没有保存：{reason}。你写的内容还在。"

    def _close(self, reason: str) -> None:
        self.closed_reason, self.title, self.summary, self.notice = reason, "", "", ""


def save_failure_reason(error: Exception) -> str:
    text = str(error)
    if "future events remain plans" in text or "positive existing interval" in text:
        return "这条记录的生效时间不允许现在变更，请改用“之前记错了”"
    if "empty" in text or "too long" in text:
        return "内容不能为空，最多 240 字；标题最多 60 字"
    if "stale" in text:
        return "记忆刚刚有更新"
    if isinstance(error, OSError) or "database" in text or "locked" in text:
        return "存档暂时写不进去，稍后重试"
    return text or type(error).__name__
