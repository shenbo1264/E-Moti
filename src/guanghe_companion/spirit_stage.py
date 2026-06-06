from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from PySide6.QtCore import QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

from .presentation_renderer import PresentationFrame

REQUIRED_PORTRAIT_EXPRESSIONS = ("neutral", "smile", "thinking", "surprised", "sad", "sleepy")
MAX_PORTRAIT_WIDTH = 4096
MAX_PORTRAIT_HEIGHT = 4096
BREATH_TICK_MS = 80
FRAME_TRANSITION_TICK_MS = 16


@dataclass(frozen=True, slots=True)
class PortraitExpressionFrames:
    open_path: str
    blink_half_path: str = ""
    blink_closed_path: str = ""

    @property
    def can_blink(self) -> bool:
        return bool(self.blink_half_path and self.blink_closed_path)


@dataclass(frozen=True, slots=True)
class PortraitAnimationConfig:
    breathing_enabled: bool = False
    breath_amplitude_px: int = 0
    breath_scale_delta: float = 0.0
    breath_cycle_ms: int = 4200
    blink_enabled: bool = False
    blink_min_interval_ms: int = 3000
    blink_max_interval_ms: int = 7000
    blink_half_ms: int = 45
    blink_closed_ms: int = 90


@dataclass(frozen=True, slots=True)
class PortraitManifest:
    manifest_path: str
    fallback_expression: str
    anchor: str
    default_scale: float
    expressions: dict[str, PortraitExpressionFrames]
    animation: PortraitAnimationConfig = PortraitAnimationConfig()


class PortraitManifestError(ValueError):
    pass


class SpiritStageSurface(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.loaded_frames: list[tuple[PresentationFrame, object]] = []
        self.last_portrait_path = ""
        self._source_pixmap = QPixmap()
        self._previous_source_pixmap = QPixmap()
        self._current_expression = ""
        self._current_asset_dir: Path | None = None
        self._current_manifest_path = ""
        self._current_frames: PortraitExpressionFrames | None = None
        self._current_animation = PortraitAnimationConfig()
        self._opacity = QGraphicsOpacityEffect(self)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setDuration(160)
        self._breath_phase = 0.0
        self._breath_timer = QTimer(self)
        self._breath_timer.timeout.connect(self._advance_breath)
        self._blink_schedule_timer = QTimer(self)
        self._blink_schedule_timer.setSingleShot(True)
        self._blink_schedule_timer.timeout.connect(self.trigger_blink)
        self._blink_step_timer = QTimer(self)
        self._blink_step_timer.setSingleShot(True)
        self._blink_step_timer.timeout.connect(self._advance_blink_frame)
        self._blink_sequence: list[str] = []
        self._frame_transition_timer = QTimer(self)
        self._frame_transition_timer.timeout.connect(self._advance_frame_transition)
        self._frame_transition_progress = 1.0
        self._frame_transition_step = 1.0
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(1.0)
        self.setObjectName("SpiritStageSurface")
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.setMinimumHeight(300)

    @property
    def breathing_enabled(self) -> bool:
        return self._current_animation.breathing_enabled

    @property
    def breath_amplitude_px(self) -> int:
        return self._current_animation.breath_amplitude_px

    @property
    def breath_scale_delta(self) -> float:
        return self._current_animation.breath_scale_delta

    @property
    def breath_cycle_ms(self) -> int:
        return self._current_animation.breath_cycle_ms

    @property
    def frame_transition_active(self) -> bool:
        return self._frame_transition_timer.isActive()

    @property
    def frame_transition_progress(self) -> float:
        return self._frame_transition_progress

    def load_frame(self, frame: PresentationFrame, asset_dir: object) -> None:
        self.loaded_frames.append((frame, asset_dir))
        try:
            manifest = load_portrait_manifest(asset_dir, frame.portrait_manifest)
            expression = frame.portrait_id if frame.portrait_id in manifest.expressions else manifest.fallback_expression
            frames = manifest.expressions[expression]
            portrait_path = resolve_portrait_frame_path(asset_dir, frame.portrait_manifest, expression, "open")
        except (OSError, PortraitManifestError, json.JSONDecodeError) as exc:
            self.last_portrait_path = ""
            self._source_pixmap = QPixmap()
            self._previous_source_pixmap = QPixmap()
            self._current_frames = None
            self._stop_animation_timers()
            self.clear()
            self.setText(str(exc))
            return

        if not self._load_portrait_pixmap(portrait_path):
            self.last_portrait_path = ""
            self._source_pixmap = QPixmap()
            self._previous_source_pixmap = QPixmap()
            self._current_frames = None
            self._stop_animation_timers()
            self.clear()
            self.setText(f"portrait image failed to load: {portrait_path.name}")
            return

        next_expression = expression
        self._current_asset_dir = Path(asset_dir)
        self._current_manifest_path = frame.portrait_manifest
        self._current_frames = frames
        self._current_animation = manifest.animation
        self.setText("")
        self._set_scaled_pixmap()
        if not self._current_expression:
            self._current_expression = next_expression
            self._fade.stop()
            self._opacity.setOpacity(1.0)
        elif next_expression != self._current_expression:
            self._current_expression = next_expression
            self._fade_in()
        self._configure_animation_timers()

    def trigger_blink(self) -> bool:
        if not self._current_frames or not self._current_frames.can_blink:
            return False
        if not self._current_asset_dir or not self._current_manifest_path:
            return False
        if not self._current_animation.blink_enabled:
            return False
        self._blink_schedule_timer.stop()
        self._blink_sequence = ["blink_half", "blink_closed", "blink_half", "open"]
        return self._advance_blink_frame()

    def advance_blink_for_test(self) -> bool:
        self._blink_step_timer.stop()
        return self._advance_blink_frame()

    def resizeEvent(self, event) -> None:
        self._set_scaled_pixmap()
        super().resizeEvent(event)

    def _set_scaled_pixmap(self) -> None:
        if self._source_pixmap.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        scale = 1.0
        y_offset = 0
        if self._current_animation.breathing_enabled:
            wave = math.sin(self._breath_phase)
            scale += self._current_animation.breath_scale_delta * max(0.0, wave)
            y_offset = int(round(-self._current_animation.breath_amplitude_px * max(0.0, wave)))
        canvas = QPixmap(self.width(), self.height())
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        if not self._previous_source_pixmap.isNull() and self._frame_transition_progress < 1.0:
            painter.setOpacity(1.0 - self._frame_transition_progress)
            self._draw_scaled_portrait(painter, self._previous_source_pixmap, scale, y_offset)
            painter.setOpacity(self._frame_transition_progress)
        self._draw_scaled_portrait(painter, self._source_pixmap, scale, y_offset)
        painter.end()
        self.setPixmap(canvas)

    def _fade_in(self) -> None:
        self._fade.stop()
        self._opacity.setOpacity(0.0)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def _load_portrait_pixmap(self, path: Path, *, transition_ms: int = 0) -> bool:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return False
        if transition_ms > 0 and not self._source_pixmap.isNull():
            self._previous_source_pixmap = self._source_pixmap
            self._frame_transition_progress = min(0.95, FRAME_TRANSITION_TICK_MS / max(transition_ms, 1))
            self._frame_transition_step = self._frame_transition_progress
            if self._frame_transition_progress < 1.0:
                self._frame_transition_timer.start(FRAME_TRANSITION_TICK_MS)
        else:
            self._previous_source_pixmap = QPixmap()
            self._frame_transition_timer.stop()
            self._frame_transition_progress = 1.0
            self._frame_transition_step = 1.0
        self.last_portrait_path = str(path)
        self._source_pixmap = pixmap
        return True

    def _draw_scaled_portrait(self, painter: QPainter, pixmap: QPixmap, scale: float, y_offset: int) -> None:
        scaled = pixmap.scaled(
            max(1, int(self.width() * scale)),
            max(1, int(self.height() * scale)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(
            int((self.width() - scaled.width()) / 2),
            self.height() - scaled.height() + y_offset,
            scaled,
        )

    def _configure_animation_timers(self) -> None:
        if self._current_animation.breathing_enabled:
            if not self._breath_timer.isActive():
                self._breath_timer.start(BREATH_TICK_MS)
        else:
            self._breath_timer.stop()
            self._breath_phase = 0.0
        if (
            self._current_animation.blink_enabled
            and self._current_frames is not None
            and self._current_frames.can_blink
        ):
            self._schedule_next_blink()
        else:
            self._blink_schedule_timer.stop()
            self._blink_step_timer.stop()

    def _stop_animation_timers(self) -> None:
        self._breath_timer.stop()
        self._blink_schedule_timer.stop()
        self._blink_step_timer.stop()
        self._frame_transition_timer.stop()
        self._blink_sequence = []

    def _advance_breath(self) -> None:
        cycle = max(self._current_animation.breath_cycle_ms, BREATH_TICK_MS)
        self._breath_phase = (self._breath_phase + (2 * math.pi * BREATH_TICK_MS / cycle)) % (2 * math.pi)
        self._set_scaled_pixmap()

    def _advance_blink_frame(self) -> bool:
        if not self._blink_sequence:
            self._schedule_next_blink()
            return False
        frame_kind = self._blink_sequence.pop(0)
        if not self._current_asset_dir or not self._current_manifest_path or not self._current_expression:
            return False
        try:
            path = resolve_portrait_frame_path(
                self._current_asset_dir,
                self._current_manifest_path,
                self._current_expression,
                frame_kind,
            )
        except (OSError, PortraitManifestError, json.JSONDecodeError):
            self._blink_sequence = []
            return False
        delay = self._blink_step_delay_for_next_kind(self._blink_sequence[0] if self._blink_sequence else "")
        if not self._load_portrait_pixmap(path, transition_ms=delay):
            self._blink_sequence = []
            return False
        self._set_scaled_pixmap()
        if self._blink_sequence:
            next_kind = self._blink_sequence[0]
            delay = self._blink_step_delay_for_next_kind(next_kind)
            self._blink_step_timer.start(max(1, delay))
        else:
            self._schedule_next_blink()
        return True

    def _advance_frame_transition(self) -> None:
        self._frame_transition_progress = min(1.0, self._frame_transition_progress + self._frame_transition_step)
        if self._frame_transition_progress >= 1.0:
            self._previous_source_pixmap = QPixmap()
            self._frame_transition_timer.stop()
        self._set_scaled_pixmap()

    def _blink_step_delay_for_next_kind(self, next_kind: str) -> int:
        return self._current_animation.blink_closed_ms if next_kind == "blink_half" else self._current_animation.blink_half_ms

    def _schedule_next_blink(self) -> None:
        if (
            not self._current_animation.blink_enabled
            or self._current_frames is None
            or not self._current_frames.can_blink
        ):
            return
        low = self._current_animation.blink_min_interval_ms
        high = max(low, self._current_animation.blink_max_interval_ms)
        self._blink_schedule_timer.start(random.randint(low, high))


def has_safe_portrait_manifest(asset_dir: Path | str, manifest_path: str) -> bool:
    try:
        load_portrait_manifest(asset_dir, manifest_path)
    except (OSError, PortraitManifestError, json.JSONDecodeError):
        return False
    return True


def resolve_portrait_image_path(asset_dir: Path | str, manifest_path: str, portrait_id: str) -> Path:
    return resolve_portrait_frame_path(asset_dir, manifest_path, portrait_id, "open")


def resolve_portrait_frame_path(asset_dir: Path | str, manifest_path: str, portrait_id: str, frame_kind: str) -> Path:
    manifest = load_portrait_manifest(asset_dir, manifest_path)
    expression = portrait_id if portrait_id in manifest.expressions else manifest.fallback_expression
    frames = manifest.expressions[expression]
    image_path = _frame_path_for_kind(frames, frame_kind)
    root = Path(asset_dir).resolve()
    resolved = (root / image_path).resolve()
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
    clean_expressions: dict[str, PortraitExpressionFrames] = {}
    for expression in REQUIRED_PORTRAIT_EXPRESSIONS:
        if expression not in expressions:
            raise PortraitManifestError(f"portrait expression missing: {expression}")
    for expression, image_path in expressions.items():
        if not isinstance(expression, str) or not expression:
            raise PortraitManifestError("portrait expression ids must be non-empty strings")
        frames = _portrait_expression_frames_from_payload(image_path)
        for image_rel in _all_frame_paths(frames):
            _verify_portrait_image(root / image_rel)
        clean_expressions[expression] = frames
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
        animation=_animation_config_from_payload(payload.get("animation")),
    )


def _portrait_expression_frames_from_payload(value: object) -> PortraitExpressionFrames:
    if isinstance(value, str):
        return PortraitExpressionFrames(open_path=_safe_portrait_image_path(value).as_posix())
    if not isinstance(value, dict):
        raise PortraitManifestError("portrait expression entry invalid")
    open_path = value.get("open")
    if not isinstance(open_path, str):
        raise PortraitManifestError("portrait expression open frame required")
    return PortraitExpressionFrames(
        open_path=_safe_portrait_image_path(open_path).as_posix(),
        blink_half_path=_optional_frame_path(value.get("blink_half")),
        blink_closed_path=_optional_frame_path(value.get("blink_closed")),
    )


def _optional_frame_path(value: object) -> str:
    if value is None or value == "":
        return ""
    return _safe_portrait_image_path(value).as_posix()


def _all_frame_paths(frames: PortraitExpressionFrames) -> tuple[Path, ...]:
    return tuple(
        Path(item)
        for item in (frames.open_path, frames.blink_half_path, frames.blink_closed_path)
        if item
    )


def _frame_path_for_kind(frames: PortraitExpressionFrames, frame_kind: str) -> str:
    if frame_kind == "blink_half" and frames.blink_half_path:
        return frames.blink_half_path
    if frame_kind == "blink_closed" and frames.blink_closed_path:
        return frames.blink_closed_path
    return frames.open_path


def _animation_config_from_payload(value: object) -> PortraitAnimationConfig:
    if not isinstance(value, dict):
        return PortraitAnimationConfig()
    breathing = value.get("breathing", {})
    blink = value.get("blink", {})
    if not isinstance(breathing, dict):
        breathing = {}
    if not isinstance(blink, dict):
        blink = {}
    return PortraitAnimationConfig(
        breathing_enabled=bool(breathing.get("enabled", False)),
        breath_amplitude_px=_int_range(breathing.get("amplitude_px", 0), 0, 8, 0),
        breath_scale_delta=_float_range(breathing.get("scale_delta", 0.0), 0.0, 0.03, 0.0),
        breath_cycle_ms=_int_range(breathing.get("cycle_ms", 4200), 2500, 7000, 4200),
        blink_enabled=bool(blink.get("enabled", False)),
        blink_min_interval_ms=_int_range(blink.get("min_interval_ms", 3000), 1000, 20000, 3000),
        blink_max_interval_ms=_int_range(blink.get("max_interval_ms", 7000), 1000, 30000, 7000),
        blink_half_ms=_int_range(blink.get("half_ms", 45), 20, 120, 45),
        blink_closed_ms=_int_range(blink.get("closed_ms", 90), 40, 240, 90),
    )


def _int_range(value: object, minimum: int, maximum: int, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return min(max(value, minimum), maximum)


def _float_range(value: object, minimum: float, maximum: float, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return min(max(float(value), minimum), maximum)


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
