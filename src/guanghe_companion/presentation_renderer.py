from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol

from .visual_actions import VisualAction, sprite_motion_override, visual_actions_from_dicts

RendererBackend = Literal["sprite", "live2d_web"]


@dataclass(frozen=True, slots=True)
class PresentationFrame:
    backend: RendererBackend
    motion: str
    visual_actions: tuple[VisualAction, ...] = ()
    model_path: str = ""
    live2d_actions: tuple[dict[str, str], ...] = ()


class PresentationRendererAdapter(Protocol):
    def frame_from_snapshot(self, snapshot: Mapping[str, object]) -> PresentationFrame:
        ...


class SpritePresentationAdapter:
    backend: RendererBackend = "sprite"

    def __init__(self, motion_map: Mapping[str, str] | None = None) -> None:
        self.motion_map = {
            key: value
            for key, value in dict(motion_map or {}).items()
            if isinstance(key, str) and isinstance(value, str) and key and value
        }

    def frame_from_snapshot(self, snapshot: Mapping[str, object]) -> PresentationFrame:
        visual_actions = _visual_actions(snapshot.get("visual_actions"))
        visual_motion = sprite_motion_override(visual_actions)
        motion = self.motion_map.get(visual_motion, visual_motion) if visual_motion else _snapshot_motion(snapshot)
        return PresentationFrame(
            backend=self.backend,
            motion=motion,
            visual_actions=visual_actions,
        )


class Live2DWebPresentationAdapter:
    backend: RendererBackend = "live2d_web"

    def __init__(
        self,
        *,
        model_path: str,
        motion_map: Mapping[str, str] | None = None,
        expression_map: Mapping[str, str] | None = None,
    ) -> None:
        self.model_path = model_path
        self.motion_map = _clean_string_map(motion_map)
        self.expression_map = _clean_string_map(expression_map)

    def frame_from_snapshot(self, snapshot: Mapping[str, object]) -> PresentationFrame:
        visual_actions = _visual_actions(snapshot.get("visual_actions"))
        live2d_actions = _live2d_actions(
            visual_actions,
            motion_map=self.motion_map,
            expression_map=self.expression_map,
        )
        visual_motion = sprite_motion_override(visual_actions)
        raw_motion = visual_motion or _snapshot_motion(snapshot)
        motion = self.motion_map.get(raw_motion, raw_motion)
        return PresentationFrame(
            backend=self.backend,
            motion=motion,
            visual_actions=visual_actions,
            model_path=self.model_path,
            live2d_actions=live2d_actions,
        )


def _visual_actions(value: object) -> tuple[VisualAction, ...]:
    if isinstance(value, tuple) and all(isinstance(action, VisualAction) for action in value):
        return value
    if isinstance(value, list):
        return visual_actions_from_dicts(value)
    return ()


def _live2d_actions(
    actions: tuple[VisualAction, ...],
    *,
    motion_map: Mapping[str, str],
    expression_map: Mapping[str, str],
) -> tuple[dict[str, str], ...]:
    mapped: list[dict[str, str]] = []
    for action in actions:
        if action.action_type == "expression":
            target = expression_map.get(action.action_id)
        elif action.action_type == "motion":
            target = motion_map.get(action.action_id)
        else:
            target = None
        if not target:
            continue
        mapped.append(
            {
                "type": action.action_type,
                "id": action.action_id,
                "mapped": target,
                "source": action.source,
            }
        )
    return tuple(mapped)


def _clean_string_map(value: Mapping[str, str] | None) -> dict[str, str]:
    return {
        key: item
        for key, item in dict(value or {}).items()
        if isinstance(key, str) and isinstance(item, str) and key and item
    }


def _snapshot_motion(snapshot: Mapping[str, object]) -> str:
    motion = snapshot.get("motion", "Default")
    return motion if isinstance(motion, str) and motion else "Default"
