from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.batch_process_portrait_video_source_packs import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_SOURCE_ROOT,
    scan_portrait_video_source_packs,
)
from tools.art.bundle_portrait_video_source_packs import DEFAULT_OUTPUT_DIR as DEFAULT_HANDOFF_DIR  # noqa: E402
from tools.art.inspect_portrait_video_source_frames import inspect_portrait_video_source_frames  # noqa: E402


@dataclass(frozen=True, slots=True)
class PortraitVideoWorkflowItem:
    set_id: str
    source_pack_dir: str
    source_status: str
    frame_count: int
    readable_frame_count: int
    invalid_frame_count: int
    size_mismatch_count: int
    normalizable_size_mismatch_count: int
    body_drift_warning_count: int
    handoff_zip_path: str
    handoff_status: str
    motion_candidate_dir: str
    motion_candidate_status: str
    next_action: str
    source_next_action: str
    motion_next_action: str
    suggested_commands: tuple[str, ...] = ()
    attention_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "set_id": self.set_id,
            "source_pack_dir": self.source_pack_dir,
            "source_status": self.source_status,
            "frame_count": self.frame_count,
            "readable_frame_count": self.readable_frame_count,
            "invalid_frame_count": self.invalid_frame_count,
            "size_mismatch_count": self.size_mismatch_count,
            "normalizable_size_mismatch_count": self.normalizable_size_mismatch_count,
            "body_drift_warning_count": self.body_drift_warning_count,
            "handoff_zip_path": self.handoff_zip_path,
            "handoff_status": self.handoff_status,
            "motion_candidate_dir": self.motion_candidate_dir,
            "motion_candidate_status": self.motion_candidate_status,
            "next_action": self.next_action,
            "source_next_action": self.source_next_action,
            "motion_next_action": self.motion_next_action,
            "suggested_commands": list(self.suggested_commands),
            "attention_reasons": list(self.attention_reasons),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class PortraitVideoWorkflowReport:
    ok: bool
    source_root: str
    handoff_dir: str
    candidate_root: str
    pack_count: int
    missing_handoff_count: int
    ready_count: int
    waiting_count: int
    insufficient_count: int
    motion_candidate_count: int
    items: tuple[PortraitVideoWorkflowItem, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source_root": self.source_root,
            "handoff_dir": self.handoff_dir,
            "candidate_root": self.candidate_root,
            "pack_count": self.pack_count,
            "missing_handoff_count": self.missing_handoff_count,
            "ready_count": self.ready_count,
            "waiting_count": self.waiting_count,
            "insufficient_count": self.insufficient_count,
            "motion_candidate_count": self.motion_candidate_count,
            "items": [item.to_dict() for item in self.items],
            "errors": list(self.errors),
        }


def inspect_portrait_video_workflow(
    *,
    source_root: Path | str = DEFAULT_SOURCE_ROOT,
    handoff_dir: Path | str = DEFAULT_HANDOFF_DIR,
    candidate_root: Path | str = DEFAULT_OUTPUT_ROOT,
) -> PortraitVideoWorkflowReport:
    root = Path(source_root)
    handoff = Path(handoff_dir)
    candidates = Path(candidate_root)
    batch = scan_portrait_video_source_packs(source_root=root)
    preflight = inspect_portrait_video_source_frames(source_root=root)
    preflight_items = {item.set_id: item for item in preflight.items}
    errors: list[str] = list(batch.errors)

    items: list[PortraitVideoWorkflowItem] = []
    for pack in batch.packs:
        item = _workflow_item(
            pack=pack,
            preflight=preflight_items.get(pack.set_id),
            handoff_dir=handoff,
            candidate_root=candidates,
        )
        errors.extend(item.errors)
        items.append(item)

    return _report(
        source_root=root,
        handoff_dir=handoff,
        candidate_root=candidates,
        items=tuple(items),
        errors=tuple(errors),
    )


def render_portrait_video_workflow_markdown(report: PortraitVideoWorkflowReport) -> str:
    lines = [
        "# Portrait Video Workflow Status",
        "",
        f"- OK: `{str(report.ok).lower()}`",
        f"- Source root: `{report.source_root}`",
        f"- Handoff dir: `{report.handoff_dir}`",
        f"- Candidate root: `{report.candidate_root}`",
        f"- Packs: `{report.pack_count}`",
        f"- Missing handoff zips: `{report.missing_handoff_count}`",
        f"- Ready source packs: `{report.ready_count}`",
        f"- Waiting for frames: `{report.waiting_count}`",
        f"- Insufficient frames: `{report.insufficient_count}`",
        f"- Motion candidates: `{report.motion_candidate_count}`",
        "",
        "| Set | Source Status | Frames | Handoff | Motion Candidate | Next Action |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for item in report.items:
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_cell(item.set_id),
                    _markdown_cell(item.source_status),
                    str(item.frame_count),
                    _markdown_cell(item.handoff_status),
                    _markdown_cell(item.motion_candidate_status),
                    _markdown_cell(item.next_action),
                )
            )
            + " |"
        )
    if report.errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{_markdown_cell(error)}`" for error in report.errors)
    attention = tuple(item for item in report.items if item.attention_reasons)
    if attention:
        lines.extend(["", "## Attention", ""])
        for item in attention:
            reasons = ", ".join(f"`{_markdown_cell(reason)}`" for reason in item.attention_reasons)
            lines.append(f"- `{_markdown_cell(item.set_id)}`: {reasons}")
        lines.extend(["", "| Set | Source Next | Motion Next |", "| --- | --- | --- |"])
        for item in attention:
            lines.append(
                "| "
                + " | ".join(
                    (
                        _markdown_cell(item.set_id),
                        _markdown_cell(item.source_next_action),
                        _markdown_cell(item.motion_next_action),
                    )
                )
                + " |"
            )
        command_items = tuple(item for item in attention if item.suggested_commands)
        if command_items:
            lines.extend(["", "## Suggested Commands", ""])
            for item in command_items:
                lines.append(f"### {_markdown_cell(item.set_id)}")
                lines.append("")
                for command in item.suggested_commands:
                    lines.append(f"- `{_markdown_cell(command)}`")
                lines.append("")
    lines.append("")
    return "\n".join(lines)


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _workflow_item(
    *,
    pack,
    preflight,
    handoff_dir: Path,
    candidate_root: Path,
) -> PortraitVideoWorkflowItem:
    source_status = preflight.status if preflight is not None else pack.status
    frame_count = preflight.frame_count if preflight is not None else pack.frame_count
    readable_frame_count = preflight.readable_frame_count if preflight is not None else pack.frame_count
    invalid_frame_count = preflight.invalid_frame_count if preflight is not None else 0
    size_mismatch_count = preflight.size_mismatch_count if preflight is not None else 0
    normalizable_size_mismatch_count = (
        preflight.normalizable_size_mismatch_count if preflight is not None else 0
    )
    body_drift_warning_count = preflight.body_drift_warning_count if preflight is not None else 0
    warnings = preflight.warnings if preflight is not None else ()
    errors = preflight.errors if preflight is not None else pack.errors
    handoff_zip = handoff_dir / f"{pack.set_id}.zip"
    handoff_status = "present" if handoff_zip.is_file() else "missing"
    motion_candidate_dir = candidate_root / f"portrait-candidate-{pack.set_id}-motion"
    motion_candidate_manifest = motion_candidate_dir / "portrait_candidate.json"
    motion_candidate_report = motion_candidate_dir / "candidate-motion-frame-report.json"
    motion_candidate_status, motion_candidate_errors = _motion_candidate_status(
        manifest_path=motion_candidate_manifest,
        report_path=motion_candidate_report,
    )
    item_errors = tuple(errors) + motion_candidate_errors
    source_next_action = _source_next_action(
        source_status=source_status,
        source_next_action=preflight.next_action if preflight is not None else "",
        handoff_status=handoff_status,
        motion_candidate_status=motion_candidate_status,
    )
    motion_next_action = _motion_next_action(motion_candidate_status=motion_candidate_status)
    next_action = _next_action(
        source_next_action=source_next_action,
        motion_next_action=motion_next_action,
        motion_candidate_status=motion_candidate_status,
    )
    suggested_commands = _suggested_commands(
        set_id=pack.set_id,
        source_pack_dir=Path(pack.source_pack_dir),
        source_root=Path(pack.source_pack_dir).parent,
        handoff_dir=handoff_dir,
        candidate_root=candidate_root,
        source_next_action=source_next_action,
        motion_next_action=motion_next_action,
    )
    return PortraitVideoWorkflowItem(
        set_id=pack.set_id,
        source_pack_dir=pack.source_pack_dir,
        source_status=source_status,
        frame_count=frame_count,
        readable_frame_count=readable_frame_count,
        invalid_frame_count=invalid_frame_count,
        size_mismatch_count=size_mismatch_count,
        normalizable_size_mismatch_count=normalizable_size_mismatch_count,
        body_drift_warning_count=body_drift_warning_count,
        handoff_zip_path=str(handoff_zip),
        handoff_status=handoff_status,
        motion_candidate_dir=str(motion_candidate_dir),
        motion_candidate_status=motion_candidate_status,
        next_action=next_action,
        source_next_action=source_next_action,
        motion_next_action=motion_next_action,
        suggested_commands=suggested_commands,
        attention_reasons=_attention_reasons(
            source_status=source_status,
            handoff_status=handoff_status,
            motion_candidate_status=motion_candidate_status,
            invalid_frame_count=invalid_frame_count,
            size_mismatch_count=size_mismatch_count,
            normalizable_size_mismatch_count=normalizable_size_mismatch_count,
            body_drift_warning_count=body_drift_warning_count,
        ),
        warnings=warnings,
        errors=item_errors,
    )


def _motion_candidate_status(*, manifest_path: Path, report_path: Path) -> tuple[str, tuple[str, ...]]:
    if manifest_path.is_file():
        return "present", ()
    if not report_path.is_file():
        return "missing", ()
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return "invalid_report", (f"motion extraction report invalid: {exc}",)
    if not isinstance(payload, dict):
        return "invalid_report", ("motion extraction report must be a JSON object",)
    if payload.get("ok") is False:
        raw_errors = payload.get("errors")
        if isinstance(raw_errors, list) and raw_errors:
            errors = tuple(
                f"motion extraction failed: {error}"
                for error in raw_errors
                if isinstance(error, str) and error.strip()
            )
            return "failed", errors or ("motion extraction failed",)
        return "failed", ("motion extraction failed",)
    if payload.get("ok") is True:
        return "incomplete", ("motion extraction report passed but portrait_candidate.json is missing",)
    return "invalid_report", ("motion extraction report missing boolean ok field",)


def _source_next_action(
    *,
    source_status: str,
    source_next_action: str,
    handoff_status: str,
    motion_candidate_status: str,
) -> str:
    if source_status in {"invalid", "failed"}:
        return "fix_source_pack"
    if source_status == "invalid_frames":
        return "replace_invalid_frames"
    if handoff_status == "missing":
        return "bundle_handoff"
    if source_status == "waiting_for_frames":
        return "generate_ai_video"
    if source_status == "insufficient_frames":
        return "export_more_frames"
    if source_status == "ready_with_warnings":
        if source_next_action == "normalize_frames":
            return "normalize_frames"
        return "review_frame_warnings"
    if source_status == "ready":
        return "review_motion_candidate" if motion_candidate_status == "present" else "process_frames"
    return "inspect_manually"


def _motion_next_action(*, motion_candidate_status: str) -> str:
    if motion_candidate_status == "failed":
        return "regenerate_ai_video"
    if motion_candidate_status in {"invalid_report", "incomplete"}:
        return "inspect_motion_candidate"
    if motion_candidate_status == "present":
        return "review_motion_candidate"
    return "none"


def _next_action(
    *,
    source_next_action: str,
    motion_next_action: str,
    motion_candidate_status: str,
) -> str:
    if motion_candidate_status in {"failed", "invalid_report", "incomplete"}:
        return motion_next_action
    if source_next_action:
        return source_next_action
    return "inspect_manually"


def _attention_reasons(
    *,
    source_status: str,
    handoff_status: str,
    motion_candidate_status: str,
    invalid_frame_count: int,
    size_mismatch_count: int,
    normalizable_size_mismatch_count: int,
    body_drift_warning_count: int,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if handoff_status == "missing":
        reasons.append("missing_handoff")
    if source_status == "waiting_for_frames":
        reasons.append("waiting_for_frames")
    if source_status == "insufficient_frames":
        reasons.append("insufficient_frames")
    if source_status == "invalid_frames" or invalid_frame_count > 0:
        reasons.append("invalid_frames")
    if normalizable_size_mismatch_count > 0:
        reasons.append("normalizable_size_mismatch")
    if size_mismatch_count > normalizable_size_mismatch_count:
        reasons.append("size_mismatch")
    if body_drift_warning_count > 0:
        reasons.append("body_drift_warnings")
    if motion_candidate_status == "failed":
        reasons.append("failed_motion_extraction")
    if motion_candidate_status == "invalid_report":
        reasons.append("invalid_motion_candidate_report")
    if motion_candidate_status == "incomplete":
        reasons.append("incomplete_motion_candidate")
    return tuple(reasons)


def _suggested_commands(
    *,
    set_id: str,
    source_pack_dir: Path,
    source_root: Path,
    handoff_dir: Path,
    candidate_root: Path,
    source_next_action: str,
    motion_next_action: str,
) -> tuple[str, ...]:
    commands: list[str] = []
    if source_next_action == "bundle_handoff":
        commands.append(
            "python tools\\art\\bundle_portrait_video_source_packs.py "
            f"{_command_path(source_root)} --output-dir {_command_path(handoff_dir)} "
            "--report artifacts\\portrait-video-handoff-report.json"
        )
    elif source_next_action == "normalize_frames":
        output_pack = _normalized_source_pack_dir(source_pack_dir)
        commands.append(
            "python tools\\art\\normalize_portrait_video_source_frames.py "
            f"{_command_path(source_pack_dir)} --output-pack-dir {_command_path(output_pack)} "
            "--report artifacts\\portrait-video-frame-normalization.json"
        )
        commands.append(
            "python tools\\art\\inspect_portrait_video_source_frames.py "
            f"{_command_path(source_root)} --report artifacts\\portrait-video-frame-preflight.json"
        )
    elif source_next_action in {"review_frame_warnings", "replace_invalid_frames"}:
        commands.append(
            "python tools\\art\\inspect_portrait_video_source_frames.py "
            f"{_command_path(source_root)} --report artifacts\\portrait-video-frame-preflight.json"
        )
    elif source_next_action == "generate_ai_video":
        commands.append(
            "python tools\\art\\inspect_liveportrait_preflight.py "
            f"{_command_path(source_pack_dir)} "
            "--liveportrait-root tmp\\liveportrait_research\\LivePortrait "
            f"--driving tmp\\liveportrait_research\\drivers\\{set_id}-blink-driver.mp4 "
            f"--report artifacts\\liveportrait-preflight-{set_id}.json "
            f"--markdown artifacts\\liveportrait-preflight-{set_id}.md"
        )
    elif source_next_action == "process_frames":
        output_dir = candidate_root / f"portrait-candidate-{set_id}-motion"
        commands.append(
            "python tools\\art\\process_portrait_video_source_pack.py "
            f"{_command_path(source_pack_dir)} --output-dir {_command_path(output_dir)}"
        )
    if motion_next_action == "regenerate_ai_video":
        commands.append(
            "python tools\\art\\inspect_portrait_video_workflow.py "
            f"{_command_path(source_root)} --handoff-dir {_command_path(handoff_dir)} "
            f"--candidate-root {_command_path(candidate_root)} "
            "--report artifacts\\portrait-video-workflow-report.json "
            "--markdown artifacts\\portrait-video-workflow-report.md"
        )
    return _dedupe(commands)


def _normalized_source_pack_dir(source_pack_dir: Path) -> Path:
    normalized_name = source_pack_dir.name if source_pack_dir.name.endswith("-normalized") else f"{source_pack_dir.name}-normalized"
    return source_pack_dir.parent / normalized_name


def _command_path(path: Path) -> str:
    text = str(path)
    return f'"{text}"' if any(char.isspace() for char in text) else text


def _dedupe(items: list[str]) -> tuple[str, ...]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return tuple(result)


def _report(
    *,
    source_root: Path,
    handoff_dir: Path,
    candidate_root: Path,
    items: tuple[PortraitVideoWorkflowItem, ...],
    errors: tuple[str, ...],
) -> PortraitVideoWorkflowReport:
    return PortraitVideoWorkflowReport(
        ok=not errors,
        source_root=str(source_root),
        handoff_dir=str(handoff_dir),
        candidate_root=str(candidate_root),
        pack_count=len(items),
        missing_handoff_count=sum(1 for item in items if item.handoff_status == "missing"),
        ready_count=sum(1 for item in items if item.source_status == "ready"),
        waiting_count=sum(1 for item in items if item.source_status == "waiting_for_frames"),
        insufficient_count=sum(1 for item in items if item.source_status == "insufficient_frames"),
        motion_candidate_count=sum(1 for item in items if item.motion_candidate_status == "present"),
        items=items,
        errors=errors,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect AI video portrait source pack workflow status.")
    parser.add_argument("source_root", nargs="?", default=str(DEFAULT_SOURCE_ROOT))
    parser.add_argument("--handoff-dir", default=str(DEFAULT_HANDOFF_DIR))
    parser.add_argument("--candidate-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--report", default="")
    parser.add_argument("--markdown", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = inspect_portrait_video_workflow(
        source_root=args.source_root,
        handoff_dir=args.handoff_dir,
        candidate_root=args.candidate_root,
    )
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
    if args.markdown:
        target = Path(args.markdown)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_portrait_video_workflow_markdown(report), encoding="utf-8")
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
