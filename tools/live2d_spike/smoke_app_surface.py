from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.live2d_web import Live2DWebSurface
from guanghe_companion.presentation_renderer import PresentationFrame


DEFAULT_ASSET_DIR = REPO_ROOT / "tmp/live2d_research/CubismWebSamples/Samples/Resources/Haru"
DEFAULT_SCREENSHOT = REPO_ROOT / "artifacts/simulation/live2d_app_surface.png"


def wait_for_loaded(surface: Live2DWebSurface, timeout_seconds: float = 45.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_state: dict[str, object] = {}
    while time.monotonic() < deadline:
        view = getattr(surface, "_view", None)
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
    raise TimeoutError(f"Live2D app surface did not load; last_state={last_state!r}")


def grab_nonblank(surface: Live2DWebSurface, screenshot_path: Path) -> dict[str, object]:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = surface.grab()
    if pixmap.isNull():
        raise RuntimeError("Live2D app surface screenshot is null")
    pixmap.save(str(screenshot_path))
    image = Image.open(screenshot_path).convert("RGBA")
    colors = image.getcolors(maxcolors=1_000_000)
    unique_colors = len(colors or [])
    if unique_colors < 64:
        raise RuntimeError(f"Live2D app surface screenshot appears blank: unique_colors={unique_colors}")
    return {"path": str(screenshot_path), "size": image.size, "unique_colors": unique_colors}


def main() -> int:
    if not (DEFAULT_ASSET_DIR / "Haru.model3.json").is_file():
        raise FileNotFoundError(f"missing local sample model: {DEFAULT_ASSET_DIR / 'Haru.model3.json'}")
    app = QApplication.instance() or QApplication([])
    surface = Live2DWebSurface()
    surface.resize(720, 900)
    surface.show()
    frame = PresentationFrame(
        backend="live2d_web",
        motion="TapBody",
        model_path="Haru.model3.json",
        live2d_actions=(
            {"type": "expression", "id": "excited", "mapped": "F02", "source": "llm"},
            {"type": "motion", "id": "Play", "mapped": "TapBody", "source": "llm"},
        ),
    )
    surface.load_frame(frame, DEFAULT_ASSET_DIR)
    state = wait_for_loaded(surface)
    screenshot = grab_nonblank(surface, DEFAULT_SCREENSHOT)
    surface.close()
    surface.shutdown()
    print(json.dumps({"ok": True, "url": surface.last_url, "state": state, "screenshot": screenshot}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
