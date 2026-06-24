from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.expression_settings import ExpressionSettingsStore, expression_settings_readiness

DEFAULT_PRIVATE_CONFIG_DIR = REPO_ROOT / "private_submission_config"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "dist" / "E-Moti-course-submission"
DEFAULT_ZIP_PATH = REPO_ROOT / "dist" / "E-Moti-course-submission.zip"
ALLOWED_PRIVATE_CONFIG_FILENAMES = frozenset(
    {
        "expression_settings.json",
        "capability_settings.json",
        "long_term_memory.json",
        "dialogue_history.json",
        "companion_demo_save.json",
    }
)


@dataclass(frozen=True, slots=True)
class CourseSubmissionPackageReport:
    ok: bool
    app_dir: str
    output_dir: str
    zip_path: str
    include_voice_runtime: bool
    voice_runtime_included: bool
    private_config_dir: str
    private_config_files: tuple[str, ...]
    ai_expression_settings: dict[str, object]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "app_dir": self.app_dir,
            "output_dir": self.output_dir,
            "zip_path": self.zip_path,
            "include_voice_runtime": self.include_voice_runtime,
            "voice_runtime_included": self.voice_runtime_included,
            "private_config_dir": self.private_config_dir,
            "private_config_files": list(self.private_config_files),
            "ai_expression_settings": self.ai_expression_settings,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def build_course_submission_package(
    *,
    app_dir: Path | str | None = None,
    private_config_dir: Path | str = DEFAULT_PRIVATE_CONFIG_DIR,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    zip_path: Path | str = DEFAULT_ZIP_PATH,
    include_voice_runtime: bool = False,
) -> CourseSubmissionPackageReport:
    source_app_dir = Path(app_dir).resolve() if app_dir is not None else _default_app_dir().resolve()
    private_dir = Path(private_config_dir).resolve()
    target_dir = Path(output_dir).resolve()
    target_zip = Path(zip_path).resolve()
    warnings: list[str] = []
    errors: list[str] = []
    private_files: list[str] = []
    ai_expression_settings: dict[str, object] = {}

    if not source_app_dir.is_dir():
        errors.append(f"app dir not found: {source_app_dir}")
        return _report(
            ok=False,
            source_app_dir=source_app_dir,
            target_dir=target_dir,
            target_zip=target_zip,
            include_voice_runtime=include_voice_runtime,
            private_dir=private_dir,
            private_files=private_files,
            warnings=warnings,
            errors=errors,
        )
    if not (source_app_dir / "E-Moti.exe").is_file():
        errors.append(f"frozen executable not found: {source_app_dir / 'E-Moti.exe'}")

    if private_dir.exists():
        private_files, validation_errors = _validated_private_config_files(private_dir)
        errors.extend(validation_errors)
        ai_expression_settings = _read_private_expression_settings(private_dir, private_files)
    else:
        warnings.append("private config directory not found")

    if errors:
        return _report(
            ok=False,
            source_app_dir=source_app_dir,
            target_dir=target_dir,
            target_zip=target_zip,
            include_voice_runtime=include_voice_runtime,
            private_dir=private_dir,
            private_files=private_files,
            ai_expression_settings=ai_expression_settings,
            warnings=warnings,
            errors=errors,
        )

    _prepare_output_dir(target_dir)
    _copy_app_tree(
        source_app_dir=source_app_dir,
        target_dir=target_dir,
        include_voice_runtime=include_voice_runtime,
    )
    if private_files:
        _copy_private_config(private_dir=private_dir, target_dir=target_dir, filenames=private_files)
    _write_zip(target_dir=target_dir, zip_path=target_zip)
    voice_runtime_included = (target_dir / "voice_runtime").exists()

    return _report(
        ok=True,
        source_app_dir=source_app_dir,
        target_dir=target_dir,
        target_zip=target_zip,
        include_voice_runtime=include_voice_runtime,
        voice_runtime_included=voice_runtime_included,
        private_dir=private_dir,
        private_files=private_files,
        ai_expression_settings=ai_expression_settings,
        warnings=warnings,
        errors=errors,
    )


def _default_app_dir() -> Path:
    lite_dir = REPO_ROOT / "dist" / "E-Moti-submission-lite"
    if lite_dir.is_dir():
        return lite_dir
    return REPO_ROOT / "dist" / "E-Moti"


def _validated_private_config_files(private_dir: Path) -> tuple[list[str], list[str]]:
    filenames: list[str] = []
    errors: list[str] = []
    for path in sorted(private_dir.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(private_dir).as_posix()
        if "/" in relative:
            errors.append(f"private config file must be at top level: {relative}")
            continue
        if path.name not in ALLOWED_PRIVATE_CONFIG_FILENAMES:
            errors.append(f"private config filename is not allowed: {path.name}")
            continue
        filenames.append(path.name)
    return filenames, errors


def _read_private_expression_settings(private_dir: Path, private_files: Sequence[str]) -> dict[str, object]:
    if "expression_settings.json" not in private_files:
        return {}
    settings = ExpressionSettingsStore(private_dir / "expression_settings.json").load()
    return expression_settings_readiness(settings)


def _prepare_output_dir(target_dir: Path) -> None:
    parent = target_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = parent.resolve()
    resolved_target = target_dir.resolve()
    if resolved_target == resolved_parent or resolved_parent not in resolved_target.parents:
        raise ValueError(f"refusing to remove unsafe output dir: {target_dir}")
    if resolved_target.exists():
        shutil.rmtree(resolved_target)
    resolved_target.mkdir(parents=True, exist_ok=True)


def _copy_app_tree(*, source_app_dir: Path, target_dir: Path, include_voice_runtime: bool) -> None:
    ignored = shutil.ignore_patterns("voice_runtime") if not include_voice_runtime else None
    shutil.copytree(source_app_dir, target_dir, dirs_exist_ok=True, ignore=ignored)


def _copy_private_config(*, private_dir: Path, target_dir: Path, filenames: Sequence[str]) -> None:
    user_data_dir = target_dir / "user_data"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    for filename in filenames:
        shutil.copy2(private_dir / filename, user_data_dir / filename)


def _write_zip(*, target_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(target_dir.rglob("*")):
            if path.is_dir():
                continue
            archive.write(path, path.relative_to(target_dir).as_posix())


def _report(
    *,
    ok: bool,
    source_app_dir: Path,
    target_dir: Path,
    target_zip: Path,
    include_voice_runtime: bool,
    private_dir: Path,
    private_files: Sequence[str],
    warnings: Sequence[str],
    errors: Sequence[str],
    ai_expression_settings: dict[str, object] | None = None,
    voice_runtime_included: bool | None = None,
) -> CourseSubmissionPackageReport:
    return CourseSubmissionPackageReport(
        ok=ok,
        app_dir=str(source_app_dir),
        output_dir=str(target_dir),
        zip_path=str(target_zip),
        include_voice_runtime=include_voice_runtime,
        voice_runtime_included=bool(voice_runtime_included),
        private_config_dir=str(private_dir),
        private_config_files=tuple(private_files),
        ai_expression_settings=dict(ai_expression_settings or {}),
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the lightweight E-Moti course submission package.")
    parser.add_argument("--app-dir", default="")
    parser.add_argument("--private-config-dir", default=str(DEFAULT_PRIVATE_CONFIG_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--zip-path", default=str(DEFAULT_ZIP_PATH))
    parser.add_argument("--include-voice-runtime", action="store_true")
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = build_course_submission_package(
        app_dir=args.app_dir or None,
        private_config_dir=args.private_config_dir,
        output_dir=args.output_dir,
        zip_path=args.zip_path,
        include_voice_runtime=args.include_voice_runtime,
    )
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
