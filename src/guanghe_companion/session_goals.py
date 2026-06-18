from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SessionGoalDefinition:
    goal_id: str
    label: str
    description: str
    target: int
    suggested_action_id: str
    suggested_label: str
    reward: dict[str, int]

    def accepts(self, event_type: str, action_id: str) -> bool:
        if self.goal_id == "interact_twice":
            return event_type == "action" and action_id in {"touch", "soothe", "rest", "study", "play", "drag"}
        if self.goal_id == "rest_once":
            return event_type == "action" and action_id == "rest"
        if self.goal_id == "give_gift":
            return event_type == "inventory" and action_id == "gift"
        if self.goal_id == "switch_expression_route":
            return event_type == "expression_route"
        return False


@dataclass(frozen=True, slots=True)
class SessionGoalResult:
    completed_goal_id: str = ""
    completed_label: str = ""
    reward: dict[str, int] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, object] | None:
        if not self.completed_goal_id:
            return None
        return {
            "goal_id": self.completed_goal_id,
            "label": self.completed_label,
            "coins": int(self.reward.get("coins", 0)),
            "exp": int(self.reward.get("exp", 0)),
        }


SESSION_GOALS: tuple[SessionGoalDefinition, ...] = (
    SessionGoalDefinition(
        goal_id="interact_twice",
        label="互动两次",
        description="用两个小动作把今天的陪伴节奏打开。",
        target=2,
        suggested_action_id="touch",
        suggested_label="轻触",
        reward={"coins": 2, "exp": 1},
    ),
    SessionGoalDefinition(
        goal_id="rest_once",
        label="休息一次",
        description="让星汐放低频率，完成一次安静休息。",
        target=1,
        suggested_action_id="rest",
        suggested_label="休息",
        reward={"coins": 1, "exp": 1},
    ),
    SessionGoalDefinition(
        goal_id="give_gift",
        label="送出一份礼物",
        description="从背包里送出一份礼物，观察她的本地反应。",
        target=1,
        suggested_action_id="gift",
        suggested_label="赠送礼物",
        reward={"coins": 2, "exp": 2},
    ),
    SessionGoalDefinition(
        goal_id="switch_expression_route",
        label="切换表达路线",
        description="切换一次表达路线或角色呈现方式，观察舞台表现。",
        target=1,
        suggested_action_id="open_expression_settings",
        suggested_label="切换表达路线",
        reward={"coins": 1, "exp": 1},
    ),
)


class SessionGoalTracker:
    def __init__(self, goals: tuple[SessionGoalDefinition, ...] = SESSION_GOALS) -> None:
        if not goals:
            raise ValueError("session goal tracker requires at least one goal")
        self._goals = goals
        self._index = 0
        self._progress = 0

    @property
    def current_goal(self) -> SessionGoalDefinition:
        return self._goals[self._index % len(self._goals)]

    def snapshot(self) -> dict[str, object]:
        goal = self.current_goal
        return {
            "goal_id": goal.goal_id,
            "label": goal.label,
            "description": goal.description,
            "progress": self._progress,
            "target": goal.target,
            "reward": dict(goal.reward),
        }

    def suggested_action(self) -> dict[str, object]:
        goal = self.current_goal
        return {
            "action_id": goal.suggested_action_id,
            "label": goal.suggested_label,
        }

    def record_event(self, event_type: str, *, action_id: str = "") -> SessionGoalResult:
        goal = self.current_goal
        if not goal.accepts(event_type, action_id):
            return SessionGoalResult()
        self._progress = min(goal.target, self._progress + 1)
        if self._progress < goal.target:
            return SessionGoalResult()
        result = SessionGoalResult(
            completed_goal_id=goal.goal_id,
            completed_label=goal.label,
            reward=dict(goal.reward),
        )
        self._index = (self._index + 1) % len(self._goals)
        self._progress = 0
        return result
