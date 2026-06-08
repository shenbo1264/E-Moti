from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.process_portrait_video_source_pack import (  # noqa: E402
    process_portrait_video_source_pack,
)


DEFAULT_SOURCE_ROOT = Path("artifacts") / "portrait-video-source"
DEFAULT_OUTPUT_ROOT = Path("artifacts")


@dataclass(frozen=True, slots=True)
class PortraitVideoSourcePackStatus:
    set_id: str
    source_pack_dir: str
    frame_count: int
    status: str
    output_dir: str = ""
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "set_id": self.set_id,
            "source_pack_dir": self.source_pack_dir,
            "frame_count": self.frame_count,
            "status": self.status,
            "output_dir": self.output_dir,
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class PortraitVideoSourceBatchReport:
    ok: bool
    source_root: str
    process_ready: bool
    pack_count: int
    ready_count: int
    waiting_count: int
    processed_count: int
    failed_count: int
    packs: tuple[PortraitVideoSourcePackStatus, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source_root": self.source_root,
            "process_ready": self.process_ready,
            "pack_count": self.pack_count,
            "ready_count": self.ready_count,
            "waiting_count": self.waiting_count,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "packs": [pack.to_dict() for pack in self.packs],
            "errors": list(self.errors),
        }


def scan_portrait_video_source_packs(
    *,
    source_root: Path | str = DEFAULT_SOURCE_ROOT,
    process_ready: bool = False,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
) -> PortraitVideoSourceBatchReport:
    root = Path(source_root)
    errors: list[str] = []
    if not root.is_dir():
        errors.append("source_root not found")
        return _report(
            source_root=root,
            process_ready=process_ready,
            packs=(),
            errors=tuple(errors),
        )

    packs: list[PortraitVideoSourcePackStatus] = []
    for source_pack in _source_pack_dirs(root):
        status = _source_pack_status(source_pack)
        if process_ready and status.status == "ready":
            output = Path(output_root) / f"portrait-candidate-{status.set_id}-motion"
            processed = process_portrait_video_source_pack(source_pack_dir=source_pack, output_dir=output)
            if processed.ok:
                status = PortraitVideoSourcePackStatus(
                    set_id=status.set_id,
                    source_pack_dir=status.source_pack_dir,
                    frame_count=status.frame_count,
                    status="processed",
                    output_dir=processed.output_dir,
                )
            else:
                status = PortraitVideoSourcePackStatus(
                    set_id=status.set_id,
                    source_pack_dir=status.source_pack_dir,
                    frame_count=status.frame_count,
                    status="failed",
                    output_dir=processed.output_dir,
                    errors=processed.errors,
                )
        packs.append(status)

    return _report(
        source_root=root,
        process_ready=process_ready,
        packs=tuple(packs),
        errors=tuple(errors),
    )


def _source_pack_dirs(root: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_dir() and (path / "source_pack.json").is_file()
    )


def _source_pack_status(path: Path) -> PortraitVideoSourcePackStatus:
    payload, errors = _read_metadata(path / "source_pack.json")
    set_id = payload.get("set_id") if isinstance(payload.get("set_id"), str) else path.name
    frames_dir_name = payload.get("frames_dir") if isinstance(payload.get("frames_dir"), str) else "frames"
    frames_dir = path / frames_dir_name
    frame_count = _png_frame_count(frames_dir)
    if errors:
        return PortraitVideoSourcePackStatus(
            set_id=str(set_id),
            source_pack_dir=str(path),
            frame_count=frame_count,
            status="invalid",
            errors=errors,
        )
    if frame_count <= 0:
        return PortraitVideoSourcePackStatus(
            set_id=str(set_id),
            source_pack_dir=str(path),
            frame_count=0,
            status="waiting_for_frames",
        )
    return PortraitVideoSourcePackStatus(
        set_id=str(set_id),
        source_pack_dir=str(path),
        frame_count=frame_count,
        status="ready",
    )


def _read_metadata(path: Path) -> tuple[dict[str, object], tuple[str, ...]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, (f"source_pack.json invalid: {exc}",)
    if not isinstance(payload, dict):
        return {}, ("source_pack.json must be an object",)
    errors: list[str] = []
    if not isinstance(payload.get("set_id"), str) or not str(payload.get("set_id")).strip():
        errors.append("source_pack.json.set_id must be a non-empty string")
    return payload, tuple(errors)


def _png_frame_count(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".png")


def _report(
    *,
    source_root: Path,
    process_ready: bool,
    packs: tuple[PortraitVideoSourcePackStatus, ...],
    errors: tuple[str, ...],
) -> PortraitVideoSourceBatchReport:
    ready_count = sum(1 for pack in packs if pack.status == "ready")
    waiting_count = sum(1 for pack in packs if pack.status == "waiting_for_frames")
    processed_count = sum(1 for pack in packs if pack.status == "processed")
    failed_count = sum(1 for pack in packs if pack.status in {"failed", "invalid"})
    return PortraitVideoSourceBatchReport(
        ok=not errors and failed_count == 0,
        source_root=str(source_root),
        process_ready=process_ready,
        pack_count=len(packs),
        ready_count=ready_count,
        waiting_count=waiting_count,
        processed_count=processed_count,
        failed_count=failed_count,
        packs=packs,
        errors=errors,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan or process local Gemini portrait video source packs.")
    parser.add_argument("source_root", nargs="?", default=str(DEFAULT_SOURCE_ROOT))
    parser.add_argument("--process-ready", action="store_true")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = scan_portrait_video_source_packs(
        source_root=args.source_root,
        process_ready=args.process_ready,
        output_root=args.output_root,
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
