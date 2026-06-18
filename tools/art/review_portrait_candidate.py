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

from tools.art.portrait_candidate_decision_brief import (
    build_portrait_candidate_decision_brief,
    render_portrait_candidate_decision_markdown,
)
from tools.art.portrait_candidate_visual_qa import build_portrait_candidate_visual_qa
from tools.art.validate_portrait_candidates import validate_portrait_candidate


@dataclass(frozen=True, slots=True)
class PortraitCandidateReviewReport:
    ok: bool
    candidate_manifest: str
    output_dir: str
    candidate_status: str
    decision_state: str
    validation_report: dict[str, object]
    visual_qa_report: dict[str, object]
    decision_brief: dict[str, object]
    review_outputs: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "candidate_manifest": self.candidate_manifest,
            "output_dir": self.output_dir,
            "candidate_status": self.candidate_status,
            "decision_state": self.decision_state,
            "validation_report": self.validation_report,
            "visual_qa_report": self.visual_qa_report,
            "decision_brief": self.decision_brief,
            "review_outputs": self.review_outputs,
        }


def review_portrait_candidate(
    candidate_manifest_path: Path | str,
    *,
    output_dir: Path | str | None = None,
    report_path: Path | str | None = None,
) -> PortraitCandidateReviewReport:
    manifest = Path(candidate_manifest_path)
    output = Path(output_dir) if output_dir is not None else manifest.parent / "review"
    output.mkdir(parents=True, exist_ok=True)

    contact_sheet = output / "portrait-contact-sheet.png"
    visual_preview = output / "portrait-visual-qa.png"
    visual_report_path = output / "portrait-visual-qa-report.json"
    decision_json = output / "portrait-decision-brief.json"
    decision_markdown = output / "portrait-decision-brief.md"

    validation = validate_portrait_candidate(manifest, contact_sheet_path=contact_sheet)
    visual = build_portrait_candidate_visual_qa(
        manifest,
        preview_path=visual_preview,
        report_path=visual_report_path,
    )
    decision = build_portrait_candidate_decision_brief(manifest)
    decision_payload = decision.to_dict()
    decision_json.write_text(json.dumps(decision_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    decision_markdown.write_text(render_portrait_candidate_decision_markdown(decision), encoding="utf-8")

    review_outputs = {
        "contact_sheet": str(contact_sheet),
        "visual_preview": str(visual_preview),
        "visual_report": str(visual_report_path),
        "decision_json": str(decision_json),
        "decision_markdown": str(decision_markdown),
    }
    report = PortraitCandidateReviewReport(
        ok=validation.ok and visual.ok and decision.ok,
        candidate_manifest=str(manifest),
        output_dir=str(output),
        candidate_status=validation.status,
        decision_state=decision.decision_state,
        validation_report=validation.to_dict(),
        visual_qa_report=visual.to_dict(),
        decision_brief=decision_payload,
        review_outputs=review_outputs,
    )
    if report_path is not None:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all local portrait candidate review checks and write review artifacts.")
    parser.add_argument("candidate_manifest")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = review_portrait_candidate(
        args.candidate_manifest,
        output_dir=args.output_dir or None,
        report_path=args.report or None,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
