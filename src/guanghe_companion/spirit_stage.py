from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from PySide6.QtCore import QPropertyAnimation, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

from .presentation_renderer import PresentationFrame

REQUIRED_PORTRAIT_EXPRESSIONS = ("neutral", "smile", "thinking", "surprised", "sad", "sleepy")
MAX_PORTRAIT_WIDTH = 4096
MAX_PORTRAIT_HEIGHT = 4096


@dataclass(frozen=True, slots=True)
class PortraitManifest:
    manifest_path: str
    fallback_expression: str
    anchor: str
    default_scale: float
    expressions: dict[str, str]


class PortraitManifestError(ValueError):
    pass


class SpiritStageSurface(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.loaded_frames: list[tuple[PresentationFrame, object]] = []
        self.last_portrait_path = ""
        self._source_pixmap = QPixmap()
        self._current_expression = ""
        self._opacity = QGraphicsOpacityEffect(self)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setDuration(160)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(1.0)
        self.setObjectName("SpiritStageSurface")
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.setMinimumHeight(300)

    def load_frame(self, frame: PresentationFrame, asset_dir: object) -> None:
        self.loaded_frames.append((frame, asset_dir))
        try:
            portrait_path = resolve_portrait_image_path(
                asset_dir,
                frame.portrait_manifest,
                frame.portrait_id,
            )
        except (OSError, PortraitManifestError, json.JSONDecodeError) as exc:
            self.last_portrait_path = ""
            self._source_pixmap = QPixmap()
            self.clear()
            self.setText(str(exc))
            return

        pixmap = QPixmap(str(portrait_path))
        if pixmap.isNull():
            self.last_portrait_path = ""
            self._source_pixmap = QPixmap()
            self.clear()
            self.setText(f"portrait image failed to load: {portrait_path.name}")
            return

        next_expression = frame.portrait_id or portrait_path.stem
        self.last_portrait_path = str(portrait_path)
        self._source_pixmap = pixmap
        self.setText("")
        self._set_scaled_pixmap()
        if not self._current_expression:
            self._current_expression = next_expression
            self._fade.stop()
            self._opacity.setOpacity(1.0)
        elif next_expression != self._current_expression:
            self._current_expression = next_expression
            self._fade_in()

    def resizeEvent(self, event) -> None:
        self._set_scaled_pixmap()
        super().resizeEvent(event)

    def _set_scaled_pixmap(self) -> None:
        if self._source_pixmap.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        scaled = self._source_pixmap.scaled(
            self.width(),
            self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def _fade_in(self) -> None:
        self._fade.stop()
        self._opacity.setOpacity(0.0)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()


def has_safe_portrait_manifest(asset_dir: Path | str, manifest_path: str) -> bool:
    try:
        load_portrait_manifest(asset_dir, manifest_path)
    except (OSError, PortraitManifestError, json.JSONDecodeError):
        return False
    return True


def resolve_portrait_image_path(asset_dir: Path | str, manifest_path: str, portrait_id: str) -> Path:
    manifest = load_portrait_manifest(asset_dir, manifest_path)
    expression = portrait_id if portrait_id in manifest.expressions else manifest.fallback_expression
    root = Path(asset_dir).resolve()
    resolved = (root / manifest.expressions[expression]).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PortraitManifestError("portrait image path must stay inside character asset directory") from exc
    return resolved


def load_portrait_manifest(asset_dir: Path | str, manifest_path: str) -> PortraitManifest:
    root = Path(asset_dir).resolve()
    manifest_rel = _safe_manifest_path(manifest_path)
    path = root / manifest_rel
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise PortraitManifestError("portrait manifest must be an object")
    expressions = payload.get("expressions")
    if not isinstance(expressions, dict):
        raise PortraitManifestError("portrait_manifest.expressions must be an object")
    clean_expressions: dict[str, str] = {}
    for expression in REQUIRED_PORTRAIT_EXPRESSIONS:
        if expression not in expressions:
            raise PortraitManifestError(f"portrait expression missing: {expression}")
    for expression, image_path in expressions.items():
        if not isinstance(expression, str) or not expression:
            raise PortraitManifestError("portrait expression ids must be non-empty strings")
        image_rel = _safe_portrait_image_path(image_path)
        _verify_portrait_image(root / image_rel)
        clean_expressions[expression] = image_rel.as_posix()
    fallback = payload.get("fallback_expression")
    if not isinstance(fallback, str) or fallback not in clean_expressions:
        raise PortraitManifestError("portrait fallback expression must reference an expression")
    anchor = payload.get("anchor", "bottom_center")
    if anchor not in {"bottom_center", "center"}:
        raise PortraitManifestError("portrait anchor invalid")
    default_scale = payload.get("default_scale", 1.0)
    if (
        isinstance(default_scale, bool)
        or not isinstance(default_scale, (int, float))
        or not 0.1 <= float(default_scale) <= 3.0
    ):
        raise PortraitManifestError("portrait default_scale must be between 0.1 and 3.0")
    return PortraitManifest(
        manifest_path=manifest_rel.as_posix(),
        fallback_expression=fallback,
        anchor=anchor,
        default_scale=float(default_scale),
        expressions=clean_expressions,
    )


def _safe_manifest_path(value: str) -> Path:
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        raise PortraitManifestError("portrait manifest path invalid")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1 or path.suffix != ".json":
        raise PortraitManifestError("portrait manifest path invalid")
    return path


def _safe_portrait_image_path(value: object) -> Path:
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        raise PortraitManifestError("portrait image path invalid")
    path = Path(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or len(path.parts) != 2
        or path.parts[0] != "portraits"
        or path.suffix.lower() != ".png"
    ):
        raise PortraitManifestError("portrait image path invalid")
    return path


def _verify_portrait_image(path: Path) -> None:
    try:
        with Image.open(path) as image:
            size = image.size
            mode = image.mode
            image.verify()
    except (OSError, UnidentifiedImageError) as exc:
        raise PortraitManifestError(f"portrait image invalid: {path.name}") from exc
    if mode != "RGBA":
        raise PortraitManifestError("portrait image mode must be RGBA")
    if size[0] > MAX_PORTRAIT_WIDTH or size[1] > MAX_PORTRAIT_HEIGHT:
        raise PortraitManifestError("portrait image too large")
