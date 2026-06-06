from pathlib import Path

import pytest

from guanghe_companion.presentation_renderer import PresentationFrame


def test_build_live2d_page_url_carries_mapped_actions_from_frame(tmp_path):
    from guanghe_companion import live2d_web

    asset_dir = tmp_path / "character"
    model_path = asset_dir / "live2d" / "Xingxi.model3.json"
    model_path.parent.mkdir(parents=True)
    model_path.write_text("{}", encoding="utf-8")
    frame = PresentationFrame(
        backend="live2d_web",
        motion="TapBody",
        model_path="live2d/Xingxi.model3.json",
        live2d_actions=(
            {"type": "expression", "id": "excited", "mapped": "F02", "source": "llm"},
            {"type": "motion", "id": "Play", "mapped": "TapBody", "source": "llm"},
        ),
    )

    url = live2d_web.build_live2d_page_url("http://127.0.0.1:4173", frame, asset_dir)

    assert url.startswith("http://127.0.0.1:4173/tools/live2d_spike/index.html?")
    assert "model=/live2d/Xingxi.model3.json" not in url
    assert "model=/" in url
    assert "mappedActions=" in url
    assert "excited" in url
    assert "TapBody" in url


def test_build_live2d_page_url_rejects_model_outside_character_pack(tmp_path):
    from guanghe_companion import live2d_web

    frame = PresentationFrame(
        backend="live2d_web",
        motion="TapBody",
        model_path="../outside.model3.json",
    )

    with pytest.raises(ValueError, match="must stay inside character asset directory"):
        live2d_web.build_live2d_page_url("http://127.0.0.1:4173", frame, tmp_path / "character")


def test_resolve_live2d_static_path_blocks_repo_wide_file_serving(tmp_path):
    from guanghe_companion import live2d_web

    asset_dir = tmp_path / "character"
    asset_dir.mkdir()

    blocked = live2d_web.resolve_live2d_static_path("/README.md", asset_dir)
    allowed = live2d_web.resolve_live2d_static_path("/tools/live2d_spike/index.html", asset_dir)
    traversal = live2d_web.resolve_live2d_static_path("/character-assets/../outside.txt", asset_dir)

    assert blocked.name == "__missing_live2d_asset__"
    assert allowed.name == "index.html"
    assert traversal.name == "__missing_live2d_asset__"
