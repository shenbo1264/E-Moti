from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SnapshotRenderer:
    def snapshot_tts_speech(self, snapshot: dict[str, object]) -> str:
        character_name = str(snapshot.get("character_name", ""))
        events = snapshot.get("events")
        if not isinstance(events, list):
            return ""
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("character_name") != character_name:
                continue
            speech = str(event.get("speech", "")).strip()
            if speech:
                return speech
        return ""

    def format_relationship_presentation(self, snapshot: dict[str, object]) -> str:
        presentation = snapshot.get("relationship_presentation")
        if not isinstance(presentation, dict):
            return f"当前关系：{snapshot['relationship_stage']}\n下个解锁：{snapshot['next_relationship_unlock']}"
        decorations = presentation.get("unlocked_decorations")
        if isinstance(decorations, list) and decorations:
            decoration_text = " / ".join(str(entry.get("label", "")) for entry in decorations if isinstance(entry, dict))
        else:
            decoration_text = "暂无"
        return (
            f"当前关系：{snapshot['relationship_stage']}\n"
            f"{presentation.get('address_line', '')}\n"
            f"语气：{presentation.get('tone_label', '')} / 小动作：{presentation.get('micro_motion', '')}\n"
            f"装饰：{decoration_text}\n"
            f"下个解锁：{snapshot['next_relationship_unlock']}"
        )

    def format_desktop_status_panel(self, snapshot: dict[str, object]) -> str:
        return (
            f"模式：{snapshot['mode']}\n"
            f"能量 {int(float(snapshot['charge']))} / 心情 {int(float(snapshot['mood']))} / "
            f"信任 {int(float(snapshot['trust']))}\n"
            f"动作：{snapshot['motion_caption']}\n"
            f"{snapshot['feedback']}"
        )

    def format_memory_log(self, entries: object) -> str:
        if not entries:
            return "回忆日志：暂无回忆"
        lines = ["回忆日志："]
        for entry in list(entries)[:5]:
            lines.append(f"- {entry['kind']}：{entry['summary']}")
        return "\n".join(lines)

    def format_event_summary(self, events: object) -> str:
        if not isinstance(events, list) or not events:
            return "最近事件：暂无"
        lines: list[str] = []
        for event in events[:3]:
            if not isinstance(event, dict):
                continue
            character_name = str(event.get("character_name", ""))
            speech = str(event.get("speech", "")).strip()
            if not speech:
                continue
            if character_name == "STAT":
                lines.append(f"状态：{speech}")
            elif character_name == "CHOICE":
                lines.append(f"可选动作：{speech}")
            elif character_name:
                lines.append(f"{character_name}：{speech}")
        return "\n".join(lines) if lines else "最近事件：暂无"
