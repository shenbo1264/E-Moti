from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


ASPECT_RATIO_TOLERANCE = 0.002


@dataclass(frozen=True, slots=True)
class PortraitVideoFrameNormalizationReport:
    ok: bool
    source_set_id: str
    set_id: str
    source_pack_dir: str
    output_pack_dir: str
    reference_image: str
    source_frames_dir: str
    output_frames_dir: str
    reference_size: tuple[int, int]
    input_frame_count: int
    normalized_frame_count: int
    resized_frame_count: int
    copied_frame_count: int
    invalid_frame_count: int
    aspect_mismatch_count: int
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source_set_id": self.source_set_id,
            "set_id": self.set_id,
            "source_pack_dir": self.source_pack_dir,
            "output_pack_dir": self.output_pack_dir,
            "reference_image": self.reference_image,
            "source_frames_dir": self.source_frames_dir,
            "output_frames_dir": self.output_frames_dir,
            "reference_size": list(self.reference_size),
            "input_frame_count": self.input_frame_count,
            "normalized_frame_count": self.normalized_frame_count,
            "resized_frame_count": self.resized_frame_count,
            "copied_frame_count": self.copied_frame_count,
            "invalid_frame_count": self.invalid_frame_count,
            "aspect_mismatch_count": self.aspect_mismatch_count,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def normalize_portrait_video_source_pack(
    *,
    source_pack_dir: Path | str,
    output_pack_dir: Path | str | None = None,
) -> PortraitVideoFrameNormalizationReport:
    source_root = Path(source_pack_dir)
    metadata, metadata_errors = _read_metadata(source_root / "source_pack.json")
    source_set_id = _metadata_string(metadata, "set_id") or source_root.name
    normalized_set_id = f"{source_set_id}-normalized"
    output_root = Path(output_pack_dir) if output_pack_dir is not None else source_root.parent / normalized_set_id
    if metadata_errors:
        return _empty_report(
            source_root=source_root,
            output_root=output_root,
            source_set_id=source_set_id,
            set_id=normalized_set_id,
            errors=metadata_errors,
        )

    reference_rel = _metadata_string(metadata, "reference_image")
    frames_rel = _metadata_string(metadata, "frames_dir") or "frames"
    path_errors = _metadata_path_errors({"reference_image": reference_rel, "frames_dir": frames_rel})
    if path_errors:
        return _empty_report(
            source_root=source_root,
            output_root=output_root,
            source_set_id=source_set_id,
            set_id=normalized_set_id,
            errors=path_errors,
        )

    reference_path = source_root / reference_rel
    source_frames_dir = source_root / frames_rel
    reference = _load_image(reference_path)
    if reference is None:
        return _empty_report(
            source_root=source_root,
            output_root=output_root,
            source_set_id=source_set_id,
            set_id=normalized_set_id,
            reference_path=reference_path,
            source_frames_dir=source_frames_dir,
            errors=("reference image invalid or missing",),
        )
    reference_size = reference.size
    frame_paths = _frame_paths(source_frames_dir)
    if not frame_paths:
        return _empty_report(
            source_root=source_root,
            output_root=output_root,
            source_set_id=source_set_id,
            set_id=normalized_set_id,
            reference_path=reference_path,
            source_frames_dir=source_frames_dir,
            reference_size=reference_size,
            errors=("no png frames found",),
        )

    output_frames_dir = output_root / "frames"
    output_frames_dir.mkdir(parents=True, exist_ok=True)
    _copy_pack_support_files(
        metadata=metadata,
        source_root=source_root,
        output_root=output_root,
        reference_rel=reference_rel,
    )

    errors: list[str] = []
    warnings: list[str] = []
    normalized_count = 0
    resized_count = 0
    copied_count = 0
    invalid_count = 0
    aspect_mismatch_count = 0
    for frame_path in frame_paths:
        frame = _load_image(frame_path)
        if frame is None:
            invalid_count += 1
            errors.append(f"{frame_path.name} is not a readable png frame")
            continue
        if not _same_aspect(frame.size, reference_size):
            aspect_mismatch_count += 1
            errors.append(
                f"{frame_path.name} size {frame.size[0]}x{frame.size[1]} aspect ratio "
                f"differs from reference {reference_size[0]}x{reference_size[1]}"
            )
            continue
        if frame.size == reference_size:
            normalized = frame.convert("RGBA")
            copied_count += 1
        else:
            normalized = frame.convert("RGBA").resize(reference_size, Image.Resampling.LANCZOS)
            resized_count += 1
            warnings.append(
                f"{frame_path.name} resized from {frame.size[0]}x{frame.size[1]} "
                f"to {reference_size[0]}x{reference_size[1]}"
            )
        normalized.save(output_frames_dir / frame_path.name)
        normalized_count += 1

    _write_normalized_metadata(
        source_metadata=metadata,
        output_root=output_root,
        set_id=normalized_set_id,
        source_set_id=source_set_id,
        reference_rel=reference_rel,
        source_root=source_root,
        source_frames_dir=source_frames_dir,
        reference_size=reference_size,
    )
    _write_readme(
        output_root=output_root,
        source_root=source_root,
        reference_size=reference_size,
        normalized_count=normalized_count,
    )

    if normalized_count < 3:
        errors.append("fewer than 3 normalized png frames were written")
    return PortraitVideoFrameNormalizationReport(
        ok=not errors,
        source_set_id=source_set_id,
        set_id=normalized_set_id,
        source_pack_dir=str(source_root),
        output_pack_dir=str(output_root),
        reference_image=str(output_root / reference_rel),
        source_frames_dir=str(source_frames_dir),
        output_frames_dir=str(output_frames_dir),
        reference_size=reference_size,
        input_frame_count=len(frame_paths),
        normalized_frame_count=normalized_count,
        resized_frame_count=resized_count,
        copied_frame_count=copied_count,
        invalid_frame_count=invalid_count,
        aspect_mismatch_count=aspect_mismatch_count,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def _read_metadata(path: Path) -> tuple[dict[str, object], tuple[str, ...]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, (f"source_pack.json invalid: {exc}",)
    if not isinstance(payload, dict):
        return {}, ("source_pack.json must be an object",)
    errors: list[str] = []
    for field in ("set_id", "reference_image"):
        if not isinstance(payload.get(field), str) or not str(payload.get(field)).strip():
            errors.append(f"source_pack.json.{field} must be a non-empty string")
    return payload, tuple(errors)


def _metadata_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _metadata_path_errors(paths: dict[str, str]) -> tuple[str, ...]:
    errors: list[str] = []
    for key, value in paths.items():
        path = Path(value)
        if (
            not value
            or path.is_absolute()
            or ".." in path.parts
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
        ):
            errors.append(f"source_pack.json.{key} must be a safe relative path")
    return tuple(errors)


def _load_image(path: Path) -> Image.Image | None:
    try:
        with Image.open(path) as image:
            loaded = image.convert("RGBA")
            loaded.load()
            return loaded
    except (OSError, UnidentifiedImageError):
        return None


def _frame_paths(path: Path) -> tuple[Path, ...]:
    if not path.is_dir():
        return ()
    return tuple(sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".png"))


def _same_aspect(size: tuple[int, int], reference_size: tuple[int, int]) -> bool:
    width, height = size
    reference_width, reference_height = reference_size
    if width <= 0 or height <= 0 or reference_width <= 0 or reference_height <= 0:
        return False
    delta = abs(width * reference_height - height * reference_width)
    scale = max(width * reference_height, height * reference_width)
    return delta / scale <= ASPECT_RATIO_TOLERANCE


def _copy_pack_support_files(
    *,
    metadata: dict[str, object],
    source_root: Path,
    output_root: Path,
    reference_rel: str,
) -> None:
    _copy_relative_file(source_root, output_root, reference_rel)
    for key in ("prompt_path", "provider_prompts_path"):
        value = _metadata_string(metadata, key)
        if value:
            _copy_relative_file(source_root, output_root, value)
    for relative in ("gemini_prompt.md", "provider_prompts.md", "video/README.md"):
        source = source_root / relative
        if source.is_file():
            _copy_relative_file(source_root, output_root, relative)


def _copy_relative_file(source_root: Path, output_root: Path, relative: str) -> None:
    source = source_root / relative
    if not source.is_file():
        return
    target = output_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _write_normalized_metadata(
    *,
    source_metadata: dict[str, object],
    output_root: Path,
    set_id: str,
    source_set_id: str,
    reference_rel: str,
    source_root: Path,
    source_frames_dir: Path,
    reference_size: tuple[int, int],
) -> None:
    payload = dict(source_metadata)
    payload["set_id"] = set_id
    payload["frames_dir"] = "frames"
    payload["reference_image"] = reference_rel
    payload["normalization"] = {
        "source_set_id": source_set_id,
        "source_pack_dir": str(source_root),
        "source_frames_dir": str(source_frames_dir),
        "method": "aspect_ratio_preserving_resize_to_reference",
        "reference_size": list(reference_size),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "source_pack.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_readme(
    *,
    output_root: Path,
    source_root: Path,
    reference_size: tuple[int, int],
    normalized_count: int,
) -> None:
    lines = [
        "# Normalized Portrait Video Source Pack",
        "",
        f"- Source pack: `{source_root}`",
        f"- Reference size: `{reference_size[0]}x{reference_size[1]}`",
        f"- Normalized frame count: `{normalized_count}`",
        "",
        "Run frame preflight on this normalized source root before extraction.",
        "Do not promote any generated motion frames without visual QA and the strict portrait promotion gate.",
        "",
    ]
    (output_root / "FRAME_NORMALIZATION_README.md").write_text("\n".join(lines), encoding="utf-8")


def _empty_report(
    *,
    source_root: Path,
    output_root: Path,
    source_set_id: str = "",
    set_id: str = "",
    reference_path: Path | None = None,
    source_frames_dir: Path | None = None,
    reference_size: tuple[int, int] = (0, 0),
    errors: tuple[str, ...],
) -> PortraitVideoFrameNormalizationReport:
    return PortraitVideoFrameNormalizationReport(
        ok=False,
        source_set_id=source_set_id,
        set_id=set_id,
        source_pack_dir=str(source_root),
        output_pack_dir=str(output_root),
        reference_image=str(reference_path) if reference_path is not None else "",
        source_frames_dir=str(source_frames_dir) if source_frames_dir is not None else "",
        output_frames_dir=str(output_root / "frames"),
        reference_size=reference_size,
        input_frame_count=0,
        normalized_frame_count=0,
        resized_frame_count=0,
        copied_frame_count=0,
        invalid_frame_count=0,
        aspect_mismatch_count=0,
        errors=errors,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clone a portrait video source pack and resize same-aspect provider PNG frames to reference size."
    )
    parser.add_argument("source_pack_dir")
    parser.add_argument("--output-pack-dir", default="")
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = normalize_portrait_video_source_pack(
        source_pack_dir=args.source_pack_dir,
        output_pack_dir=args.output_pack_dir or None,
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
