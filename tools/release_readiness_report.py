from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.review_character_pack_status import review_character_pack_status
from tools.review_llm_smoke_report import review_llm_smoke_report
from tools.validate_windows_build import DEFAULT_APP_DIR, DEFAULT_INSTALLER, validate_windows_build


DEFAULT_CHARACTER_PACK = REPO_ROOT / "assets" / "companion" / "original_oc"


def build_release_readiness_report(
    *,
    character_pack: Path | str = DEFAULT_CHARACTER_PACK,
    app_dir: Path | str = DEFAULT_APP_DIR,
    installer_path: Path | str | None = DEFAULT_INSTALLER,
    llm_reports: Iterable[Path | str] = (),
    portrait_workflow_reports: Iterable[Path | str] = (),
) -> dict[str, object]:
    source_check = _source_character_pack_check(Path(character_pack))
    build_check = _windows_build_check(Path(app_dir), Path(installer_path) if installer_path is not None else None)
    checks = [source_check, build_check]
    checks.extend(_llm_report_check(Path(report_path)) for report_path in llm_reports)
    checks.extend(_portrait_workflow_report_check(Path(report_path)) for report_path in portrait_workflow_reports)
    ok = all(check["ok"] is True for check in checks)
    return {
        "ok": ok,
        "status": "ready" if ok else "needs_attention",
        "checks": checks,
        "next_actions": _next_actions(checks),
    }


def render_release_readiness_markdown(payload: dict[str, object]) -> str:
    checks = _list_of_mappings(payload.get("checks"))
    lines = [
        "# E-Moti Release Readiness",
        "",
        f"- Status: `{payload.get('status', 'unknown')}`",
        f"- Checks: `{len(checks)}`",
    ]
    next_actions = _string_list(payload.get("next_actions"))
    if next_actions:
        lines.extend(["", "## Next Actions", ""])
        lines.extend(f"- {item}" for item in next_actions)
    lines.extend(["", "## Checks", ""])
    for check in checks:
        lines.extend(
            [
                f"### {check.get('label', check.get('id', 'unknown'))}",
                "",
                f"- Status: `{check.get('status', 'unknown')}`",
                f"- OK: `{'yes' if check.get('ok') is True else 'no'}`",
                f"- Path: `{check.get('path', '')}`",
            ]
        )
        errors = _string_list(check.get("errors"))
        if errors:
            lines.append("- Errors: `" + "; ".join(errors) + "`")
        warnings = _string_list(check.get("warnings"))
        if warnings:
            lines.append("- Warnings: `" + "; ".join(warnings) + "`")
        commands = _string_list(check.get("suggested_commands"))
        if commands:
            lines.append("- Suggested commands: `" + "`; `".join(commands) + "`")
        lines.append("")
    return "\n".join(lines)


def _source_character_pack_check(character_pack: Path) -> dict[str, object]:
    report = review_character_pack_status(character_pack)
    return {
        "id": "source_character_pack",
        "label": "Source Character Pack",
        "ok": report.get("ok") is True,
        "status": str(report.get("status") or "unknown"),
        "path": str(character_pack),
        "character_id": str(report.get("character_id") or ""),
        "errors": _string_list(report.get("errors")),
        "warnings": _string_list(report.get("warnings")),
        "next_actions": _string_list(report.get("next_actions")),
    }


def _windows_build_check(app_dir: Path, installer_path: Path | None) -> dict[str, object]:
    report = validate_windows_build(app_dir=app_dir, installer_path=installer_path)
    return {
        "id": "windows_build",
        "label": "Windows Frozen Build",
        "ok": report.ok,
        "status": "ready" if report.ok else "needs_attention",
        "path": report.app_dir,
        "app_exe": report.app_exe,
        "installer_path": report.installer_path,
        "character_id": report.character_id,
        "errors": list(report.errors),
        "warnings": [],
        "next_actions": [] if report.ok else ["rebuild Windows app and installer after fixing release artifacts"],
    }


def _llm_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "llm_report",
            "label": "LLM Smoke Report",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "provider": "",
            "model": "",
            "report_type": "invalid",
            "errors": ["LLM smoke report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review LLM smoke report before release"],
        }
    review = review_llm_smoke_report(payload)
    return {
        "id": "llm_report",
        "label": "LLM Smoke Report",
        "ok": review.ok,
        "status": review.status,
        "path": str(report_path),
        "provider": review.provider,
        "model": review.model,
        "report_type": review.report_type,
        "errors": [f"{issue.kind}: {issue.message}" for issue in review.issues],
        "warnings": [],
        "next_actions": [] if review.ok else ["review LLM smoke report before release"],
    }


def _portrait_workflow_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_video_workflow",
            "label": "Portrait AI Video Workflow",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "pack_count": 0,
            "ready_count": 0,
            "attention_reasons": [],
            "errors": ["portrait workflow report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review portrait AI-video workflow report before release"],
        }
    items = _list_of_mappings(payload.get("items"))
    errors = _string_list(payload.get("errors"))
    for item in items:
        errors.extend(_string_list(item.get("errors")))
    attention_reasons = _dedupe(
        reason
        for item in items
        for reason in _string_list(item.get("attention_reasons"))
    )
    suggested_commands = _dedupe(
        command
        for item in items
        for command in _string_list(item.get("suggested_commands"))
    )
    ok = payload.get("ok") is True
    return {
        "id": "portrait_video_workflow",
        "label": "Portrait AI Video Workflow",
        "ok": ok,
        "status": "ready" if ok else "needs_attention",
        "path": str(report_path),
        "pack_count": _nonnegative_int(payload.get("pack_count")),
        "ready_count": _nonnegative_int(payload.get("ready_count")),
        "attention_reasons": attention_reasons,
        "suggested_commands": suggested_commands,
        "errors": _dedupe(errors),
        "warnings": [],
        "next_actions": [] if ok else ["resolve portrait AI-video workflow blockers before promoting motion assets"],
    }


def _load_json_object(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _next_actions(checks: Iterable[dict[str, object]]) -> list[str]:
    actions: list[str] = []
    for check in checks:
        if check.get("ok") is True:
            continue
        actions.extend(_string_list(check.get("next_actions")))
    return _dedupe(actions)


def _dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _list_of_mappings(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _write_text(path: str, text: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an E-Moti release readiness report from existing validators.")
    parser.add_argument("--character-pack", default=str(DEFAULT_CHARACTER_PACK))
    parser.add_argument("--app-dir", default=str(DEFAULT_APP_DIR))
    parser.add_argument("--installer", default=str(DEFAULT_INSTALLER))
    parser.add_argument("--skip-installer", action="store_true")
    parser.add_argument(
        "--llm-report",
        action="append",
        default=[],
        help="Optional LLM dialogue smoke or expression cue probe JSON report to include.",
    )
    parser.add_argument(
        "--portrait-workflow-report",
        action="append",
        default=[],
        help="Optional portrait AI-video workflow JSON report to include.",
    )
    parser.add_argument("--json", default="", help="Optional JSON output path.")
    parser.add_argument("--markdown", default="", help="Optional Markdown output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_release_readiness_report(
        character_pack=Path(args.character_pack),
        app_dir=Path(args.app_dir),
        installer_path=None if args.skip_installer else Path(args.installer),
        llm_reports=[Path(item) for item in args.llm_report],
        portrait_workflow_reports=[Path(item) for item in args.portrait_workflow_report],
    )
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    _write_text(args.json, text + "\n")
    _write_text(args.markdown, render_release_readiness_markdown(payload))
    print(text)
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
