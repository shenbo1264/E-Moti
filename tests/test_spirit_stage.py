import json

from PIL import Image

def _write_portrait_pack(tmp_path, *, structured=False, animation=None, motion_frames=None):
    expressions = {
        "neutral": "portraits/neutral.png",
        "smile": "portraits/smile.png",
        "thinking": "portraits/thinking.png",
        "surprised": "portraits/surprised.png",
        "sad": "portraits/sad.png",
        "sleepy": "portraits/sleepy.png",
    }
    (tmp_path / "portraits").mkdir()
    if structured:
        expressions["neutral"] = {
            "open": "portraits/neutral_open.png",
            "blink_half": "portraits/neutral_half.png",
            "blink_closed": "portraits/neutral_closed.png",
        }
    for value in expressions.values():
        paths = value.values() if isinstance(value, dict) else (value,)
        for path in paths:
            Image.new("RGBA", (128, 192), (40, 80, 120, 255)).save(tmp_path / path)
    if motion_frames:
        (tmp_path / "motion_frames").mkdir()
        for index, path in enumerate(motion_frames, start=1):
            Image.new("RGBA", (128, 192), (40 + index, 80, 120, 255)).save(tmp_path / path)
    (tmp_path / "portrait_manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "fallback_expression": "neutral",
                "anchor": "bottom_center",
                "default_scale": 1.0,
                "expressions": expressions,
                "motion_frames": list(motion_frames or ()),
                "animation": animation or {},
            }
        ),
        encoding="utf-8",
    )


def test_spirit_stage_loads_first_portrait_frame_fully_visible(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.presentation_renderer import PresentationFrame
    from guanghe_companion.spirit_stage import SpiritStageSurface, has_safe_portrait_manifest

    _write_portrait_pack(tmp_path)
    app = QApplication.instance() or QApplication([])
    surface = SpiritStageSurface()
    surface.resize(288, 312)

    surface.load_frame(
        PresentationFrame(
            backend="portrait",
            motion="Default",
            portrait_manifest="portrait_manifest.json",
            portrait_id="neutral",
        ),
        tmp_path,
    )

    assert has_safe_portrait_manifest(tmp_path, "portrait_manifest.json")
    assert surface.pixmap() is not None
    assert not surface.pixmap().isNull()
    assert surface.graphicsEffect().opacity() == 1.0
    assert surface.last_portrait_path.endswith("neutral.png")
    surface.close()
    app.processEvents()


def test_portrait_manifest_reads_structured_blink_frames_and_animation(tmp_path):
    from guanghe_companion.spirit_stage import load_portrait_manifest

    _write_portrait_pack(
        tmp_path,
        structured=True,
        animation={
            "breathing": {"enabled": True, "amplitude_px": 3, "scale_delta": 0.012, "cycle_ms": 4200},
            "blink": {"enabled": True, "min_interval_ms": 3000, "max_interval_ms": 7000, "half_ms": 45, "closed_ms": 90},
        },
    )

    manifest = load_portrait_manifest(tmp_path, "portrait_manifest.json")

    assert manifest.expressions["neutral"].open_path == "portraits/neutral_open.png"
    assert manifest.expressions["neutral"].blink_half_path == "portraits/neutral_half.png"
    assert manifest.expressions["neutral"].blink_closed_path == "portraits/neutral_closed.png"
    assert manifest.animation.breathing_enabled is True
    assert manifest.animation.breath_amplitude_px == 3
    assert manifest.animation.blink_enabled is True
    assert manifest.animation.blink_half_ms == 45


def test_portrait_manifest_reads_idle_motion_frames_and_animation(tmp_path):
    from guanghe_companion.spirit_stage import load_portrait_manifest

    _write_portrait_pack(
        tmp_path,
        motion_frames=("motion_frames/idle_0001.png", "motion_frames/idle_0002.png"),
        animation={"idle": {"enabled": True, "fps": 6}},
    )

    manifest = load_portrait_manifest(tmp_path, "portrait_manifest.json")

    assert manifest.motion_frames == ("motion_frames/idle_0001.png", "motion_frames/idle_0002.png")
    assert manifest.animation.idle_enabled is True
    assert manifest.animation.idle_fps == 6


def test_portrait_manifest_rejects_unsafe_idle_motion_frame_path(tmp_path):
    from guanghe_companion.spirit_stage import PortraitManifestError, load_portrait_manifest

    _write_portrait_pack(tmp_path)
    payload = json.loads((tmp_path / "portrait_manifest.json").read_text(encoding="utf-8"))
    payload["motion_frames"] = ["../idle_0001.png"]
    (tmp_path / "portrait_manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    try:
        load_portrait_manifest(tmp_path, "portrait_manifest.json")
    except PortraitManifestError as exc:
        assert "portrait motion frame path invalid" in str(exc)
    else:
        raise AssertionError("unsafe motion frame path should be rejected")


def test_spirit_stage_trigger_blink_uses_half_closed_then_open_frames(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.presentation_renderer import PresentationFrame
    from guanghe_companion.spirit_stage import SpiritStageSurface

    _write_portrait_pack(
        tmp_path,
        structured=True,
        animation={"blink": {"enabled": True, "min_interval_ms": 3000, "max_interval_ms": 7000}},
    )
    app = QApplication.instance() or QApplication([])
    surface = SpiritStageSurface()
    surface.resize(288, 312)
    surface.load_frame(
        PresentationFrame(
            backend="portrait",
            motion="Default",
            portrait_manifest="portrait_manifest.json",
            portrait_id="neutral",
        ),
        tmp_path,
    )

    assert surface.last_portrait_path.endswith("neutral_open.png")

    surface.trigger_blink()
    assert surface.last_portrait_path.endswith("neutral_half.png")

    surface.advance_blink_for_test()
    assert surface.last_portrait_path.endswith("neutral_closed.png")

    surface.advance_blink_for_test()
    assert surface.last_portrait_path.endswith("neutral_half.png")

    surface.advance_blink_for_test()
    assert surface.last_portrait_path.endswith("neutral_open.png")
    surface.close()
    app.processEvents()


def test_spirit_stage_advance_idle_motion_uses_motion_frame_sequence(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.presentation_renderer import PresentationFrame
    from guanghe_companion.spirit_stage import SpiritStageSurface

    _write_portrait_pack(
        tmp_path,
        motion_frames=("motion_frames/idle_0001.png", "motion_frames/idle_0002.png"),
        animation={"idle": {"enabled": True, "fps": 6}},
    )
    app = QApplication.instance() or QApplication([])
    surface = SpiritStageSurface()
    surface.resize(288, 312)
    surface.load_frame(
        PresentationFrame(
            backend="portrait",
            motion="Default",
            portrait_manifest="portrait_manifest.json",
            portrait_id="neutral",
        ),
        tmp_path,
    )

    assert surface.last_portrait_path.endswith("neutral.png")

    assert surface.advance_idle_motion_for_test() is True
    assert surface.last_portrait_path.endswith("idle_0001.png")

    assert surface.advance_idle_motion_for_test() is True
    assert surface.last_portrait_path.endswith("idle_0002.png")
    surface.close()
    app.processEvents()


def test_spirit_stage_blink_frames_start_smooth_transition(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.presentation_renderer import PresentationFrame
    from guanghe_companion.spirit_stage import SpiritStageSurface

    _write_portrait_pack(
        tmp_path,
        structured=True,
        animation={"blink": {"enabled": True, "half_ms": 60, "closed_ms": 90}},
    )
    app = QApplication.instance() or QApplication([])
    surface = SpiritStageSurface()
    surface.resize(288, 312)
    surface.load_frame(
        PresentationFrame(
            backend="portrait",
            motion="Default",
            portrait_manifest="portrait_manifest.json",
            portrait_id="neutral",
        ),
        tmp_path,
    )

    assert surface.trigger_blink() is True

    assert surface.frame_transition_active is True
    assert 0.0 < surface.frame_transition_progress < 1.0
    surface.close()
    app.processEvents()


def test_spirit_stage_enables_breathing_from_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.presentation_renderer import PresentationFrame
    from guanghe_companion.spirit_stage import SpiritStageSurface

    _write_portrait_pack(
        tmp_path,
        animation={"breathing": {"enabled": True, "amplitude_px": 4, "scale_delta": 0.01, "cycle_ms": 3600}},
    )
    app = QApplication.instance() or QApplication([])
    surface = SpiritStageSurface()
    surface.resize(288, 312)
    surface.load_frame(
        PresentationFrame(
            backend="portrait",
            motion="Default",
            portrait_manifest="portrait_manifest.json",
            portrait_id="neutral",
        ),
        tmp_path,
    )

    assert surface.breathing_enabled is True
    assert surface.breath_amplitude_px == 4
    assert surface.breath_scale_delta == 0.01
    assert surface.breath_cycle_ms == 3600
    surface.close()
    app.processEvents()


def test_original_oc_does_not_enable_blink_without_structured_blink_frames():
    from pathlib import Path

    from guanghe_companion.spirit_stage import load_portrait_manifest

    asset_dir = Path(__file__).resolve().parents[1] / "assets" / "companion" / "original_oc"
    manifest = load_portrait_manifest(asset_dir, "portrait_manifest.json")

    assert manifest.animation.blink_enabled is False
    assert all(not frames.can_blink for frames in manifest.expressions.values())
