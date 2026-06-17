from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from guanghe_companion.app import CompanionWindow  # noqa: E402
from guanghe_companion.character_registry import CharacterRegistry  # noqa: E402
from guanghe_companion.controller import CompanionController  # noqa: E402
from tools.desktop_pet_smoke import _pump_events_for, validate_desktop_pet_window  # noqa: E402


@dataclass(frozen=True, slots=True)
class CharacterLibraryQAReport:
    ok: bool
    character_id: str
    default_character_id: str
    selected_character_id: str
    after_switch_character_id: str
    candidate_source: str
    candidate_pack_path: str
    candidate_backend: str
    desktop_backend: str
    available_character_ids: tuple[str, ...]
    character_library_screenshot: str
    desktop_pet_screenshot: str
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "character_id": self.character_id,
            "default_character_id": self.default_character_id,
            "selected_character_id": self.selected_character_id,
            "after_switch_character_id": self.after_switch_character_id,
            "candidate_source": self.candidate_source,
            "candidate_pack_path": self.candidate_pack_path,
            "candidate_backend": self.candidate_backend,
            "desktop_backend": self.desktop_backend,
            "available_character_ids": list(self.available_character_ids),
            "character_library_screenshot": self.character_library_screenshot,
            "desktop_pet_screenshot": self.desktop_pet_screenshot,
            "errors": list(self.errors),
        }


def run_character_library_qa(
    *,
    character_id: str,
    report_path: Path | str,
    screenshot_dir: Path | str,
    character_root: Path | str | None = None,
    pet_seconds: float = 0.5,
) -> CharacterLibraryQAReport:
    app = QApplication.instance() or QApplication(sys.argv)
    screenshots = Path(screenshot_dir)
    screenshots.mkdir(parents=True, exist_ok=True)
    report_target = Path(report_path)
    report_target.parent.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    library_screenshot = screenshots / f"{character_id}-character-library.png"
    desktop_screenshot = screenshots / f"{character_id}-desktop-pet.png"

    with TemporaryDirectory() as tmp:
        user_data_root = Path(tmp) / "user-data"
        controller = CompanionController(user_data_root=user_data_root, auto_load=False)
        window = CompanionWindow(controller=controller)
        if character_root is not None:
            empty_builtin_root = Path(tmp) / "empty-builtin-character-packs"
            empty_builtin_root.mkdir(parents=True, exist_ok=True)
            window.character_registry = CharacterRegistry(
                builtin_root=empty_builtin_root,
                user_root=Path(character_root),
            )
            window._refresh_character_library()
        window.resize(1080, 760)
        window.show()
        app.processEvents()
        default_character_id = window.controller.state.character_id

        try:
            window._select_navigation_button(3)
            _select_character(window, character_id, errors)
            selected_character_id = window._selected_character_id()
            candidate_summary = window._character_pack_summaries.get(character_id)
            candidate_backend = _renderer_backend(candidate_summary.path if candidate_summary else None)
            candidate_source = candidate_summary.source if candidate_summary else ""
            candidate_pack_path = str(candidate_summary.path) if candidate_summary else ""
            if character_root is not None:
                if candidate_source != "user":
                    errors.append(f"character root QA did not select user pack source: {candidate_source}")
                elif not _path_stays_inside(candidate_summary.path, Path(character_root)):
                    errors.append(f"character root QA selected pack outside character root: {candidate_summary.path}")
            _validate_character_detail(window, character_id, errors)
            _save_widget_screenshot(window, library_screenshot, errors)

            if selected_character_id == character_id:
                window.character_switch_button.click()
                app.processEvents()
            after_switch_character_id = window.controller.state.character_id
            if after_switch_character_id != character_id:
                errors.append(f"character switch did not select {character_id}: {after_switch_character_id}")

            window._enter_desktop_mode()
            app.processEvents()
            pet_window = window.desktop_pet_window
            desktop_backend = ""
            if pet_window is None:
                errors.append("desktop pet window was not created")
            else:
                desktop_backend = pet_window.presentation_renderer.backend
                _pump_events_for(app, max(0.05, pet_seconds), step=0.025)
                errors.extend(validate_desktop_pet_window(app, pet_window))
                _save_widget_screenshot(pet_window, desktop_screenshot, errors)

            report = CharacterLibraryQAReport(
                ok=not errors,
                character_id=character_id,
                default_character_id=default_character_id,
                selected_character_id=selected_character_id,
                after_switch_character_id=after_switch_character_id,
                candidate_source=candidate_source,
                candidate_pack_path=candidate_pack_path,
                candidate_backend=candidate_backend,
                desktop_backend=desktop_backend,
                available_character_ids=tuple(window._character_pack_summaries),
                character_library_screenshot=str(library_screenshot),
                desktop_pet_screenshot=str(desktop_screenshot),
                errors=tuple(errors),
            )
        finally:
            if window.desktop_pet_window is not None:
                window.desktop_pet_window.close()
            window.close()
            app.processEvents()

    report_target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _select_character(window: CompanionWindow, character_id: str, errors: list[str]) -> None:
    if character_id not in window._character_pack_summaries:
        errors.append(f"character pack not listed: {character_id}")
        return
    window._select_character_pack(character_id)
    if window._selected_character_id() != character_id:
        errors.append(f"character pack selection failed: {character_id}")


def _validate_character_detail(window: CompanionWindow, character_id: str, errors: list[str]) -> None:
    detail = window.character_detail_label.text()
    if character_id not in window._character_pack_summaries:
        return
    required_fragments = (
        "Distribution: shareable_after_review",
        "Provenance: provenance.md",
        "License: LICENSE.md",
    )
    for fragment in required_fragments:
        if fragment not in detail:
            errors.append(f"character detail missing {fragment!r}")
    if window.character_preview_label.pixmap() is None or window.character_preview_label.pixmap().isNull():
        errors.append("character preview pixmap did not load")
    if not window.character_switch_button.isEnabled() and window.controller.state.character_id != character_id:
        errors.append("character switch button is disabled before candidate switch")


def _renderer_backend(pack_dir: Path | None) -> str:
    if pack_dir is None:
        return ""
    try:
        payload = json.loads((pack_dir / "character.json").read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    renderer = payload.get("renderer") if isinstance(payload, dict) else None
    if isinstance(renderer, dict) and isinstance(renderer.get("backend"), str):
        return str(renderer["backend"])
    return "sprite"


def _path_stays_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _save_widget_screenshot(widget, path: Path, errors: list[str]) -> None:
    pixmap = widget.grab()
    if pixmap.isNull():
        errors.append(f"screenshot capture returned empty pixmap: {path}")
        return
    if not pixmap.save(str(path)):
        errors.append(f"screenshot write failed: {path}")
        return
    if not path.is_file() or path.stat().st_size <= 0:
        errors.append(f"screenshot is missing or empty: {path}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run character-library QA for a bundled character pack.")
    parser.add_argument("--character-id", default="xingxi_pixel_pet")
    parser.add_argument(
        "--character-root",
        default=None,
        help="Optional local character_packs root to use as the user-pack source for QA.",
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--screenshot-dir", required=True)
    parser.add_argument("--pet-seconds", type=float, default=0.5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    started = time.monotonic()
    report = run_character_library_qa(
        character_id=args.character_id,
        report_path=args.report,
        screenshot_dir=args.screenshot_dir,
        character_root=args.character_root,
        pet_seconds=max(0.05, args.pet_seconds),
    )
    elapsed = round(time.monotonic() - started, 2)
    if report.ok:
        print(f"character library QA ok: character_id={report.character_id}, seconds={elapsed}")
        return 0
    print(
        "character library QA failed: "
        f"character_id={report.character_id}, errors={'; '.join(report.errors)}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
