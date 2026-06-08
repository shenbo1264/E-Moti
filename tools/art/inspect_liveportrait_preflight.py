from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError


ALLOWED_DRIVING_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".pkl"}
REQUIRED_LIVEPORTRAIT_FILES = ("inference.py", "app.py", "requirements.txt")
REQUIRED_HUMAN_WEIGHT_PATHS = (
    "pretrained_weights/liveportrait/base_models/appearance_feature_extractor.pth",
    "pretrained_weights/liveportrait/base_models/motion_extractor.pth",
    "pretrained_weights/liveportrait/base_models/spade_generator.pth",
    "pretrained_weights/liveportrait/base_models/warping_module.pth",
    "pretrained_weights/liveportrait/landmark.onnx",
    "pretrained_weights/liveportrait/retargeting_models/stitching_retargeting_module.pth",
    "pretrained_weights/insightface/models/buffalo_l/2d106det.onnx",
    "pretrained_weights/insightface/models/buffalo_l/det_10g.onnx",
)


@dataclass(frozen=True, slots=True)
class LivePortraitPreflightReport:
    ok: bool
    source_pack_dir: str
    liveportrait_root: str
    source_image_path: str
    reference_size: tuple[int, int] | tuple[()]
    driving_path: str
    driving_status: str
    ffmpeg_path: str
    next_action: str
    suggested_command: str
    errors: tuple[str, ...]
    missing_weight_paths: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source_pack_dir": self.source_pack_dir,
            "liveportrait_root": self.liveportrait_root,
            "source_image_path": self.source_image_path,
            "reference_size": list(self.reference_size),
            "driving_path": self.driving_path,
            "driving_status": self.driving_status,
            "ffmpeg_path": self.ffmpeg_path,
            "next_action": self.next_action,
            "suggested_command": self.suggested_command,
            "errors": list(self.errors),
            "missing_weight_paths": list(self.missing_weight_paths),
            "warnings": list(self.warnings),
        }


def inspect_liveportrait_preflight(
    source_pack_dir: Path | str,
    *,
    liveportrait_root: Path | str,
    driving_path: Path | str = "",
    ffmpeg_path: Path | str = "",
    report_path: Path | str | None = None,
    markdown_path: Path | str | None = None,
) -> LivePortraitPreflightReport:
    source_root = Path(source_pack_dir)
    liveportrait = Path(liveportrait_root)
    errors: list[str] = []
    warnings: list[str] = []

    source_image, reference_size = _source_pack_reference(source_root, errors)
    _validate_liveportrait_root(liveportrait, errors)
    missing_weight_paths = _missing_human_weight_paths(liveportrait) if liveportrait.exists() else tuple(REQUIRED_HUMAN_WEIGHT_PATHS)
    if liveportrait.exists() and missing_weight_paths:
        errors.append("required pretrained weights are missing")
    driving, driving_status = _validate_driving_path(driving_path, errors)
    ffmpeg = _resolve_ffmpeg(ffmpeg_path, errors)
    next_action = _next_action(
        liveportrait=liveportrait,
        errors=errors,
        missing_weight_paths=missing_weight_paths,
        driving=driving,
        ffmpeg=ffmpeg,
    )
    suggested_command = _suggested_command(liveportrait, source_image, driving) if next_action == "run_liveportrait" else ""

    report = LivePortraitPreflightReport(
        ok=not errors,
        source_pack_dir=str(source_root),
        liveportrait_root=str(liveportrait),
        source_image_path=str(source_image) if source_image is not None else "",
        reference_size=reference_size,
        driving_path=str(driving) if driving is not None else "",
        driving_status=driving_status,
        ffmpeg_path=ffmpeg,
        next_action=next_action,
        suggested_command=suggested_command,
        errors=tuple(errors),
        missing_weight_paths=missing_weight_paths,
        warnings=tuple(warnings),
    )
    _write_report(report, report_path)
    _write_markdown(report, markdown_path)
    return report


def render_liveportrait_preflight_markdown(report: LivePortraitPreflightReport) -> str:
    lines = [
        "# LivePortrait Preflight",
        "",
        f"- OK: `{str(report.ok).lower()}`",
        f"- Source pack: `{report.source_pack_dir}`",
        f"- LivePortrait root: `{report.liveportrait_root}`",
        f"- Source image: `{report.source_image_path}`",
        f"- Reference size: `{_size_text(report.reference_size)}`",
        f"- Driving input: `{report.driving_path}`",
        f"- Driving status: `{report.driving_status}`",
        f"- FFmpeg: `{report.ffmpeg_path}`",
        f"- Next action: `{report.next_action}`",
        "",
        "## Missing Weights",
        *_markdown_list(report.missing_weight_paths),
        "",
        "## Errors",
        *_markdown_list(report.errors),
        "",
        "## Suggested Command",
        "",
    ]
    if report.suggested_command:
        lines.extend(["```powershell", report.suggested_command, "```"])
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _source_pack_reference(source_root: Path, errors: list[str]) -> tuple[Path | None, tuple[int, int] | tuple[()]]:
    metadata_path = source_root / "source_pack.json"
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"source_pack.json invalid: {exc}")
        return None, ()
    if not isinstance(payload, dict):
        errors.append("source_pack.json must be an object")
        return None, ()
    reference_value = payload.get("reference_image")
    reference_path = _safe_relative_path(source_root, reference_value)
    if reference_path is None:
        errors.append("reference_image must be a safe relative path inside the source pack")
        return None, ()
    if not reference_path.is_file():
        errors.append("reference_image file not found")
        return reference_path, ()
    try:
        with Image.open(reference_path) as image:
            image.verify()
        with Image.open(reference_path) as image:
            return reference_path, image.size
    except (OSError, UnidentifiedImageError) as exc:
        errors.append(f"reference_image invalid: {exc}")
        return reference_path, ()


def _safe_relative_path(root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def _validate_liveportrait_root(root: Path, errors: list[str]) -> None:
    if not root.is_dir():
        errors.append("liveportrait_root not found")
        return
    for filename in REQUIRED_LIVEPORTRAIT_FILES:
        if not (root / filename).is_file():
            errors.append(f"liveportrait file not found: {filename}")


def _missing_human_weight_paths(root: Path) -> tuple[str, ...]:
    missing: list[str] = []
    for relative_path in REQUIRED_HUMAN_WEIGHT_PATHS:
        if not (root / relative_path).is_file():
            missing.append(relative_path)
    return tuple(missing)


def _validate_driving_path(value: Path | str, errors: list[str]) -> tuple[Path | None, str]:
    if value == "":
        errors.append("driving video or motion template is required")
        return None, "missing"
    path = Path(value)
    if not path.is_file():
        errors.append("driving video or motion template not found")
        return None, "missing"
    if path.suffix.lower() not in ALLOWED_DRIVING_SUFFIXES:
        errors.append("driving input must be a video file or LivePortrait motion template")
        return None, "invalid_type"
    status = _driving_file_status(path, errors)
    if status.startswith("valid_"):
        return path, status
    return None, status


def _driving_file_status(path: Path, errors: list[str]) -> str:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        errors.append(f"driving input could not be read: {exc}")
        return "invalid_video"
    if not payload:
        errors.append("driving video is empty")
        return "invalid_video"
    suffix = path.suffix.lower()
    if suffix == ".pkl":
        return "valid_motion_template"
    if _looks_like_video(path, payload):
        return "valid_video"
    errors.append("driving video signature is invalid")
    return "invalid_video"


def _looks_like_video(path: Path, payload: bytes) -> bool:
    suffix = path.suffix.lower()
    if suffix in {".mp4", ".mov"}:
        return b"ftyp" in payload[:32]
    if suffix in {".webm", ".mkv"}:
        return payload.startswith(b"\x1a\x45\xdf\xa3")
    if suffix == ".avi":
        return len(payload) >= 12 and payload.startswith(b"RIFF") and payload[8:12] == b"AVI "
    return False


def _resolve_ffmpeg(value: Path | str, errors: list[str]) -> str:
    if value:
        text = str(value)
        if Path(text).is_file():
            return text
        resolved = shutil.which(text)
        if resolved:
            return resolved
        errors.append("ffmpeg not found")
        return ""
    resolved = shutil.which("ffmpeg")
    if resolved:
        return resolved
    errors.append("ffmpeg not found")
    return ""


def _next_action(
    *,
    liveportrait: Path,
    errors: list[str],
    missing_weight_paths: tuple[str, ...],
    driving: Path | None,
    ffmpeg: str,
) -> str:
    if not liveportrait.is_dir() or any(error.startswith("liveportrait file not found:") for error in errors):
        return "install_liveportrait"
    if missing_weight_paths:
        return "download_liveportrait_weights"
    if driving is None:
        return "add_driving_video"
    if not ffmpeg:
        return "install_ffmpeg"
    if errors:
        return "fix_preflight_errors"
    return "run_liveportrait"


def _suggested_command(liveportrait: Path, source_image: Path | None, driving: Path | None) -> str:
    if source_image is None or driving is None:
        return ""
    return (
        f"Push-Location {_quote(liveportrait)}; "
        f"python inference.py -s {_quote(source_image.resolve())} -d {_quote(driving.resolve())}; "
        "Pop-Location"
    )


def _quote(path: Path) -> str:
    return f'"{path}"'


def _markdown_list(items: tuple[str, ...]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- `{item}`" for item in items]


def _size_text(size: tuple[int, int] | tuple[()]) -> str:
    if len(size) != 2:
        return ""
    return f"{size[0]}x{size[1]}"


def _write_report(report: LivePortraitPreflightReport, report_path: Path | str | None) -> None:
    if report_path is None:
        return
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(report: LivePortraitPreflightReport, markdown_path: Path | str | None) -> None:
    if markdown_path is None:
        return
    target = Path(markdown_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_liveportrait_preflight_markdown(report), encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight a local LivePortrait run for one portrait video source pack.")
    parser.add_argument("source_pack_dir")
    parser.add_argument("--liveportrait-root", required=True)
    parser.add_argument("--driving", default="")
    parser.add_argument("--ffmpeg", default="")
    parser.add_argument("--report", default="")
    parser.add_argument("--markdown", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = inspect_liveportrait_preflight(
        args.source_pack_dir,
        liveportrait_root=args.liveportrait_root,
        driving_path=args.driving,
        ffmpeg_path=args.ffmpeg,
        report_path=args.report or None,
        markdown_path=args.markdown or None,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
