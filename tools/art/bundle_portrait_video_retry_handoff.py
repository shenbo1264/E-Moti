from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OUTPUT_DIR = Path("artifacts") / "portrait-video-retry-handoff"


@dataclass(frozen=True, slots=True)
class PortraitVideoRetryHandoffReport:
    ok: bool
    set_id: str
    regeneration_brief_path: str
    reference_image_path: str
    output_dir: str
    zip_path: str
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "set_id": self.set_id,
            "regeneration_brief_path": self.regeneration_brief_path,
            "reference_image_path": self.reference_image_path,
            "output_dir": self.output_dir,
            "zip_path": self.zip_path,
            "errors": list(self.errors),
        }


def bundle_portrait_video_retry_handoff(
    *,
    regeneration_brief_path: Path | str,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    report_path: Path | str | None = None,
) -> PortraitVideoRetryHandoffReport:
    brief_path = Path(regeneration_brief_path)
    output = Path(output_dir)
    brief = _load_json_object(brief_path)
    errors = _brief_errors(brief)
    set_id = _optional_string(brief.get("set_id"))
    reference_path = Path(_optional_string(brief.get("reference_image_path")))
    if reference_path and not reference_path.is_file():
        errors.append("reference_image_path must point to an existing file")
    zip_path = output / f"{set_id or 'portrait-video'}-retry.zip"
    if errors:
        report = PortraitVideoRetryHandoffReport(
            ok=False,
            set_id=set_id,
            regeneration_brief_path=str(brief_path),
            reference_image_path=str(reference_path) if str(reference_path) != "." else "",
            output_dir=str(output),
            zip_path="",
            errors=tuple(errors),
        )
        _write_report(report_path, report)
        return report

    output.mkdir(parents=True, exist_ok=True)
    reference_arcname = f"reference/{reference_path.name}"
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(reference_path, arcname=reference_arcname)
        archive.writestr("retry_prompt.txt", _optional_string(brief.get("retry_prompt")))
        archive.writestr("negative_prompt.txt", _optional_string(brief.get("negative_prompt")))
        archive.writestr("regeneration_brief.json", json.dumps(brief, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("source_pack_reference.txt", _source_pack_reference_text(brief))
        archive.writestr(
            "AI_VIDEO_RETRY_README.md",
            _readme_text(set_id=set_id, reference_arcname=reference_arcname, brief=brief),
        )
    report = PortraitVideoRetryHandoffReport(
        ok=True,
        set_id=set_id,
        regeneration_brief_path=str(brief_path),
        reference_image_path=str(reference_path),
        output_dir=str(output),
        zip_path=str(zip_path),
    )
    _write_report(report_path, report)
    return report


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _brief_errors(brief: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if not brief:
        return ["regeneration brief must be a JSON object"]
    if not _optional_string(brief.get("set_id")):
        errors.append("set_id must be present")
    if not _optional_string(brief.get("reference_image_path")):
        errors.append("reference_image_path must be present")
    if not _optional_string(brief.get("retry_prompt")):
        errors.append("retry_prompt must be present")
    if not _optional_string(brief.get("negative_prompt")):
        errors.append("negative_prompt must be present")
    return errors


def _readme_text(*, set_id: str, reference_arcname: str, brief: dict[str, object]) -> str:
    return "\n".join(
        [
            "# AI Video Retry Handoff",
            "",
            f"Set id: `{set_id}`",
            "",
            f"Upload `{reference_arcname}` to the selected image-to-video provider.",
            "Paste `retry_prompt.txt` as the positive prompt and `negative_prompt.txt` as the negative prompt.",
            "",
            "After generation:",
            "",
            "- Download the raw video into the matching source pack `video/` folder.",
            "- Export sequential PNG frames into the matching source pack `frames/` folder.",
            "- Rerun frame preflight, frame visual QA, and release readiness before extracting motion frames.",
            "",
            "Current blockers:",
            "",
            *_markdown_list(_string_list(brief.get("blockers"))),
            "",
            "Do not commit generated videos or rejected frames unless they are explicitly approved release assets.",
            "",
        ]
    )


def _source_pack_reference_text(brief: dict[str, object]) -> str:
    return "\n".join(
        [
            f"set_id={_optional_string(brief.get('set_id'))}",
            f"source_pack_dir={_optional_string(brief.get('source_pack_dir'))}",
            f"reference_image_path={_optional_string(brief.get('reference_image_path'))}",
            f"workflow_report_path={_optional_string(brief.get('workflow_report_path'))}",
            f"frame_qa_report_path={_optional_string(brief.get('frame_qa_report_path'))}",
            "",
        ]
    )


def _markdown_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _optional_string(value: object) -> str:
    return value if isinstance(value, str) and value else ""


def _write_report(report_path: Path | str | None, report: PortraitVideoRetryHandoffReport) -> None:
    if not report_path:
        return
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bundle a portrait AI-video retry handoff zip from a regeneration brief.")
    parser.add_argument("regeneration_brief")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = bundle_portrait_video_retry_handoff(
        regeneration_brief_path=args.regeneration_brief,
        output_dir=args.output_dir,
        report_path=args.report or None,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
