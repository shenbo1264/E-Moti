from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.character_registry import validate_character_pack_dir  # noqa: E402
from tools.art.pixel_pet_visual_qa import inspect_pixel_pet_visual_qa  # noqa: E402
from tools.pixel_pet_emote_mapping_check import inspect_pixel_pet_emote_mapping  # noqa: E402
from tools.pixel_pet_promotion_gate import REQUIRED_MANUAL_QA_CHECKS  # noqa: E402
from tools.validate_pixel_pet_pack import validate_pixel_pet_pack_dir  # noqa: E402


@dataclass(frozen=True, slots=True)
class PixelPetPromotionPreflightReport:
    ok: bool
    status: str
    deterministic_ok: bool
    manual_qa_status: str
    character_id: str
    path: str
    checks: tuple[dict[str, object], ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    next_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "deterministic_ok": self.deterministic_ok,
            "manual_qa_status": self.manual_qa_status,
            "character_id": self.character_id,
            "path": self.path,
            "checks": [dict(check) for check in self.checks],
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }


def inspect_pixel_pet_promotion_preflight(
    pack_dir: Path | str,
    *,
    manual_qa_path: Path | str | None = None,
) -> PixelPetPromotionPreflightReport:
    root = Path(pack_dir)
    checks: list[dict[str, object]] = []
    errors: list[str] = []
    warnings: list[str] = []

    pixel_report = validate_pixel_pet_pack_dir(root)
    checks.append(
        {
            "id": "pixel_pack_validation",
            "ok": pixel_report.ok,
            "status": "ready" if pixel_report.ok else "blocked",
            "errors": list(pixel_report.errors),
        }
    )
    errors.extend(f"pixel pack: {error}" for error in pixel_report.errors)

    runtime_report = validate_character_pack_dir(root, source="promotion_preflight")
    checks.append(
        {
            "id": "runtime_character_pack_validation",
            "ok": runtime_report.ok,
            "status": "ready" if runtime_report.ok else "blocked",
            "errors": list(runtime_report.errors),
        }
    )
    errors.extend(f"character pack: {error}" for error in runtime_report.errors)

    visual_report = inspect_pixel_pet_visual_qa(root / "spritesheet.png", root / "motion_manifest.json")
    visual_ok = visual_report.ok and not visual_report.warnings
    checks.append(
        {
            "id": "pixel_visual_qa",
            "ok": visual_ok,
            "status": visual_report.status,
            "errors": list(visual_report.errors),
            "warnings": list(visual_report.warnings),
        }
    )
    errors.extend(f"visual QA: {error}" for error in visual_report.errors)
    warnings.extend(f"visual QA: {warning}" for warning in visual_report.warnings)

    mapping_report = inspect_pixel_pet_emote_mapping(root)
    checks.append(
        {
            "id": "llm_emote_mapping",
            "ok": mapping_report.ok,
            "status": mapping_report.status,
            "errors": list(mapping_report.errors),
            "missing_motion_ids": list(mapping_report.missing_motion_ids),
        }
    )
    errors.extend(f"LLM emote mapping: {error}" for error in mapping_report.errors)
    if mapping_report.missing_motion_ids:
        errors.append("LLM emote mapping missing motions: " + ", ".join(mapping_report.missing_motion_ids))

    character_id = runtime_report.character_id or pixel_report.character_id or root.name
    if pixel_report.distribution_boundary != "official_candidate":
        errors.append("qa_report.distribution_boundary must be official_candidate before bundled promotion")

    manual_status, manual_errors = _manual_qa_status(Path(manual_qa_path) if manual_qa_path else None)
    errors.extend(manual_errors)
    checks.append(
        {
            "id": "manual_qa_decision",
            "ok": manual_status == "ready",
            "status": manual_status,
            "errors": list(manual_errors),
        }
    )

    deterministic_ok = (
        pixel_report.ok
        and runtime_report.ok
        and visual_ok
        and mapping_report.ok
        and pixel_report.distribution_boundary == "official_candidate"
    )
    status = _status(deterministic_ok=deterministic_ok, manual_qa_status=manual_status, errors=errors)
    return PixelPetPromotionPreflightReport(
        ok=status == "ready_for_promotion_gate",
        status=status,
        deterministic_ok=deterministic_ok,
        manual_qa_status=manual_status,
        character_id=character_id,
        path=str(root),
        checks=tuple(checks),
        errors=tuple(errors),
        warnings=tuple(warnings),
        next_actions=tuple(_next_actions(status=status, errors=errors, warnings=warnings)),
    )


def _manual_qa_status(path: Path | None) -> tuple[str, tuple[str, ...]]:
    if path is None:
        return "missing", ()
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return "invalid", (f"manual_qa json invalid: {exc}",)
    if not isinstance(payload, dict):
        return "invalid", ("manual_qa must be an object",)
    decision = payload.get("manual_decision")
    if not isinstance(decision, str) or not decision.startswith("promotion_gate_candidate"):
        errors.append("manual_qa.manual_decision must start with promotion_gate_candidate")
    if payload.get("runtime_manifest_updated") is not False:
        errors.append("manual_qa.runtime_manifest_updated must be false before promotion gate")
    checks = payload.get("deterministic_checks")
    if not isinstance(checks, dict):
        errors.append("manual_qa.deterministic_checks must be an object")
    else:
        for key in REQUIRED_MANUAL_QA_CHECKS:
            if checks.get(key) is not True:
                errors.append(f"manual_qa.deterministic_checks.{key} must be true")
    return ("invalid", tuple(errors)) if errors else ("ready", ())


def _status(*, deterministic_ok: bool, manual_qa_status: str, errors: list[str]) -> str:
    blocking_errors = [error for error in errors if not error.startswith("manual_qa.")]
    if blocking_errors or not deterministic_ok:
        return "blocked"
    if manual_qa_status != "ready":
        return "needs_manual_qa"
    return "ready_for_promotion_gate"


def _next_actions(*, status: str, errors: list[str], warnings: list[str]) -> list[str]:
    if status == "ready_for_promotion_gate":
        return ["run pixel_pet_promotion_gate.py with the approved manual QA file before copying bundled assets"]
    if status == "needs_manual_qa":
        return ["manual QA decision is required before bundled promotion"]
    actions = []
    if errors:
        actions.append("fix blocked deterministic checks before requesting promotion approval")
    if warnings:
        actions.append("review visual QA warnings before promotion")
    return actions


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic pixel-pet promotion preflight checks.")
    parser.add_argument("pack_dir")
    parser.add_argument("--manual-qa", default="", help="Optional manual QA JSON decision file.")
    parser.add_argument("--report", default="", help="Optional JSON report output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = inspect_pixel_pet_promotion_preflight(
        args.pack_dir,
        manual_qa_path=args.manual_qa or None,
    )
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
