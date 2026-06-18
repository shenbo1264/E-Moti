from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.app import CompanionWindow
from guanghe_companion.character_resources import load_character_resources_from_dir
from guanghe_companion.controller import CompanionController


SAMPLE_MODEL_DIR = REPO_ROOT / "tmp/live2d_research/CubismWebSamples/Samples/Resources/Haru"
SCREENSHOT_PATH = REPO_ROOT / "artifacts/simulation/live2d_character_pack_window.png"


def write_live2d_character_pack(root: Path) -> Path:
    pack_dir = root / "live2d_smoke_character"
    live2d_dir = pack_dir / "live2d"
    live2d_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE_MODEL_DIR, live2d_dir)
    Image.new("RGBA", (192, 208), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    (pack_dir / "character.json").write_text(
        json.dumps(
            {
                "character_id": "live2d_smoke_character",
                "name": "Live2D Smoke",
                "title": "Live2D desktop companion smoke",
                "description": "Temporary local Live2D smoke character pack.",
                "spritesheet": "spritesheet.png",
                "motion_manifest": "motion_manifest.json",
                "default_mode": "Calm",
                "modes": ["Calm"],
                "mode_descriptions": {"Calm": "Calm response"},
                "motion_labels": {"Default": "Idle"},
                "renderer": {
                    "backend": "live2d_web",
                    "model": "live2d/Haru.model3.json",
                    "expression_map": {
                        "calm": "F01",
                        "excited": "F02",
                        "surprised": "F03",
                        "sleepy": "F05",
                        "focused": "F06",
                    },
                    "motion_map": {
                        "Default": "Idle",
                        "Play": "TapBody",
                        "Raised": "TapBody",
                        "TouchHead": "TapBody",
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pack_dir / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 1,
                "sheet_rows": 1,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
            }
        ),
        encoding="utf-8",
    )
    (pack_dir / "shop_items.json").write_text("[]", encoding="utf-8")
    return pack_dir


def wait_for_loaded(window: CompanionWindow, timeout_seconds: float = 45.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_state: dict[str, object] = {}
    while time.monotonic() < deadline:
        view = getattr(window.live2d_surface, "_view", None)
        if view is None:
            QApplication.processEvents()
            time.sleep(0.1)
            continue
        loop = QEventLoop()
        holder: dict[str, object] = {}

        def receive(value: object) -> None:
            holder["value"] = value
            loop.quit()

        view.page().runJavaScript("window.live2dSpike ? JSON.stringify(window.live2dSpike) : ''", receive)
        QTimer.singleShot(500, loop.quit)
        loop.exec()
        raw = holder.get("value")
        if isinstance(raw, str) and raw:
            last_state = json.loads(raw)
            if last_state.get("error"):
                raise RuntimeError(str(last_state["error"]))
            if last_state.get("loaded") and int(last_state.get("frameSamples") or 0) >= 5:
                return last_state
        QApplication.processEvents()
        time.sleep(0.1)
    raise TimeoutError(f"Live2D character pack window did not load; last_state={last_state!r}")


def grab_nonblank(window: CompanionWindow, screenshot_path: Path) -> dict[str, object]:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = window.grab()
    if pixmap.isNull():
        raise RuntimeError("Live2D character pack window screenshot is null")
    pixmap.save(str(screenshot_path))
    image = Image.open(screenshot_path).convert("RGBA")
    colors = image.getcolors(maxcolors=1_000_000)
    unique_colors = len(colors or [])
    if unique_colors < 64:
        raise RuntimeError(f"Live2D character pack window appears blank: unique_colors={unique_colors}")
    return {"path": str(screenshot_path), "size": image.size, "unique_colors": unique_colors}


def main() -> int:
    if not (SAMPLE_MODEL_DIR / "Haru.model3.json").is_file():
        raise FileNotFoundError(f"missing local sample model: {SAMPLE_MODEL_DIR / 'Haru.model3.json'}")
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="e-moti-live2d-pack-") as tmp:
        pack_dir = write_live2d_character_pack(Path(tmp))
        resources = load_character_resources_from_dir(pack_dir)
        controller = CompanionController(
            character_resources=resources,
            save_path=Path(tmp) / "save.json",
            user_data_root=Path(tmp) / "user-data",
            auto_load=False,
        )
        window = CompanionWindow(controller=controller, desktop_mode=True, advance_ticks=False)
        window.show()
        app.processEvents()
        snapshot = controller.get_snapshot()
        snapshot["visual_actions"] = [
            {"type": "expression", "id": "excited", "ttl_ms": 3000, "priority": 70, "source": "llm"},
            {"type": "motion", "id": "Play", "ttl_ms": 1800, "priority": 60, "source": "llm"},
        ]
        window._apply_snapshot(snapshot)
        state = wait_for_loaded(window)
        if window.presentation_renderer.backend != "live2d_web":
            raise RuntimeError(f"expected live2d_web renderer, got {window.presentation_renderer.backend}")
        if not state.get("appliedVisualActions"):
            raise RuntimeError(f"expected mapped Live2D actions, got {state!r}")
        screenshot = grab_nonblank(window, SCREENSHOT_PATH)
        window.close()
        controller.close()
    print(json.dumps({"ok": True, "state": state, "screenshot": screenshot}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
