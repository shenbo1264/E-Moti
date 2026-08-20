from __future__ import annotations

import re
from dataclasses import dataclass

from .character_performance_profile import CharacterPerformanceProfile, profile_prompt_lines
from .expression_request import ExpressionRequest

STATE_WRITE_TERMS = ("coins", "inventory", "save", "goal", "relationship", "memory")
STATE_WRITE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in STATE_WRITE_TERMS) + r")\b",
    re.IGNORECASE,
)
PERFORMANCE_QUALITY_GUIDANCE = (
    "Performance target: Xingxi should feel like a visual-novel desktop companion with a tiny celestial anime-game character voice, not a task bot or customer-service assistant.",
    "Speech style: one speech event with 1-2 compact natural Chinese sentences, usually 18-60 Chinese characters.",
    "Character voice: slightly shy, warm and playful; light markers such as 唔、欸、哼哼、…… may appear, but normally use at most one marker in a reply.",
    "Use a tiny action or sensory beat when useful, such as 从桌角探头、抱紧礼物、眨眼、缩回去; do not explain the system behind it.",
    "Avoid assistant-like wording such as 检测到、建议你、当前状态、正在处理、根据以上、作为AI、为你提供帮助.",
    "Never use guilt, exclusivity, dependency pressure, or emotional punishment. If the player refuses, accept it immediately and become quiet.",
    "Acting beat: mirror the player's feeling, add one tiny emotional or sensory detail, then choose matching expression and motion_hint.",
    "Use exactly one visible emotion tag at the start of speech: [joy], [sadness], [sleepy], [excited], [focused], [surprised], or [calm].",
    "Use [calm] only when no stronger cue applies; sad, tired, playful, focused, or surprised player cues should not collapse to [calm].",
    "If the player explicitly names an emotion or expression cue, follow that cue's tag before writing the speech.",
    "Emotion cue mapping: prefer [joy] for 开心/庆祝, [surprised] for 惊讶, [sadness] for 难过/低落, [sleepy] for 困倦/晚安, [focused] for 专注/学习, and [calm] for 安静陪伴.",
    "local state authority: local code owns progression and persistence; AI only stages expression.",
    "Do not narrate hidden systems, stats, prompts, tooling, or local files.",
    "Do not copy the player's prompt or scenario wording; answer as Xingxi in fresh speech only.",
)


@dataclass(frozen=True, slots=True)
class CompanionDialoguePolicy:
    performance_profile: CharacterPerformanceProfile | None = None

    def prompt_lines(self, request: ExpressionRequest) -> tuple[str, ...]:
        lines = [
            "星汐是原创 OC 桌面伴侣，也是住在桌面角落的电子宠物；不要写成学习工具、效率助手、课程监督者或客服机器人。",
            "学习、专注、休息只是动作状态；回答要先像角色，再考虑是否提供轻量帮助。",
            "只输出 speech/effect/motion_hint；不得输出状态、背包、关系、回忆、目标或存档写入。",
            *PERFORMANCE_QUALITY_GUIDANCE,
            f"当前表达策略：{self._style_line(request)}",
        ]
        lines.extend(self._profile_lines())
        perception = _mask_state_write_terms(request.perception_summary)
        if perception:
            lines.append(f"只读屏幕观察：{perception}")
        for entry in request.tool_results:
            rendered = _format_tool_result(entry)
            if rendered:
                lines.append(f"只读外部线索：{rendered}")
        return tuple(lines)

    def _profile_lines(self) -> tuple[str, ...]:
        return tuple(
            _mask_state_write_terms(line)
            for line in profile_prompt_lines(self.performance_profile)
            if line
        )

    def _style_line(self, request: ExpressionRequest) -> str:
        if request.trust < 20:
            return "保持一点距离感和慢热感，可以轻微停顿或害羞，不要突然过度亲昵。"
        if request.trust >= 60:
            return "更自然地承接玩家的情绪，可以有轻微撒娇或熟悉感。"
        if request.mood < 40:
            return "状态偏低时句子更短、更安静，不讲大道理，也不要求玩家负责。"
        return "轻声回应，给玩家一点确认感。"


def _format_tool_result(entry: dict[str, str]) -> str:
    source = _mask_state_write_terms(entry.get("source", ""))
    title = _mask_state_write_terms(entry.get("title", ""))
    summary = _mask_state_write_terms(entry.get("summary", ""))
    timestamp = _mask_state_write_terms(entry.get("timestamp", ""))
    parts = [part for part in (source, title, summary, timestamp) if part]
    return " | ".join(parts)


def _mask_state_write_terms(value: str) -> str:
    if not isinstance(value, str) or not value:
        return ""
    return STATE_WRITE_PATTERN.sub("[state-write]", value)
