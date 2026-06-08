from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.extract_portrait_motion_frames import (  # noqa: E402
    DEFAULT_IDLE_FRAME_COUNT,
    DEFAULT_MAX_BODY_DRIFT,
    extract_portrait_motion_frames,
)


DEFAULT_CANDIDATE_ROOT = Path("artifacts")


@dataclass(frozen=True, slots=True)
class PortraitVideoSourcePackProcessReport:
    ok: bool
    set_id: str
    source_pack_dir: str
    output_dir: str
    reference_image: str
    frames_dir: str
    prompt_path: str
    candidate_manifest_path: str
    extraction_report_path: str
    motion_frame_count: int
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "set_id": self.set_id,
            "source_pack_dir": self.source_pack_dir,
            "output_dir": self.output_dir,
            "reference_image": self.reference_image,
            "frames_dir": self.frames_dir,
            "prompt_path": self.prompt_path,
            "candidate_manifest_path": self.candidate_manifest_path,
            "extraction_report_path": self.extraction_report_path,
            "motion_frame_count": self.motion_frame_count,
            "errors": list(self.errors),
        }


def process_portrait_video_source_pack(
    *,
    source_pack_dir: Path | str,
    output_dir: Path | str | None = None,
    idle_frame_count: int = DEFAULT_IDLE_FRAME_COUNT,
    max_body_drift: float = DEFAULT_MAX_BODY_DRIFT,
) -> PortraitVideoSourcePackProcessReport:
    source_root = Path(source_pack_dir)
    metadata_path = source_root / "source_pack.json"
    metadata, metadata_errors = _read_metadata(metadata_path)
    if metadata_errors:
        return _empty_report(source_root=source_root, errors=metadata_errors)

    set_id = _metadata_string(metadata, "set_id")
    reference_rel = _metadata_string(metadata, "reference_image")
    frames_rel = _metadata_string(metadata, "frames_dir") or "frames"
    prompt_rel = _metadata_string(metadata, "prompt_path") or "gemini_prompt.md"
    path_errors = _metadata_path_errors(
        {
            "reference_image": reference_rel,
            "frames_dir": frames_rel,
            "prompt_path": prompt_rel,
        }
    )
    if path_errors:
        return _empty_report(source_root=source_root, errors=path_errors)
    reference_path = source_root / reference_rel
    frames_dir = source_root / frames_rel
    prompt_path = source_root / prompt_rel
    output = Path(output_dir) if output_dir is not None else DEFAULT_CANDIDATE_ROOT / f"portrait-candidate-{set_id}-motion"
    report_path = output / "candidate-motion-frame-report.json"
    prompt_text = _read_text(prompt_path)

    extraction = extract_portrait_motion_frames(
        reference_image_path=reference_path,
        frames_dir=frames_dir,
        output_dir=output,
        report_path=report_path,
        idle_frame_count=idle_frame_count,
        max_body_drift=max_body_drift,
        source_tool="Gemini video",
        generation_prompt=prompt_text,
    )
    return PortraitVideoSourcePackProcessReport(
        ok=extraction.ok,
        set_id=set_id,
        source_pack_dir=str(source_root),
        output_dir=str(output),
        reference_image=str(reference_path),
        frames_dir=str(frames_dir),
        prompt_path=str(prompt_path),
        candidate_manifest_path=extraction.manifest_path,
        extraction_report_path=extraction.report_path,
        motion_frame_count=len(extraction.motion_frames),
        errors=extraction.errors,
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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _empty_report(
    *,
    source_root: Path,
    errors: tuple[str, ...],
) -> PortraitVideoSourcePackProcessReport:
    return PortraitVideoSourcePackProcessReport(
        ok=False,
        set_id="",
        source_pack_dir=str(source_root),
        output_dir="",
        reference_image="",
        frames_dir="",
        prompt_path="",
        candidate_manifest_path="",
        extraction_report_path="",
        motion_frame_count=0,
        errors=errors,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process a Gemini portrait video source pack into a motion candidate.")
    parser.add_argument("source_pack_dir")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--idle-frame-count", type=int, default=DEFAULT_IDLE_FRAME_COUNT)
    parser.add_argument("--max-body-drift", type=float, default=DEFAULT_MAX_BODY_DRIFT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = process_portrait_video_source_pack(
        source_pack_dir=args.source_pack_dir,
        output_dir=args.output_dir or None,
        idle_frame_count=args.idle_frame_count,
        max_body_drift=args.max_body_drift,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
