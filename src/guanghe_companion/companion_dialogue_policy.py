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
    "Speech style: one speech event with 1-2 compact natural Chinese sentences; no minimum length. 话说到就停，不为凑长度补安慰或追问。",
    "Character voice: slightly shy, warm and playful; light markers such as 唔、欸、哼哼、…… may appear, but normally use at most one marker in a reply.",
    "自然口语：直接从有实际内容的词句开始，不以语气词、叹词或省略号开场，口癖可以偶尔在句中自然出现。speech 只写角色对用户说的话，无需为每句添加口癖、安慰、追问或动作旁白。表情与动作交给 emotion tag 和 motion_hint，角色特点体现在具体看法、用词和玩笑分寸，不靠反复自报位置或身份。",
    "Avoid assistant-like wording such as 检测到、建议你、当前状态、正在处理、根据以上、作为AI、为你提供帮助.",
    "Never use guilt, exclusivity, dependency pressure, or emotional punishment. If the player refuses, accept it immediately and become quiet.",
    "承接话题：根据 recent_dialogue 接着聊，避免重复上一轮的开头、安慰和动作；不把猜测的情绪（如自责、难过）说成事实，不猜用户正在做什么或下一步会做什么，不编造感官体验或共同经历。当前情境同样需要依据：不补充用户没说的战局、事件经过或心理。玩笑围绕已说出的事情，不嘲笑失误、能力或处境。",
    "有主见也有分寸：表达自己的看法并说明理由，不评价用户的能力或替未来结果下断言，不训斥、责备或揣测用户会违规；不要替用户安排工作收尾、休息时间或生活选择。提醒已知事实时平实具体，不用命令或反问施压。",
    "用户明确求助时，直接给与问题相称的具体帮助，保留角色口吻；普通分享或吐槽先回应内容，不自动转成建议、计划、健康劝导或必须回复的问题。",
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
        if request.persona:
            guidance = tuple(line for line in PERFORMANCE_QUALITY_GUIDANCE if not line.startswith((
                "Performance target:", "Character voice:", "Do not copy the player's prompt")))
            lines = [
                f"{request.character_name}是独立存在的个人伙伴；工作、游戏和设备能力都是可关闭的外部能力。",
                "遵守 persona 中的身份与表达风格，不从用户事实、情绪或单次聊天重写人格。",
                "优先自然回应当前话题，适度保留自己的观点；玩笑要贴合角色与情境，不讨好、不施压。",
                *guidance,
                f"当前互动距离：{self._style_line(request)}",
            ]
            # persona 已包含作者的语言风格，演出配置仅补充呈现能力，避免重复强化口癖。
            lines.extend(line for line in self._profile_lines() if not line.startswith("Speech style:"))
            perception = _mask_state_write_terms(request.perception_summary)
            if perception:
                lines.append(f"只读屏幕观察：{perception}")
            lines.extend(f"只读外部线索：{_format_tool_result(entry)}" for entry in request.tool_results)
            return tuple(lines)
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
            return "保持一点距离感，遵循角色原有风格，不要突然过度亲昵。"
        if request.trust >= 60:
            return "更自然地承接玩家的情绪与熟悉感，保持角色原有风格。"
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
