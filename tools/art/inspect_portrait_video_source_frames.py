from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_SOURCE_ROOT = Path("artifacts") / "portrait-video-source"
MIN_READY_FRAME_COUNT = 3


@dataclass(frozen=True, slots=True)
class PortraitVideoFramePreflightItem:
    set_id: str
    source_pack_dir: str
    reference_image: str
    frames_dir: str
    frame_count: int
    readable_frame_count: int
    invalid_frame_count: int
    size_mismatch_count: int
    status: str
    next_action: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "set_id": self.set_id,
            "source_pack_dir": self.source_pack_dir,
            "reference_image": self.reference_image,
            "frames_dir": self.frames_dir,
            "frame_count": self.frame_count,
            "readable_frame_count": self.readable_frame_count,
            "invalid_frame_count": self.invalid_frame_count,
            "size_mismatch_count": self.size_mismatch_count,
            "status": self.status,
            "next_action": self.next_action,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class PortraitVideoFramePreflightReport:
    ok: bool
    source_root: str
    pack_count: int
    ready_count: int
    waiting_count: int
    insufficient_count: int
    invalid_count: int
    warning_count: int
    items: tuple[PortraitVideoFramePreflightItem, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source_root": self.source_root,
            "pack_count": self.pack_count,
            "ready_count": self.ready_count,
            "waiting_count": self.waiting_count,
            "insufficient_count": self.insufficient_count,
            "invalid_count": self.invalid_count,
            "warning_count": self.warning_count,
            "items": [item.to_dict() for item in self.items],
            "errors": list(self.errors),
        }


def inspect_portrait_video_source_frames(
    *,
    source_root: Path | str = DEFAULT_SOURCE_ROOT,
) -> PortraitVideoFramePreflightReport:
    root = Path(source_root)
    if not root.is_dir():
        return _report(
            source_root=root,
            items=(),
            errors=("source_root not found",),
        )

    items = tuple(_inspect_source_pack(path) for path in _source_pack_dirs(root))
    errors = tuple(error for item in items for error in item.errors)
    return _report(source_root=root, items=items, errors=errors)


def _source_pack_dirs(root: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_dir() and (path / "source_pack.json").is_file()
    )


def _inspect_source_pack(path: Path) -> PortraitVideoFramePreflightItem:
    payload, metadata_errors = _read_metadata(path / "source_pack.json")
    set_id = _metadata_string(payload, "set_id") or path.name
    reference_rel = _metadata_string(payload, "reference_image")
    frames_rel = _metadata_string(payload, "frames_dir") or "frames"
    path_errors = _metadata_path_errors(
        {
            "reference_image": reference_rel,
            "frames_dir": frames_rel,
        }
    )
    reference = path / reference_rel if reference_rel else path / "reference-missing.png"
    frames_dir = path / frames_rel
    frame_paths = _frame_paths(frames_dir)
    errors = list(metadata_errors) + list(path_errors)
    warnings: list[str] = []

    reference_size = _image_size(reference)
    if reference_size is None:
        errors.append("reference image invalid or missing")

    readable_count = 0
    invalid_count = 0
    mismatch_count = 0
    for frame_path in frame_paths:
        frame_size = _image_size(frame_path)
        if frame_size is None:
            invalid_count += 1
            errors.append(f"{frame_path.name} is not a readable png frame")
            continue
        readable_count += 1
        if reference_size is not None and frame_size != reference_size:
            mismatch_count += 1
            warnings.append(
                f"{frame_path.name} size {frame_size[0]}x{frame_size[1]} "
                f"differs from reference {reference_size[0]}x{reference_size[1]}"
            )

    status = _status(
        errors=tuple(errors),
        frame_count=len(frame_paths),
        readable_frame_count=readable_count,
        warning_count=len(warnings),
    )
    return PortraitVideoFramePreflightItem(
        set_id=set_id,
        source_pack_dir=str(path),
        reference_image=str(reference),
        frames_dir=str(frames_dir),
        frame_count=len(frame_paths),
        readable_frame_count=readable_count,
        invalid_frame_count=invalid_count,
        size_mismatch_count=mismatch_count,
        status=status,
        next_action=_next_action(status),
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


def _frame_paths(path: Path) -> tuple[Path, ...]:
    if not path.is_dir():
        return ()
    return tuple(sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".png"))


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as image:
            image.load()
            return image.size
    except (OSError, UnidentifiedImageError):
        return None


def _status(
    *,
    errors: tuple[str, ...],
    frame_count: int,
    readable_frame_count: int,
    warning_count: int,
) -> str:
    if errors:
        return "invalid_frames"
    if frame_count <= 0:
        return "waiting_for_frames"
    if readable_frame_count < MIN_READY_FRAME_COUNT:
        return "insufficient_frames"
    if warning_count:
        return "ready_with_warnings"
    return "ready"


def _next_action(status: str) -> str:
    if status == "waiting_for_frames":
        return "generate_ai_video"
    if status == "insufficient_frames":
        return "export_more_frames"
    if status == "invalid_frames":
        return "replace_invalid_frames"
    if status == "ready_with_warnings":
        return "review_frame_warnings"
    if status == "ready":
        return "process_frames"
    return "inspect_manually"


def _report(
    *,
    source_root: Path,
    items: tuple[PortraitVideoFramePreflightItem, ...],
    errors: tuple[str, ...],
) -> PortraitVideoFramePreflightReport:
    invalid_count = sum(1 for item in items if item.status == "invalid_frames")
    return PortraitVideoFramePreflightReport(
        ok=not errors and invalid_count == 0,
        source_root=str(source_root),
        pack_count=len(items),
        ready_count=sum(1 for item in items if item.status == "ready"),
        waiting_count=sum(1 for item in items if item.status == "waiting_for_frames"),
        insufficient_count=sum(1 for item in items if item.status == "insufficient_frames"),
        invalid_count=invalid_count,
        warning_count=sum(1 for item in items if item.warnings),
        items=items,
        errors=errors,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight exported AI video PNG frames before motion extraction.")
    parser.add_argument("source_root", nargs="?", default=str(DEFAULT_SOURCE_ROOT))
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = inspect_portrait_video_source_frames(source_root=args.source_root)
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
