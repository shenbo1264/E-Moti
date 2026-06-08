from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.character_registry import REQUIRED_PORTRAIT_EXPRESSIONS
from tools.art.portrait_candidate_visual_qa import inspect_portrait_candidate_visual_qa
from tools.art.validate_portrait_candidates import validate_portrait_candidate


ITERATION_DECISION = "approve edge cleanup and expression/blink generation for this candidate, or reject it and regenerate"
PROMOTION_REVIEW_DECISION = "run strict portrait promotion gate on a complete reviewed pack before manifest integration"


@dataclass(frozen=True, slots=True)
class PortraitCandidateDecisionBrief:
    ok: bool
    path: str
    status: str
    image_count: int
    decision_state: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    validation_errors: tuple[str, ...]
    next_human_decisions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "path": self.path,
            "status": self.status,
            "image_count": self.image_count,
            "decision_state": self.decision_state,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "validation_errors": list(self.validation_errors),
            "next_human_decisions": list(self.next_human_decisions),
        }


def build_portrait_candidate_decision_brief(candidate_manifest_path: Path | str) -> PortraitCandidateDecisionBrief:
    manifest = Path(candidate_manifest_path)
    validation = validate_portrait_candidate(manifest)
    payload = _read_manifest_object(manifest)
    blockers = _metadata_blockers(payload)
    blockers.extend(_expression_blockers(payload))

    visual_report = inspect_portrait_candidate_visual_qa(manifest)
    warnings = _visual_warnings(visual_report)
    validation_errors = tuple(validation.errors)
    ok = validation.ok and visual_report.ok and isinstance(payload, dict)
    if not ok:
        decision_state = "invalid_candidate"
    elif blockers or warnings:
        decision_state = "needs_iteration"
    else:
        decision_state = "ready_for_pack_promotion_review"

    return PortraitCandidateDecisionBrief(
        ok=ok,
        path=str(manifest),
        status=validation.status,
        image_count=validation.image_count,
        decision_state=decision_state,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        validation_errors=validation_errors,
        next_human_decisions=_next_human_decisions(decision_state),
    )


def _read_manifest_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _metadata_blockers(payload: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    if payload.get("status") != "approved":
        blockers.append("candidate status is not approved")
    if payload.get("approval_required") is not False:
        blockers.append("approval_required must be false before promotion")
    if payload.get("runtime_manifest_safe") is not True:
        blockers.append("runtime_manifest_safe must be true before promotion")
    return blockers


def _expression_blockers(payload: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    expressions = payload.get("expressions")
    if not isinstance(expressions, dict):
        return ["expressions must be an object"]
    for expression in REQUIRED_PORTRAIT_EXPRESSIONS:
        if expression not in expressions:
            blockers.append(f"missing required expression: {expression}")
    neutral = expressions.get("neutral")
    if not isinstance(neutral, dict) or "blink_half" not in neutral or "blink_closed" not in neutral:
        blockers.append("neutral expression requires blink_half and blink_closed frames")
    return blockers


def _visual_warnings(visual_report: object) -> list[str]:
    warnings: list[str] = []
    if not getattr(visual_report, "ok", False):
        return warnings
    for image_report in getattr(visual_report, "images", ()):
        label = image_report.get("label", "")
        for warning in image_report.get("warnings", []):
            warnings.append(f"{label}: {warning}")
    return warnings


def _next_human_decisions(decision_state: str) -> tuple[str, ...]:
    if decision_state == "ready_for_pack_promotion_review":
        return (PROMOTION_REVIEW_DECISION,)
    return (ITERATION_DECISION,)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize portrait candidate readiness for human QA decisions.")
    parser.add_argument("candidate_manifest")
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    brief = build_portrait_candidate_decision_brief(args.candidate_manifest)
    payload = json.dumps(brief.to_dict(), ensure_ascii=False, indent=2)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if brief.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
