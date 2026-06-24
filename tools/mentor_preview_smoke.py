from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP_DIR = REPO_ROOT / "dist" / "E-Moti"
DEFAULT_WORK_ROOT = REPO_ROOT / "artifacts" / "final-package-qa" / "mentor-preview-smoke"

REQUIRED_PACKAGED_FILES = (
    "E-Moti.exe",
    "_internal/voice_services/preflight_voice_services.py",
    "_internal/voice_services/qwen3_tts_local_server.py",
    "_internal/voice_services/start_qwen3_tts_server.ps1",
    "_internal/voice_services/start_ikaros_gptsovits_server.ps1",
    "_internal/voice_services/start_sensevoice_asr_server.ps1",
    "_internal/assets/companion/xingxi_pixel_pet/character.json",
    "_internal/assets/companion/ikaros_pixel_pet/character.json",
    "_internal/assets/companion/nairong_pixel_pet/character.json",
)

LaunchFunction = Callable[[Path, Sequence[str], dict[str, str], float], dict[str, object]]


@dataclass(frozen=True, slots=True)
class MentorPreviewSmokeReport:
    ok: bool
    source_app_dir: str
    working_app_dir: str
    user_data_dir: str
    seconds: float
    voice_runtime_present: bool
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    launches: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source_app_dir": self.source_app_dir,
            "working_app_dir": self.working_app_dir,
            "user_data_dir": self.user_data_dir,
            "seconds": self.seconds,
            "voice_runtime_present": self.voice_runtime_present,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "launches": list(self.launches),
        }


def run_mentor_preview_smoke(
    *,
    app_dir: Path | str = DEFAULT_APP_DIR,
    work_root: Path | str = DEFAULT_WORK_ROOT,
    seconds: float = 5.0,
    launcher: LaunchFunction | None = None,
) -> MentorPreviewSmokeReport:
    source_app_dir = Path(app_dir).resolve()
    root = Path(work_root).resolve()
    working_app_dir = root / "E-Moti-portable"
    user_data_dir = root / "user-data"
    errors: list[str] = []
    warnings: list[str] = []
    launches: list[dict[str, object]] = []
    launch = _launch_frozen_app if launcher is None else launcher

    if not source_app_dir.is_dir():
        errors.append(f"source app dir not found: {source_app_dir}")
        return _report(
            ok=False,
            source_app_dir=source_app_dir,
            working_app_dir=working_app_dir,
            user_data_dir=user_data_dir,
            seconds=seconds,
            voice_runtime_present=False,
            warnings=warnings,
            errors=errors,
            launches=launches,
        )

    _prepare_isolated_copy(source_app_dir=source_app_dir, working_app_dir=working_app_dir, user_data_dir=user_data_dir)
    voice_runtime_present = (working_app_dir / "voice_runtime").is_dir()
    if not voice_runtime_present:
        warnings.append("portable voice_runtime not found")

    for relative_path in REQUIRED_PACKAGED_FILES:
        if not (working_app_dir / relative_path).is_file():
            errors.append(f"missing packaged file: {relative_path}")

    if not errors:
        env = os.environ.copy()
        env["E_MOTI_USER_DATA_DIR"] = str(user_data_dir)
        exe_path = working_app_dir / "E-Moti.exe"
        for mode, args in (
            ("control_panel", ()),
            ("pet_mode", ("--pet-mode",)),
        ):
            launch_report = dict(launch(exe_path, args, env, max(0.1, seconds)))
            launch_report["mode"] = mode
            launches.append(launch_report)
            if not launch_report.get("ok"):
                errors.append(f"{mode} frozen launch failed: {launch_report.get('error') or launch_report}")

    return _report(
        ok=not errors,
        source_app_dir=source_app_dir,
        working_app_dir=working_app_dir,
        user_data_dir=user_data_dir,
        seconds=seconds,
        voice_runtime_present=voice_runtime_present,
        warnings=warnings,
        errors=errors,
        launches=launches,
    )


def _prepare_isolated_copy(*, source_app_dir: Path, working_app_dir: Path, user_data_dir: Path) -> None:
    work_root = working_app_dir.parent
    work_root.mkdir(parents=True, exist_ok=True)
    _remove_child_dir(working_app_dir, work_root=work_root)
    _remove_child_dir(user_data_dir, work_root=work_root)
    shutil.copytree(source_app_dir, working_app_dir)
    user_data_dir.mkdir(parents=True, exist_ok=True)


def _remove_child_dir(path: Path, *, work_root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = work_root.resolve()
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise ValueError(f"refusing to remove path outside work root: {path}")
    if resolved_path.exists():
        shutil.rmtree(resolved_path)


def _launch_frozen_app(exe_path: Path, args: Sequence[str], env: dict[str, str], seconds: float) -> dict[str, object]:
    command = [str(exe_path), *args]
    started_at = time.monotonic()
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            command,
            cwd=str(exe_path.parent),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except OSError as exc:
        return {
            "ok": False,
            "args": list(args),
            "seconds": 0.0,
            "exit_code": None,
            "error": str(exc),
        }

    time.sleep(max(0.1, seconds))
    exit_code = process.poll()
    elapsed = round(time.monotonic() - started_at, 2)
    if exit_code is not None:
        return {
            "ok": False,
            "args": list(args),
            "seconds": elapsed,
            "exit_code": exit_code,
            "error": f"process exited early with code {exit_code}",
        }

    _stop_process(process)
    return {
        "ok": True,
        "args": list(args),
        "seconds": elapsed,
        "exit_code": None,
        "error": "",
    }


def _stop_process(process: subprocess.Popen[object]) -> None:
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _report(
    *,
    ok: bool,
    source_app_dir: Path,
    working_app_dir: Path,
    user_data_dir: Path,
    seconds: float,
    voice_runtime_present: bool,
    warnings: Sequence[str],
    errors: Sequence[str],
    launches: Sequence[dict[str, object]],
) -> MentorPreviewSmokeReport:
    return MentorPreviewSmokeReport(
        ok=ok,
        source_app_dir=str(source_app_dir),
        working_app_dir=str(working_app_dir),
        user_data_dir=str(user_data_dir),
        seconds=seconds,
        voice_runtime_present=voice_runtime_present,
        warnings=tuple(warnings),
        errors=tuple(errors),
        launches=tuple(launches),
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate a mentor launching the frozen E-Moti preview package.")
    parser.add_argument("--app-dir", default=str(DEFAULT_APP_DIR))
    parser.add_argument("--work-root", default=str(DEFAULT_WORK_ROOT))
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = run_mentor_preview_smoke(
        app_dir=args.app_dir,
        work_root=args.work_root,
        seconds=args.seconds,
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
