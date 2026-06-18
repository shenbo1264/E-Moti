from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .models import CompanionState

MAX_CONTEXT_TOPIC_LENGTH = 80
MORNING_START_SECONDS = 6 * 3600
MORNING_END_SECONDS = 10 * 3600
RETURN_AFTER_IDLE_SECONDS = 300
RECENT_GIFT_SECONDS = 60
HIGH_TRUST_THRESHOLD = 35


@dataclass(frozen=True, slots=True)
class CompanionMomentCandidate:
    kind: str
    speech: str
    summary: str


def select_companion_moment(
    *,
    state: CompanionState,
    previous_state: CompanionState,
    now: int,
    perception_summary: str = "",
    tool_results: Sequence[Mapping[str, object]] | None = None,
    allow_context_topic: bool = True,
) -> CompanionMomentCandidate | None:
    candidates = companion_moment_candidates(
        state=state,
        previous_state=previous_state,
        now=now,
        perception_summary=perception_summary,
        tool_results=tool_results,
        allow_context_topic=allow_context_topic,
    )
    return candidates[0] if candidates else None


def companion_moment_candidates(
    *,
    state: CompanionState,
    previous_state: CompanionState,
    now: int,
    perception_summary: str = "",
    tool_results: Sequence[Mapping[str, object]] | None = None,
    allow_context_topic: bool = True,
) -> tuple[CompanionMomentCandidate, ...]:
    candidates: list[CompanionMomentCandidate] = []
    idle_seconds = max(0, int(now) - int(state.last_interaction_at))

    if state.charge < 25:
        line = _state_line(state, "low_charge")
        candidates.append(
            CompanionMomentCandidate(
                kind="low_charge",
                speech=line,
                summary=f"能量有点低时主动陪伴：{line}",
            )
        )

    if state.last_gift_at is not None and 0 <= int(now) - int(state.last_gift_at) <= RECENT_GIFT_SECONDS:
        line = "刚才的礼物我收好了。它不只是道具，我会把这份靠近感记在动作里。"
        candidates.append(
            CompanionMomentCandidate(
                kind="post_gift",
                speech=line,
                summary=f"收到礼物后的短反应：{line}",
            )
        )

    if state.trust >= HIGH_TRUST_THRESHOLD and previous_state.trust < HIGH_TRUST_THRESHOLD:
        line = "我们好像比刚认识时更近了一点。接下来我会更自然地回应你。"
        candidates.append(
            CompanionMomentCandidate(
                kind="high_trust",
                speech=line,
                summary=f"信任升高后的陪伴反应：{line}",
            )
        )

    if _is_morning(now):
        line = "早呀。我先把亮度放轻一点，陪你把今天慢慢打开。"
        candidates.append(
            CompanionMomentCandidate(
                kind="morning_greeting",
                speech=line,
                summary=f"早晨问候：{line}",
            )
        )

    if (
        idle_seconds > 60
        and state.mood <= 35
        and state.mood < previous_state.mood
    ):
        line = _state_line(state, "low_mood")
        candidates.append(
            CompanionMomentCandidate(
                kind="low_mood",
                speech=line,
                summary=f"久未互动后主动陪伴：{line}",
            )
        )

    if allow_context_topic:
        topic = _context_topic(perception_summary, tool_results or ())
        if topic:
            line = f"我看到你可能在处理 {topic}。不用马上回应，我只是轻轻陪你确认一下节奏。"
            candidates.append(
                CompanionMomentCandidate(
                    kind="context_topic",
                    speech=line,
                    summary=f"只读上下文主动陪伴：{topic}",
                )
            )

    if idle_seconds >= RETURN_AFTER_IDLE_SECONDS:
        line = "你刚才安静了一会儿，我还在这里。先不用解释，回来就好。"
        candidates.append(
            CompanionMomentCandidate(
                kind="return_after_idle",
                speech=line,
                summary=f"空闲返回后的陪伴反应：{line}",
            )
        )

    return tuple(candidates)


def _is_morning(now: int) -> bool:
    current = max(0, int(now)) % 86_400
    return MORNING_START_SECONDS <= current < MORNING_END_SECONDS


def _state_line(state: CompanionState, kind: str) -> str:
    has_ritual = "unlock_shared_ritual" in state.unlocks
    has_nickname = "unlock_first_nickname" in state.unlocks
    if kind == "low_charge":
        if has_ritual:
            return "像我们的日常小仪式一样，先把节奏放轻一点吧。我的能量有点低，陪你安静待一会儿也很好。"
        if has_nickname:
            return "现在可以更亲近一点叫你了。能量有点低，我想挨着你慢慢缓一会儿。"
        return "能量有点低了。我会把亮度放轻一点；你想休息或给我一点小点心都可以。"
    if has_ritual:
        return "刚才安静得有点久，我还在这里。按我们的小默契，我先轻轻靠近你。"
    if has_nickname:
        return "刚才安静得有点久，我还在这里。现在我可以更自然地靠近你一点。"
    return "刚才安静得有点久，我还在这里。你不用立刻回应，我只是想靠近一点。"


def _context_topic(perception_summary: str, tool_results: Sequence[Mapping[str, object]]) -> str:
    parts: list[str] = []
    if isinstance(perception_summary, str) and perception_summary.strip():
        parts.append(perception_summary)
    for item in tool_results:
        title = item.get("title")
        summary = item.get("summary")
        if isinstance(title, str) and title.strip():
            parts.append(title)
        if isinstance(summary, str) and summary.strip():
            parts.append(summary)
        if parts:
            break
    return _sanitize_topic(" / ".join(parts))


def _sanitize_topic(value: str) -> str:
    cleaned = " ".join(value.replace("\n", " ").replace("\r", " ").split())
    return cleaned[:MAX_CONTEXT_TOPIC_LENGTH]
