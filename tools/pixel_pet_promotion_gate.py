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

from guanghe_companion.character_registry import (  # noqa: E402
    summarize_character_pack_dir,
    validate_character_pack_dir,
)
from tools.validate_pixel_pet_pack import validate_pixel_pet_pack_dir  # noqa: E402


REQUIRED_MANUAL_QA_CHECKS = (
    "final_validation_ok",
    "hatch_review_ok",
    "pixel_pack_validation_ok",
    "runtime_import_smoke_ok",
)


@dataclass(frozen=True, slots=True)
class PixelPetPromotionReport:
    ok: bool
    character_id: str
    path: str
    distribution_boundary: str
    manual_decision: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "character_id": self.character_id,
            "path": self.path,
            "distribution_boundary": self.distribution_boundary,
            "manual_decision": self.manual_decision,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def validate_pixel_pet_promotion_candidate(
    pack_dir: Path | str,
    *,
    manual_qa_path: Path | str,
) -> PixelPetPromotionReport:
    root = Path(pack_dir)
    errors: list[str] = []
    warnings: list[str] = []

    pixel_report = validate_pixel_pet_pack_dir(root)
    errors.extend(f"pixel pack: {error}" for error in pixel_report.errors)

    runtime_report = validate_character_pack_dir(root, source="promotion_candidate")
    errors.extend(f"character pack: {error}" for error in runtime_report.errors)

    character_id = runtime_report.character_id or pixel_report.character_id
    if "_ugc_" in character_id:
        errors.append("UGC pixel-pet packs cannot pass official promotion gate")
    if pixel_report.distribution_boundary != "official_candidate":
        errors.append("qa_report.distribution_boundary must be official_candidate for promotion gate")

    summary = summarize_character_pack_dir(root, source="promotion_candidate")
    character_boundary = summary.distribution_boundary if summary is not None else ""
    if character_boundary != "shareable_after_review":
        errors.append("character.json.distribution_boundary must be shareable_after_review for promotion gate")

    qa_payload = _read_json_object(Path(manual_qa_path), errors, label="manual_qa")
    manual_decision = _validate_manual_qa(qa_payload, errors)
    _validate_runtime_manifest_boundary(root / "qa_report.json", errors)

    if summary is not None and not summary.provenance_paths:
        warnings.append("promotion candidate has no registered provenance file in character summary")

    return PixelPetPromotionReport(
        ok=not errors,
        character_id=character_id,
        path=str(root),
        distribution_boundary=pixel_report.distribution_boundary,
        manual_decision=manual_decision,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _read_json_object(path: Path, errors: list[str], *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} json invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be an object")
        return {}
    return payload


def _validate_manual_qa(payload: dict[str, object], errors: list[str]) -> str:
    decision = payload.get("manual_decision")
    manual_decision = decision if isinstance(decision, str) else ""
    if not manual_decision.startswith("promotion_gate_candidate"):
        errors.append("manual_qa.manual_decision must start with promotion_gate_candidate")
    if payload.get("runtime_manifest_updated") is not False:
        errors.append("manual_qa.runtime_manifest_updated must be false before promotion gate")
    checks = payload.get("deterministic_checks")
    if not isinstance(checks, dict):
        errors.append("manual_qa.deterministic_checks must be an object")
        return manual_decision
    for key in REQUIRED_MANUAL_QA_CHECKS:
        if checks.get(key) is not True:
            errors.append(f"manual_qa.deterministic_checks.{key} must be true")
    return manual_decision


def _validate_runtime_manifest_boundary(path: Path, errors: list[str]) -> None:
    payload = _read_json_object(path, errors, label="qa_report.json")
    if not payload:
        return
    value = payload.get("runtime_manifest_updated")
    if value is not False and value is not None:
        errors.append("qa_report.runtime_manifest_updated must be false before promotion gate")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a pixel-pet pack before promotion-gate packaging.")
    parser.add_argument("pack_dir")
    parser.add_argument("--manual-qa", required=True, help="Manual QA JSON evidence path.")
    parser.add_argument("--report", default="", help="Optional JSON report output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = validate_pixel_pet_promotion_candidate(
        Path(args.pack_dir),
        manual_qa_path=Path(args.manual_qa),
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
