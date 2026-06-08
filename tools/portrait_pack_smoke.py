from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6.QtWidgets import QApplication

from guanghe_companion.app import CompanionWindow, configure_application_style
from guanghe_companion.character_registry import validate_character_pack_dir
from guanghe_companion.character_resources import load_character_resources_from_dir
from guanghe_companion.controller import CompanionController


DEFAULT_RUNTIME_MANIFEST = REPO_ROOT / "assets" / "companion" / "original_oc" / "portrait_manifest.json"


@dataclass(frozen=True, slots=True)
class PortraitPackSmokeReport:
    ok: bool
    character_id: str
    pack_dir: str
    renderer_backend: str
    spirit_surface_visible: bool
    sprite_fallback_visible: bool
    blink_sequence: tuple[str, ...]
    runtime_manifest_referenced: bool
    validation_errors: tuple[str, ...]
    errors: tuple[str, ...]
    report_path: str = ""
    screenshot_path: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "character_id": self.character_id,
            "pack_dir": self.pack_dir,
            "renderer_backend": self.renderer_backend,
            "spirit_surface_visible": self.spirit_surface_visible,
            "sprite_fallback_visible": self.sprite_fallback_visible,
            "blink_sequence": list(self.blink_sequence),
            "runtime_manifest_referenced": self.runtime_manifest_referenced,
            "validation_errors": list(self.validation_errors),
            "errors": list(self.errors),
            "report_path": self.report_path,
            "screenshot_path": self.screenshot_path,
        }


def run_portrait_pack_smoke(
    pack_dir: Path | str,
    *,
    report_path: Path | str | None = None,
    screenshot_path: Path | str | None = None,
    runtime_manifest_path: Path | str | None = DEFAULT_RUNTIME_MANIFEST,
) -> PortraitPackSmokeReport:
    root = Path(pack_dir)
    validation = validate_character_pack_dir(root, source="candidate")
    errors: list[str] = []
    renderer_backend = ""
    spirit_surface_visible = False
    sprite_fallback_visible = False
    blink_sequence: list[str] = []
    character_id = validation.character_id

    if validation.ok:
        app = QApplication.instance() or QApplication(sys.argv)
        configure_application_style(app)
        with TemporaryDirectory() as tmp:
            controller = CompanionController(
                save_path=Path(tmp) / "portrait-pack-smoke-save.json",
                auto_load=False,
                character_resources=load_character_resources_from_dir(root),
            )
            window = CompanionWindow(controller=controller, desktop_mode=True)
            try:
                window.show()
                app.processEvents()
                renderer_backend = window.presentation_renderer.backend
                spirit_surface_visible = window.spirit_surface.isVisibleTo(window)
                sprite_fallback_visible = window.sprite_label.isVisibleTo(window)
                if renderer_backend != "portrait":
                    errors.append(f"renderer backend is not portrait: {renderer_backend}")
                if not spirit_surface_visible:
                    errors.append("portrait spirit surface is not visible")
                pixmap = window.spirit_surface.pixmap()
                if pixmap is None or pixmap.isNull():
                    errors.append("portrait spirit surface did not render a frame")
                if sprite_fallback_visible:
                    errors.append("sprite fallback is visible during portrait smoke")
                if window.spirit_surface.trigger_blink():
                    blink_sequence.append(Path(window.spirit_surface.last_portrait_path).name)
                    for _ in range(3):
                        if not window.spirit_surface.advance_blink_for_test():
                            break
                        blink_sequence.append(Path(window.spirit_surface.last_portrait_path).name)
                else:
                    errors.append("portrait blink sequence did not start")
                if screenshot_path is not None:
                    target = Path(screenshot_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if window.grab().save(str(target)):
                        screenshot_value = str(target)
                    else:
                        screenshot_value = ""
                        errors.append("portrait smoke screenshot failed to save")
                else:
                    screenshot_value = ""
            finally:
                window.close()
                controller.close()
                app.processEvents()
    else:
        screenshot_value = ""

    runtime_referenced = (
        _runtime_manifest_references_pack(Path(runtime_manifest_path), root)
        if runtime_manifest_path is not None
        else False
    )
    all_errors = tuple(errors)
    report = PortraitPackSmokeReport(
        ok=validation.ok and not all_errors,
        character_id=character_id,
        pack_dir=str(root),
        renderer_backend=renderer_backend,
        spirit_surface_visible=spirit_surface_visible,
        sprite_fallback_visible=sprite_fallback_visible,
        blink_sequence=tuple(blink_sequence),
        runtime_manifest_referenced=runtime_referenced,
        validation_errors=tuple(validation.errors),
        errors=all_errors,
        report_path=str(report_path) if report_path is not None else "",
        screenshot_path=screenshot_value,
    )
    if report_path is not None:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
    return report


def _runtime_manifest_references_pack(runtime_manifest_path: Path, pack_dir: Path) -> bool:
    try:
        payload = json.loads(runtime_manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    runtime_root = runtime_manifest_path.parent.resolve()
    pack_root = pack_dir.resolve()
    for relative_path in _manifest_image_paths(payload):
        resolved = (runtime_root / relative_path).resolve()
        try:
            resolved.relative_to(pack_root)
        except ValueError:
            continue
        return True
    return False


def _manifest_image_paths(payload: dict[str, object]) -> tuple[str, ...]:
    expressions = payload.get("expressions")
    if not isinstance(expressions, dict):
        return ()
    paths: list[str] = []
    for value in expressions.values():
        if isinstance(value, str):
            paths.append(value)
        elif isinstance(value, dict):
            for key in ("open", "blink_half", "blink_closed"):
                item = value.get(key)
                if isinstance(item, str):
                    paths.append(item)
    return tuple(paths)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a portrait character pack smoke check.")
    parser.add_argument("pack_dir", help="Path to the character pack directory.")
    parser.add_argument("--report", default="", help="Optional JSON report output path.")
    parser.add_argument("--screenshot", default="", help="Optional screenshot output path.")
    parser.add_argument(
        "--runtime-manifest",
        default=str(DEFAULT_RUNTIME_MANIFEST),
        help="Runtime portrait manifest used only to report whether candidate images are referenced.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = run_portrait_pack_smoke(
        args.pack_dir,
        report_path=args.report or None,
        screenshot_path=args.screenshot or None,
        runtime_manifest_path=args.runtime_manifest or None,
    )
    print(
        "portrait pack smoke "
        f"{'ok' if report.ok else 'failed'}: "
        f"character_id={report.character_id}, backend={report.renderer_backend}, "
        f"blink_sequence={list(report.blink_sequence)}, errors={list(report.errors)}"
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
