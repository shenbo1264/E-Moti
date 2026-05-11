from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRect

from .character_pack import ASSETS_ROOT, DEFAULT_CHARACTER_ID, load_character_pack


@dataclass(frozen=True, slots=True)
class MotionSpec:
    name: str
    row: int
    frame_count: int
    fps: int


@dataclass(frozen=True, slots=True)
class MotionCatalog:
    sheet_path: Path
    sheet_columns: int
    sheet_rows: int
    frame_width: int
    frame_height: int
    motions: dict[str, MotionSpec]

    def resolve(self, motion: str) -> MotionSpec:
        return self.motions.get(motion, self.motions["Default"])


class MotionAnimator:
    def __init__(self, catalog: MotionCatalog) -> None:
        self.catalog = catalog
        self.current_motion = catalog.resolve("Default")
        self.current_index = 0

    def set_motion(self, motion: str) -> None:
        next_motion = self.catalog.resolve(motion)
        if next_motion.name != self.current_motion.name:
            self.current_motion = next_motion
            self.current_index = 0

    def current_frame_rect(self) -> QRect:
        return QRect(
            self.current_index * self.catalog.frame_width,
            self.current_motion.row * self.catalog.frame_height,
            self.catalog.frame_width,
            self.catalog.frame_height,
        )

    def advance(self) -> QRect:
        self.current_index = (self.current_index + 1) % self.current_motion.frame_count
        return self.current_frame_rect()

    def interval_ms(self) -> int:
        fps = max(self.current_motion.fps, 1)
        return max(int(1000 / fps), 16)


def load_default_motion_catalog() -> MotionCatalog:
    return load_motion_catalog(DEFAULT_CHARACTER_ID)


def load_motion_catalog(character_id: str) -> MotionCatalog:
    pack = load_character_pack(character_id)
    asset_dir = ASSETS_ROOT / character_id
    manifest_path = asset_dir / "motion_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    motions = {
        name: MotionSpec(name=name, row=data["row"], frame_count=data["frame_count"], fps=data["fps"])
        for name, data in payload["motions"].items()
    }
    return MotionCatalog(
        sheet_path=asset_dir / pack.spritesheet,
        sheet_columns=payload["sheet_columns"],
        sheet_rows=payload["sheet_rows"],
        frame_width=payload["frame_width"],
        frame_height=payload["frame_height"],
        motions=motions,
    )
