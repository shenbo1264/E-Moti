from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_MAX_BODY_DRIFT = 16.0
PROMPT_CONSTRAINTS = (
    "Keep the exact same canvas, aspect ratio, crop, camera, and full-body framing as the reference.",
    "Keep the character identity, outfit, silhouette, feet, hands, shoulders, hips, and hair mass fixed.",
    "Only eyelids, tiny chest breathing, and slight hair-tip movement may animate.",
    "No zoom, pan, reframing, body recomposition, pose change, mouth talking, gesture, text, logo, or watermark.",
    "Export PNG frames back to the matching source pack frames folder, then rerun frame preflight and visual QA.",
)


@dataclass(frozen=True, slots=True)
class PortraitVideoRegenerationBrief:
    ok: bool
    workflow_report_path: str
    frame_qa_report_path: str
    set_id: str
    decision_state: str
    frame_status: str
    frame_count: int
    sampled_frame_count: int
    size_mismatch_count: int
    max_body_drift: float
    preview_path: str
    blockers: tuple[str, ...]
    retry_prompt: str
    negative_prompt: str
    prompt_constraints: tuple[str, ...]
    suggested_commands: tuple[str, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "workflow_report_path": self.workflow_report_path,
            "frame_qa_report_path": self.frame_qa_report_path,
            "set_id": self.set_id,
            "decision_state": self.decision_state,
            "frame_status": self.frame_status,
            "frame_count": self.frame_count,
            "sampled_frame_count": self.sampled_frame_count,
            "size_mismatch_count": self.size_mismatch_count,
            "max_body_drift": self.max_body_drift,
            "preview_path": self.preview_path,
            "blockers": list(self.blockers),
            "retry_prompt": self.retry_prompt,
            "negative_prompt": self.negative_prompt,
            "prompt_constraints": list(self.prompt_constraints),
            "suggested_commands": list(self.suggested_commands),
            "errors": list(self.errors),
        }


def build_portrait_video_regeneration_brief(
    *,
    workflow_report_path: Path | str,
    frame_qa_report_path: Path | str | None = None,
    set_id: str = "",
) -> PortraitVideoRegenerationBrief:
    workflow_path = Path(workflow_report_path)
    frame_qa_path = Path(frame_qa_report_path) if frame_qa_report_path else None
    workflow = _load_json_object(workflow_path)
    frame_qa = _load_json_object(frame_qa_path) if frame_qa_path is not None else {}
    errors: list[str] = []
    if not workflow:
        errors.append("workflow report must be a JSON object")
    target_set_id = set_id or _optional_string(frame_qa.get("set_id")) or _first_attention_set_id(workflow)
    item = _workflow_item(workflow, target_set_id)
    if workflow and item is None:
        errors.append("target set not found in workflow report")

    blockers = _blockers(item, frame_qa)
    decision_state = _decision_state(blockers, item, frame_qa)
    suggested_commands = _suggested_commands(item)
    max_body_drift = _nonnegative_float(frame_qa.get("max_body_drift"))
    return PortraitVideoRegenerationBrief(
        ok=not errors,
        workflow_report_path=str(workflow_path),
        frame_qa_report_path=str(frame_qa_path) if frame_qa_path is not None else "",
        set_id=target_set_id,
        decision_state="invalid_report" if errors else decision_state,
        frame_status=_optional_string(frame_qa.get("status")) or _optional_string(item.get("source_status") if item else None),
        frame_count=_nonnegative_int(frame_qa.get("frame_count")) or _nonnegative_int(item.get("frame_count") if item else None),
        sampled_frame_count=_nonnegative_int(frame_qa.get("sampled_frame_count")),
        size_mismatch_count=_nonnegative_int(frame_qa.get("size_mismatch_count")) or _nonnegative_int(item.get("size_mismatch_count") if item else None),
        max_body_drift=max_body_drift,
        preview_path=_optional_string(frame_qa.get("preview_path")),
        blockers=tuple(blockers),
        retry_prompt=_provider_retry_prompt(set_id=target_set_id, max_body_drift=max_body_drift, blockers=blockers),
        negative_prompt=_provider_negative_prompt(),
        prompt_constraints=PROMPT_CONSTRAINTS,
        suggested_commands=tuple(suggested_commands),
        errors=tuple(errors),
    )


def render_portrait_video_regeneration_markdown(brief: PortraitVideoRegenerationBrief) -> str:
    lines = [
        "# Portrait Video Regeneration Brief",
        "",
        f"- Set: `{brief.set_id}`",
        f"- Decision state: `{brief.decision_state}`",
        f"- Frame status: `{brief.frame_status}`",
        f"- Frame count: `{brief.frame_count}`",
        f"- Sampled frames: `{brief.sampled_frame_count}`",
        f"- Size mismatches: `{brief.size_mismatch_count}`",
        f"- Max body drift: `{brief.max_body_drift}`",
        f"- Preview: `{brief.preview_path}`",
        "",
        "## Blockers",
        *_markdown_list(brief.blockers),
        "",
        "## Provider Retry Prompt",
        "",
        brief.retry_prompt or "None",
        "",
        "## Provider Negative Prompt",
        "",
        brief.negative_prompt or "None",
        "",
        "## Prompt Constraints",
        *_markdown_list(brief.prompt_constraints),
        "",
        "## Suggested Commands",
        *_markdown_list(brief.suggested_commands),
        "",
        "## Errors",
        *_markdown_list(brief.errors),
        "",
    ]
    return "\n".join(lines)


def _load_json_object(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_attention_set_id(workflow: dict[str, object]) -> str:
    for item in _workflow_items(workflow):
        if _string_list(item.get("attention_reasons")) or _string_list(item.get("errors")):
            return _optional_string(item.get("set_id"))
    items = _workflow_items(workflow)
    return _optional_string(items[0].get("set_id")) if items else ""


def _workflow_item(workflow: dict[str, object], set_id: str) -> dict[str, object] | None:
    for item in _workflow_items(workflow):
        if _optional_string(item.get("set_id")) == set_id:
            return item
    return None


def _workflow_items(workflow: dict[str, object]) -> list[dict[str, object]]:
    value = workflow.get("items")
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _blockers(item: dict[str, object] | None, frame_qa: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    if item:
        blockers.extend(f"workflow attention: {reason}" for reason in _string_list(item.get("attention_reasons")))
        blockers.extend(_string_list(item.get("errors")))
    frame_status = _optional_string(frame_qa.get("status"))
    if frame_status and frame_status != "ready":
        blockers.append(f"frame visual QA status: {frame_status}")
    max_body_drift = _nonnegative_float(frame_qa.get("max_body_drift"))
    if max_body_drift > DEFAULT_MAX_BODY_DRIFT:
        blockers.append(f"max body drift {max_body_drift} exceeds {DEFAULT_MAX_BODY_DRIFT:.1f}")
    return _dedupe(blockers)


def _decision_state(
    blockers: list[str],
    item: dict[str, object] | None,
    frame_qa: dict[str, object],
) -> str:
    if any("body_drift" in blocker or "failed_motion" in blocker for blocker in blockers):
        return "regenerate_ai_video"
    if _optional_string(frame_qa.get("status")) == "ready":
        return "process_frames"
    if item:
        return _optional_string(item.get("next_action")) or "inspect_manually"
    return "inspect_manually"


def _suggested_commands(item: dict[str, object] | None) -> list[str]:
    if not item:
        return []
    return [
        command
        for command in _string_list(item.get("suggested_commands"))
        if "portrait_video_regeneration_brief.py" not in command
    ]


def _provider_retry_prompt(*, set_id: str, max_body_drift: float, blockers: list[str]) -> str:
    failure_note = "Previous attempt failed because body drift was too high"
    if max_body_drift:
        failure_note = f"{failure_note}: max body drift {max_body_drift} exceeded {DEFAULT_MAX_BODY_DRIFT:.1f}."
    elif blockers:
        failure_note = f"{failure_note}: {'; '.join(blockers)}."
    else:
        failure_note = "Previous attempt needs a stricter static portrait retry."
    return " ".join(
        [
            failure_note,
            f"Regenerate set {set_id or '<set_id>'} from the same reference image.",
            "Use a locked static camera with same canvas, same crop, same full-body framing, same pose, same outfit, same proportions, and the same silhouette.",
            "The character must remain anchored in place from frame to frame.",
            "Animate only eyelids, tiny chest breathing, and slight hair-tip movement.",
            "Keep face, eyes, hairstyle, hands, feet, shoulders, hips, clothing details, palette, and transparent or plain background unchanged.",
            "Export a short conservative portrait clip suitable for PNG frame extraction.",
        ]
    )


def _provider_negative_prompt() -> str:
    return " ".join(
        [
            "No camera movement, zoom, pan, crop, reframing, body recomposition, pose change, gesture, head turn, mouth talking, expression exaggeration, scene change, background character, object insertion, text, subtitle, logo, watermark, blur, red edge halo, glow border, dramatic lighting, costume redesign, palette shift, or changed body proportions.",
        ]
    )


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _optional_string(value: object) -> str:
    return value if isinstance(value, str) and value else ""


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _nonnegative_float(value: object) -> float:
    if isinstance(value, int) and value >= 0:
        return float(value)
    return value if isinstance(value, float) and value >= 0 else 0.0


def _markdown_list(items: tuple[str, ...]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _write_text(path: str, text: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize whether portrait AI-video frames should be regenerated.")
    parser.add_argument("--workflow-report", required=True)
    parser.add_argument("--frame-qa-report", default="")
    parser.add_argument("--set-id", default="")
    parser.add_argument("--report", default="")
    parser.add_argument("--markdown", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    brief = build_portrait_video_regeneration_brief(
        workflow_report_path=args.workflow_report,
        frame_qa_report_path=args.frame_qa_report or None,
        set_id=args.set_id,
    )
    payload = json.dumps(brief.to_dict(), ensure_ascii=False, indent=2)
    _write_text(args.report, payload + "\n")
    _write_text(args.markdown, render_portrait_video_regeneration_markdown(brief))
    print(payload)
    return 0 if brief.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
