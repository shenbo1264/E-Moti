from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.character_pack import DEFAULT_CHARACTER_ID
from guanghe_companion.character_registry import validate_character_pack_dir

DEFAULT_APP_DIR = REPO_ROOT / "dist" / "E-Moti"
DEFAULT_INSTALLER = REPO_ROOT / "dist" / "installer" / "E-Moti_Setup_0.1.0.exe"
COMMON_REQUIRED_BUNDLED_ASSETS = ("LICENSE.md", "preview", "item_icons")
RENDERER_REQUIRED_BUNDLED_ASSETS = {
    "portrait": ("portrait_manifest.json", "portrait_assets_provenance.md", "portraits"),
    "sprite": ("provenance.md", "spritesheet.png", "motion_manifest.json"),
}
REQUIRED_VOICE_SERVICE_SCRIPTS = (
    "preflight_voice_services.py",
    "qwen3_tts_local_server.py",
    "start_qwen3_tts_server.ps1",
    "start_ikaros_gptsovits_server.ps1",
    "start_sensevoice_asr_server.ps1",
)


@dataclass(frozen=True, slots=True)
class WindowsBuildValidationReport:
    ok: bool
    app_dir: str
    app_exe: str
    character_dir: str
    character_id: str
    voice_services_dir: str
    installer_path: str
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "app_dir": self.app_dir,
            "app_exe": self.app_exe,
            "character_dir": self.character_dir,
            "character_id": self.character_id,
            "voice_services_dir": self.voice_services_dir,
            "installer_path": self.installer_path,
            "errors": list(self.errors),
        }


def validate_windows_build(
    *,
    app_dir: Path | str = DEFAULT_APP_DIR,
    installer_path: Path | str | None = DEFAULT_INSTALLER,
    character_id: str = DEFAULT_CHARACTER_ID,
) -> WindowsBuildValidationReport:
    app_root = Path(app_dir)
    installer = Path(installer_path) if installer_path is not None else None
    errors: list[str] = []

    exe_path = app_root / "E-Moti.exe"
    if not exe_path.is_file():
        errors.append(f"frozen app executable not found: {exe_path}")
    elif exe_path.stat().st_size <= 0:
        errors.append(f"frozen app executable is empty: {exe_path}")

    character_dir = _resolve_frozen_character_dir(app_root, character_id)
    pack_report = validate_character_pack_dir(character_dir, source="frozen")
    if not pack_report.ok:
        errors.extend(f"frozen character pack: {error}" for error in pack_report.errors)

    for required in _required_bundled_assets(character_dir):
        if not (character_dir / required).exists():
            errors.append(f"frozen character pack missing required bundled asset: {required}")

    voice_services_dir = _resolve_frozen_voice_services_dir(app_root)
    for required in REQUIRED_VOICE_SERVICE_SCRIPTS:
        if not (voice_services_dir / required).is_file():
            errors.append(f"frozen voice services missing required bundled script: {required}")

    if installer is not None:
        if not installer.is_file():
            errors.append(f"installer not found: {installer}")
        elif installer.stat().st_size <= 0:
            errors.append(f"installer is empty: {installer}")

    return WindowsBuildValidationReport(
        ok=not errors,
        app_dir=str(app_root),
        app_exe=str(exe_path),
        character_dir=str(character_dir),
        character_id=pack_report.character_id,
        voice_services_dir=str(voice_services_dir),
        installer_path=str(installer) if installer is not None else "",
        errors=tuple(errors),
    )


def _resolve_frozen_character_dir(app_dir: Path, character_id: str) -> Path:
    candidates = (
        app_dir / "_internal" / "assets" / "companion" / character_id,
        app_dir / "assets" / "companion" / character_id,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _resolve_frozen_voice_services_dir(app_dir: Path) -> Path:
    candidates = (
        app_dir / "_internal" / "voice_services",
        app_dir / "voice_services",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _required_bundled_assets(character_dir: Path) -> tuple[str, ...]:
    return COMMON_REQUIRED_BUNDLED_ASSETS + RENDERER_REQUIRED_BUNDLED_ASSETS.get(
        _renderer_backend(character_dir),
        (),
    )


def _renderer_backend(character_dir: Path) -> str:
    try:
        payload = json.loads((character_dir / "character.json").read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    renderer = payload.get("renderer")
    if isinstance(renderer, dict) and isinstance(renderer.get("backend"), str):
        return str(renderer["backend"])
    return "sprite"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate frozen Windows app and installer artifacts.")
    parser.add_argument("--app-dir", default=str(DEFAULT_APP_DIR))
    parser.add_argument("--installer", default=str(DEFAULT_INSTALLER))
    parser.add_argument("--skip-installer", action="store_true")
    parser.add_argument("--character-id", default=DEFAULT_CHARACTER_ID)
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = validate_windows_build(
        app_dir=args.app_dir,
        installer_path=None if args.skip_installer else args.installer,
        character_id=args.character_id,
    )
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
