import json

from PIL import Image

def _write_portrait_pack(tmp_path):
    expressions = {
        "neutral": "portraits/neutral.png",
        "smile": "portraits/smile.png",
        "thinking": "portraits/thinking.png",
        "surprised": "portraits/surprised.png",
        "sad": "portraits/sad.png",
        "sleepy": "portraits/sleepy.png",
    }
    (tmp_path / "portraits").mkdir()
    for path in expressions.values():
        Image.new("RGBA", (128, 192), (40, 80, 120, 255)).save(tmp_path / path)
    (tmp_path / "portrait_manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "fallback_expression": "neutral",
                "anchor": "bottom_center",
                "default_scale": 1.0,
                "expressions": expressions,
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
