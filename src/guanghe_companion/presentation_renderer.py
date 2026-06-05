from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol

from .visual_actions import VisualAction, sprite_motion_override, visual_actions_from_dicts

RendererBackend = Literal["sprite"]


@dataclass(frozen=True, slots=True)
class PresentationFrame:
    backend: RendererBackend
    motion: str
    visual_actions: tuple[VisualAction, ...] = ()


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


def _visual_actions(value: object) -> tuple[VisualAction, ...]:
    if isinstance(value, tuple) and all(isinstance(action, VisualAction) for action in value):
        return value
    if isinstance(value, list):
        return visual_actions_from_dicts(value)
    return ()


def _snapshot_motion(snapshot: Mapping[str, object]) -> str:
    motion = snapshot.get("motion", "Default")
    return motion if isinstance(motion, str) and motion else "Default"
