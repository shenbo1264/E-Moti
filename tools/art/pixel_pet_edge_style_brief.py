from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


PROMPT_LOCKS = (
    "Do not run automatic transparent edge erasing on the current bundled spritesheet.",
    "Use the visual QA overlay to decide whether the marked pixels are outline style or unwanted halo.",
    "Keep the active route hatch-pet-style pixel-pet sequences, not VN portrait, AI-video, or Live2D.",
    "For the base job, generate exactly one standalone base reference sprite; do not generate a sprite sheet, row strip, atlas, repeated copies, or animation frames.",
    "Keep Xingxi as the only open-source distributable candidate unless rights are separately cleared.",
    "Do not update runtime manifests or replace the default pack until all acceptance gates pass.",
)

ACCEPTANCE_GATES = (
    "python tools\\art\\pixel_pet_visual_qa.py assets\\companion\\xingxi_pixel_pet\\spritesheet.png --motion-manifest assets\\companion\\xingxi_pixel_pet\\motion_manifest.json --fail-on-warnings",
    "python tools\\validate_character_pack.py assets\\companion\\xingxi_pixel_pet",
    "python tools\\validate_pixel_pet_pack.py assets\\companion\\xingxi_pixel_pet --report artifacts\\character-library-qa\\xingxi-pixel-pet-pack-validation-after-edge-style.json",
    "python tools\\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\\character-library-qa\\xingxi-pixel-pet-character-library-qa-after-edge-style.json --screenshot-dir artifacts\\character-library-qa\\edge-style-screenshots",
    "python -m pytest tests\\test_app.py tests\\test_desktop_pet_smoke.py -q",
    "python -m pytest",
)


@dataclass(frozen=True, slots=True)
class PixelPetEdgeStyleBrief:
    ok: bool
    visual_qa_report_path: str
    character_id: str
    character_name: str
    spritesheet_path: str
    motion_manifest_path: str
    preview_path: str
    decision_state: str
    default_promotion_allowed: bool
    edge_pixel_count: int
    suspicious_edge_halo_pixel_count: int
    suspicious_edge_halo_ratio: float
    blockers: tuple[str, ...]
    next_actions: tuple[str, ...]
    prompt_locks: tuple[str, ...]
    regeneration_prompt: str
    negative_prompt: str
    suggested_commands: tuple[str, ...]
    acceptance_gates: tuple[str, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "visual_qa_report_path": self.visual_qa_report_path,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "spritesheet_path": self.spritesheet_path,
            "motion_manifest_path": self.motion_manifest_path,
            "preview_path": self.preview_path,
            "decision_state": self.decision_state,
            "default_promotion_allowed": self.default_promotion_allowed,
            "edge_pixel_count": self.edge_pixel_count,
            "suspicious_edge_halo_pixel_count": self.suspicious_edge_halo_pixel_count,
            "suspicious_edge_halo_ratio": self.suspicious_edge_halo_ratio,
            "blockers": list(self.blockers),
            "next_actions": list(self.next_actions),
            "prompt_locks": list(self.prompt_locks),
            "regeneration_prompt": self.regeneration_prompt,
            "negative_prompt": self.negative_prompt,
            "suggested_commands": list(self.suggested_commands),
            "acceptance_gates": list(self.acceptance_gates),
            "errors": list(self.errors),
        }


def build_pixel_pet_edge_style_brief(
    *,
    visual_qa_report_path: Path | str,
    character_id: str,
    character_name: str,
) -> PixelPetEdgeStyleBrief:
    report_path = Path(visual_qa_report_path)
    report = _load_json_object(report_path)
    errors: list[str] = []
    if not report:
        errors.append("visual QA report must be a JSON object")

    visual_errors = _string_list(report.get("errors"))
    warnings = _string_list(report.get("warnings"))
    blockers = _blockers(visual_errors, warnings)
    decision_state = _decision_state(errors, visual_errors, warnings, _optional_string(report.get("status")))
    next_actions = _next_actions(decision_state)
    brief = PixelPetEdgeStyleBrief(
        ok=not errors,
        visual_qa_report_path=str(report_path),
        character_id=character_id,
        character_name=character_name,
        spritesheet_path=_optional_string(report.get("spritesheet_path")),
        motion_manifest_path=_optional_string(report.get("motion_manifest_path")),
        preview_path=_optional_string(report.get("preview_path")),
        decision_state="invalid_report" if errors else decision_state,
        default_promotion_allowed=False,
        edge_pixel_count=_nonnegative_int(report.get("edge_pixel_count")),
        suspicious_edge_halo_pixel_count=_nonnegative_int(report.get("suspicious_edge_halo_pixel_count")),
        suspicious_edge_halo_ratio=_nonnegative_float(report.get("suspicious_edge_halo_ratio")),
        blockers=tuple(blockers),
        next_actions=tuple(next_actions),
        prompt_locks=PROMPT_LOCKS,
        regeneration_prompt=_regeneration_prompt(character_name=character_name, character_id=character_id),
        negative_prompt=_negative_prompt(),
        suggested_commands=_suggested_commands(character_id),
        acceptance_gates=ACCEPTANCE_GATES,
        errors=tuple(errors),
    )
    return brief


def render_pixel_pet_edge_style_markdown(brief: PixelPetEdgeStyleBrief) -> str:
    lines = [
        "# Pixel Pet Edge Style Decision Brief",
        "",
        f"- Character: `{brief.character_id}` / `{brief.character_name}`",
        f"- Visual QA report: `{brief.visual_qa_report_path}`",
        f"- Spritesheet: `{brief.spritesheet_path}`",
        f"- Motion manifest: `{brief.motion_manifest_path}`",
        f"- Preview overlay: `{brief.preview_path}`",
        f"- Decision state: `{brief.decision_state}`",
        f"- Default promotion allowed: `{'yes' if brief.default_promotion_allowed else 'no'}`",
        f"- Edge pixels: `{brief.edge_pixel_count}`",
        f"- Suspicious edge halo pixels: `{brief.suspicious_edge_halo_pixel_count}`",
        f"- Suspicious edge halo ratio: `{brief.suspicious_edge_halo_ratio}`",
        "",
        "## Blockers",
        *_markdown_list(brief.blockers),
        "",
        "## Next Actions",
        *_markdown_list(brief.next_actions),
        "",
        "## Prompt Locks",
        *_markdown_list(brief.prompt_locks),
        "",
        "## Regeneration Prompt",
        "",
        brief.regeneration_prompt,
        "",
        "## Negative Prompt",
        "",
        brief.negative_prompt,
        "",
        "## Suggested Commands",
        *_markdown_list(brief.suggested_commands),
        "",
        "## Acceptance Gates",
        *_markdown_list(brief.acceptance_gates),
        "",
        "## Errors",
        *_markdown_list(brief.errors),
        "",
    ]
    return "\n".join(lines)


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _blockers(visual_errors: list[str], warnings: list[str]) -> list[str]:
    blockers: list[str] = []
    blockers.extend(visual_errors)
    if "suspicious_edge_halo_risk" in warnings:
        blockers.append("suspicious_edge_halo_risk")
    return _dedupe(blockers)


def _decision_state(
    errors: list[str],
    visual_errors: list[str],
    warnings: list[str],
    status: str,
) -> str:
    if errors or visual_errors:
        return "repair_visual_qa_report"
    if "suspicious_edge_halo_risk" in warnings:
        return "regenerate_or_redraw_edge_style"
    if status == "ready":
        return "eligible_for_manual_default_review"
    return "inspect_manually"


def _next_actions(decision_state: str) -> list[str]:
    if decision_state == "regenerate_or_redraw_edge_style":
        return [
            "use hatch-pet image generation or manual redraw to create an edge-style candidate with no red/purple outer halo",
            "keep the current bundled spritesheet unchanged until the replacement passes visual QA",
            "rerun the acceptance gates before any default-promotion package",
        ]
    if decision_state == "eligible_for_manual_default_review":
        return [
            "run real desktop manual QA before default promotion",
            "keep original_oc as default until a separate default-promotion package lands",
        ]
    if decision_state == "repair_visual_qa_report":
        return ["repair the visual QA report input before deciding on art promotion"]
    return ["inspect the overlay and decide whether to regenerate, redraw, or keep as candidate only"]


def _regeneration_prompt(*, character_name: str, character_id: str) -> str:
    display_name = character_name or character_id
    return " ".join(
        [
            f"Create exactly ONE standalone base reference sprite for a hatch-pet-style pixel-pet sequence candidate for {display_name}.",
            "This first output is NOT a sprite sheet, NOT a row strip, NOT an atlas, NOT an animation, and NOT multiple frames.",
            "Draw one single full-body character only, centered on a flat chroma-key canvas with generous empty margin. Do not repeat the character.",
            "Preserve Xingxi's blue-purple hair mass, tiny chibi proportions, face, outfit silhouette, star hair accessory, white-and-blue jacket, and compact desktop-pet readability.",
            "Use chunky pixel-adjacent shapes, hard 1-2 px dark navy outlines, flat cel shading, clean transparent or removable chroma-key background, and stable 192x208 frame-safe composition.",
            "The important edge-style repair is no red or purple outer halo, no magenta glow, no bright rim light, no soft aura, no color fringing outside the sprite, and no detached outline pixels.",
            "Blue-purple may remain inside the hair and shadow shapes, but the outer silhouette must read as a clean dark outline rather than a colored glow.",
            "Generate or redraw one canonical base first, then one animation row at a time. Keep identity locked across idle, running, running-left, waving, jumping, failed, waiting, running, and review rows.",
        ]
    )


def _negative_prompt() -> str:
    return " ".join(
        [
            "No sprite sheet, row strip, atlas, repeated character copies, animation frames, red edge halo, purple outer glow, magenta rim light, chromatic aberration, soft aura, drop shadow, cast shadow, blur, antialias haze, glossy illustration rendering, VN portrait proportions, Live2D rig sheet, AI-video motion smear, floating effects, detached particles, text, UI marks, watermarks, checkerboard background, or white/black opaque background.",
        ]
    )


def _suggested_commands(character_id: str) -> tuple[str, ...]:
    character = character_id or "xingxi_pixel_pet"
    return (
        "python %CODEX_HOME%\\skills\\hatch-pet\\scripts\\prepare_pet_run.py --pet-name Xingxi --description \"Original Xingxi pixel-pet edge-style repair candidate\" --output-dir artifacts\\pixel-pet-sequence-drafts\\xingxi_pixel_pet_edge_style_v2 --pet-notes \"original Xingxi desktop companion\" --style-notes \"base job must create exactly one standalone base reference sprite; no sprite sheet; no row strip; no atlas; no repeated copies; no red or purple outer halo; clean dark pixel outline; preserve blue-purple hair inside the sprite\" --force",
        f"python tools\\art\\pixel_pet_visual_qa.py assets\\companion\\{character}\\spritesheet.png --motion-manifest assets\\companion\\{character}\\motion_manifest.json --report artifacts\\character-library-qa\\{character}-visual-qa-after-edge-style.json --preview artifacts\\character-library-qa\\{character}-visual-qa-after-edge-style-preview.png",
        f"python tools\\art\\pixel_pet_visual_qa.py assets\\companion\\{character}\\spritesheet.png --motion-manifest assets\\companion\\{character}\\motion_manifest.json --fail-on-warnings",
    )


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


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


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
    parser = argparse.ArgumentParser(description="Build a pixel-pet edge-style regeneration decision brief.")
    parser.add_argument("--visual-qa-report", required=True)
    parser.add_argument("--character-id", default="xingxi_pixel_pet")
    parser.add_argument("--character-name", default="Xingxi")
    parser.add_argument("--report", default="")
    parser.add_argument("--markdown", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    brief = build_pixel_pet_edge_style_brief(
        visual_qa_report_path=args.visual_qa_report,
        character_id=args.character_id,
        character_name=args.character_name,
    )
    payload = json.dumps(brief.to_dict(), ensure_ascii=False, indent=2)
    _write_text(args.report, payload + "\n")
    _write_text(args.markdown, render_pixel_pet_edge_style_markdown(brief))
    print(payload)
    return 0 if brief.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
