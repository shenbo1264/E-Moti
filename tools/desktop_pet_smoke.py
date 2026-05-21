from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6.QtWidgets import QApplication

from guanghe_companion.app import CompanionWindow
from guanghe_companion.controller import CompanionController

EXPECTED_MENU_LABELS = ("\u8fd4\u56de\u63a7\u5236\u9762\u677f", "\u9000\u51fa")


@dataclass(frozen=True, slots=True)
class DesktopPetSmokeReport:
    platform: str
    seconds: float
    iterations: int
    save_path: Path


def validate_desktop_pet_window(app: QApplication, window: CompanionWindow) -> list[str]:
    app.processEvents()
    errors: list[str] = []

    if not window.desktop_mode:
        errors.append("window is not in desktop mode")
    if not window.isVisible():
        errors.append("window is not visible")
    if window.spritesheet.isNull():
        errors.append("spritesheet did not load")

    pixmap = window.sprite_label.pixmap()
    if pixmap is None or pixmap.isNull():
        errors.append("current sprite frame did not render")

    if not window.desktop_feedback_label.isVisibleTo(window):
        errors.append("desktop feedback overlay is not visible")

    menu_labels = tuple(action.text() for action in window._build_desktop_context_menu().actions())
    if menu_labels != EXPECTED_MENU_LABELS:
        errors.append(f"desktop context menu labels are invalid: {menu_labels!r}")

    bounds = window._desktop_available_geometry()
    pos = window.pos()
    if (
        pos.x() < bounds.left()
        or pos.y() < bounds.top()
        or pos.x() + window.width() > bounds.right() + 1
        or pos.y() + window.height() > bounds.bottom() + 1
    ):
        errors.append("window is outside available screen bounds")

    return errors


def run_desktop_pet_smoke(seconds: float, interval: float) -> DesktopPetSmokeReport:
    app = QApplication.instance() or QApplication(sys.argv)
    with TemporaryDirectory() as tmp:
        save_path = Path(tmp) / "desktop-pet-smoke-save.json"
        controller = CompanionController(save_path=save_path, auto_load=False)
        window = CompanionWindow(controller=controller, desktop_mode=True)
        window.show()
        app.processEvents()

        started_at = time.monotonic()
        iterations = 0
        try:
            while time.monotonic() - started_at < seconds:
                errors = validate_desktop_pet_window(app, window)
                if errors:
                    raise RuntimeError("; ".join(errors))
                iterations += 1
                time.sleep(interval)
            return DesktopPetSmokeReport(
                platform=app.platformName(),
                seconds=round(time.monotonic() - started_at, 2),
                iterations=iterations,
                save_path=save_path,
            )
        finally:
            window.close()
            app.processEvents()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a desktop pet PySide smoke check.")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--interval", type=float, default=0.25)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = run_desktop_pet_smoke(seconds=max(0.1, args.seconds), interval=max(0.05, args.interval))
    print(
        "desktop pet smoke ok: "
        f"platform={report.platform}, seconds={report.seconds}, iterations={report.iterations}, "
        f"save_path={report.save_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
