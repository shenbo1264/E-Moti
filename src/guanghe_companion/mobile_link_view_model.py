"""Presentation-only text for the desktop phone connection page."""

from __future__ import annotations

INVITATION_LIFETIME_SECONDS = 300

_STATUS_TEXT = {
    "unsupported": "当前控制器未启用手机连接。",
    "missing_dependency": "缺少手机连接组件。请在项目目录运行 pip install -e \".[host]\" 后重启。",
    "stopped": "手机连接已关闭。开启后只在本机地址 127.0.0.1:{port} 监听，不会开机自启。",
    "starting": "正在开启手机连接……",
    "running": "手机连接已开启：127.0.0.1:{port}。配对设备可以和当前角色聊天、管理回忆；不能观察屏幕或执行任务。",
    "failed": "手机连接启动失败：端口 {port} 可能被占用。关闭占用程序后重试。",
}


def link_status_view(state: str, *, port: int) -> dict[str, object]:
    return {
        "text": _STATUS_TEXT[state].format(port=port),
        "can_start": state in {"stopped", "failed"},
        "can_stop": state in {"starting", "running"},
        "can_invite": state == "running",
    }


def invitation_view(code: str | None, *, created_at: float | None, now: float) -> dict[str, object]:
    if not code or created_at is None:
        return {"code": "", "remaining_seconds": 0, "expired": False, "text": "尚未生成邀请码。"}
    remaining = int(created_at + INVITATION_LIFETIME_SECONDS - now)
    if remaining <= 0:
        return {"code": "", "remaining_seconds": 0, "expired": True,
                "text": "邀请码已过期，请重新生成。"}
    minutes, seconds = divmod(remaining, 60)
    return {"code": code, "remaining_seconds": remaining, "expired": False,
            "text": f"邀请码一次有效，剩余 {minutes}:{seconds:02d}。只在自己的手机上输入。"}


def device_rows(devices: list[dict], *, now: float) -> list[dict[str, object]]:
    rows = []
    for device in devices:
        status = device["status"]
        if status == "active":
            days = max(0, int((device["expires_at"] - now) // 86400))
            detail = f"已连接 · {days} 天后到期" if days else "已连接 · 今天到期"
        elif status == "revoked":
            detail = "已撤销"
        else:
            detail = "已过期，需要重新配对"
        rows.append({"device_id": device["device_id"], "title": f"{device['name']}（{detail}）",
                     "can_revoke": status == "active"})
    return rows
