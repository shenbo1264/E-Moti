from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass(frozen=True, slots=True)
class HatchPetImagegenReadinessReport:
    ok: bool
    status: str
    run_dir: str
    total_job_count: int
    complete_job_count: int
    ready_job_count: int
    blocked_job_count: int
    ready_job_ids: tuple[str, ...]
    blocked_job_ids: tuple[str, ...]
    openai_api_key_present: bool
    raw_error_codes: tuple[str, ...]
    blockers: tuple[str, ...]
    next_actions: tuple[str, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "run_dir": self.run_dir,
            "total_job_count": self.total_job_count,
            "complete_job_count": self.complete_job_count,
            "ready_job_count": self.ready_job_count,
            "blocked_job_count": self.blocked_job_count,
            "ready_job_ids": list(self.ready_job_ids),
            "blocked_job_ids": list(self.blocked_job_ids),
            "openai_api_key_present": self.openai_api_key_present,
            "raw_error_codes": list(self.raw_error_codes),
            "blockers": list(self.blockers),
            "next_actions": list(self.next_actions),
            "errors": list(self.errors),
        }


def inspect_hatch_pet_imagegen_readiness(
    run_dir: Path | str,
    *,
    openai_api_key_present: bool | None = None,
) -> HatchPetImagegenReadinessReport:
    root = Path(run_dir)
    errors: list[str] = []
    manifest = _load_manifest(root, errors)
    jobs = _jobs(manifest)
    complete_ids = _complete_ids(jobs)
    pending = [job for job in jobs if job.get("status", "pending") != "complete"]
    ready = [job for job in pending if not _missing_dependencies(job, complete_ids)]
    blocked = [job for job in pending if _missing_dependencies(job, complete_ids)]
    raw_error_codes = _raw_error_codes(root)
    api_key_present = (
        bool(os.environ.get("OPENAI_API_KEY"))
        if openai_api_key_present is None
        else openai_api_key_present
    )
    blockers = _blockers(errors, raw_error_codes, api_key_present, len(ready), len(jobs))
    status = _status(errors, raw_error_codes, api_key_present, len(ready), len(blocked), len(jobs), len(complete_ids))
    return HatchPetImagegenReadinessReport(
        ok=not blockers and not errors,
        status=status,
        run_dir=str(root),
        total_job_count=len(jobs),
        complete_job_count=len(complete_ids),
        ready_job_count=len(ready),
        blocked_job_count=len(blocked),
        ready_job_ids=tuple(_job_id(job) for job in ready),
        blocked_job_ids=tuple(_job_id(job) for job in blocked),
        openai_api_key_present=api_key_present,
        raw_error_codes=tuple(raw_error_codes),
        blockers=tuple(blockers),
        next_actions=tuple(_next_actions(status)),
        errors=tuple(errors),
    )


def render_hatch_pet_imagegen_readiness_markdown(report: HatchPetImagegenReadinessReport) -> str:
    lines = [
        "# Hatch Pet Imagegen Readiness",
        "",
        f"- Run dir: `{report.run_dir}`",
        f"- Status: `{report.status}`",
        f"- OK: `{'yes' if report.ok else 'no'}`",
        f"- Jobs: `{report.complete_job_count}/{report.total_job_count}` complete",
        f"- Ready jobs: `{', '.join(report.ready_job_ids) or 'none'}`",
        f"- Blocked jobs: `{', '.join(report.blocked_job_ids) or 'none'}`",
        f"- OPENAI_API_KEY present: `{'yes' if report.openai_api_key_present else 'no'}`",
        f"- Raw error codes: `{', '.join(report.raw_error_codes) or 'none'}`",
        "",
        "## Blockers",
        *_markdown_list(report.blockers),
        "",
        "## Next Actions",
        *_markdown_list(report.next_actions),
        "",
        "## Errors",
        *_markdown_list(report.errors),
        "",
    ]
    return "\n".join(lines)


def _load_manifest(root: Path, errors: list[str]) -> dict[str, object]:
    path = root / "imagegen-jobs.json"
    if not path.is_file():
        errors.append(f"imagegen-jobs.json not found: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"imagegen-jobs.json invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("imagegen-jobs.json must be an object")
        return {}
    return payload


def _jobs(manifest: dict[str, object]) -> list[dict[str, object]]:
    raw = manifest.get("jobs")
    return [dict(job) for job in raw if isinstance(job, dict)] if isinstance(raw, list) else []


def _complete_ids(jobs: list[dict[str, object]]) -> set[str]:
    return {_job_id(job) for job in jobs if job.get("status") == "complete"}


def _missing_dependencies(job: dict[str, object], complete_ids: set[str]) -> list[str]:
    deps = job.get("depends_on")
    if not isinstance(deps, list):
        return []
    return [dep for dep in deps if isinstance(dep, str) and dep not in complete_ids]


def _job_id(job: dict[str, object]) -> str:
    value = job.get("id")
    return value if isinstance(value, str) else ""


def _raw_error_codes(root: Path) -> list[str]:
    raw_dir = root / "raw"
    if not raw_dir.is_dir():
        return []
    codes: list[str] = []
    for path in sorted(raw_dir.glob("*.response.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            codes.append("unreadable_response_json")
            continue
        error = payload.get("error") if isinstance(payload, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        if isinstance(code, str) and code:
            codes.append(code)
        elif error:
            codes.append("provider_error")
    return _dedupe(codes)


def _blockers(
    errors: list[str],
    raw_error_codes: list[str],
    api_key_present: bool,
    ready_count: int,
    total_count: int,
) -> list[str]:
    blockers: list[str] = []
    if errors:
        blockers.append("run manifest is invalid")
    if total_count == 0:
        blockers.append("no imagegen jobs found")
    if "invalid_api_key" in raw_error_codes:
        blockers.append("raw response reports invalid OpenAI API key")
    if ready_count > 0 and not api_key_present and "invalid_api_key" not in raw_error_codes:
        blockers.append("OPENAI_API_KEY is missing for secondary fallback")
    return blockers


def _status(
    errors: list[str],
    raw_error_codes: list[str],
    api_key_present: bool,
    ready_count: int,
    blocked_count: int,
    total_count: int,
    complete_count: int,
) -> str:
    if errors or total_count == 0:
        return "invalid_run"
    if "invalid_api_key" in raw_error_codes:
        return "blocked_invalid_openai_api_key"
    if total_count and complete_count == total_count:
        return "complete"
    if ready_count > 0 and not api_key_present:
        return "waiting_for_generation_credentials"
    if ready_count > 0:
        return "ready_for_base_generation" if complete_count == 0 else "ready_for_next_generation"
    if blocked_count > 0:
        return "waiting_for_dependencies"
    return "inspect_manually"


def _next_actions(status: str) -> list[str]:
    if status == "blocked_invalid_openai_api_key":
        return [
            "set a valid OPENAI_API_KEY or use the built-in $imagegen path before retrying base generation",
            "do not edit imagegen-jobs.json or fabricate decoded/base.png",
            "retry only the ready base job, then inspect the base before row generation",
        ]
    if status == "ready_for_base_generation":
        return [
            "generate only the ready base job first",
            "record the selected built-in $imagegen output with record_imagegen_result.py, or use the documented secondary fallback",
            "inspect the base before unlocking row-strip generation",
        ]
    if status == "waiting_for_generation_credentials":
        return [
            "use the built-in $imagegen path or set OPENAI_API_KEY before secondary fallback",
            "generate only the ready job once credentials are available",
        ]
    if status == "waiting_for_dependencies":
        return ["complete upstream ready jobs before generating blocked row-strip jobs"]
    if status == "complete":
        return ["run finalize_pet_run.py and review QA outputs"]
    if status == "invalid_run":
        return ["repair the hatch-pet run manifest before generation"]
    return ["inspect the run manually before generation"]


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
    parser = argparse.ArgumentParser(description="Inspect hatch-pet image generation readiness without calling a provider.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--openai-api-key-present", action="store_true")
    parser.add_argument("--report", default="")
    parser.add_argument("--markdown", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = inspect_hatch_pet_imagegen_readiness(
        args.run_dir,
        openai_api_key_present=True if args.openai_api_key_present else None,
    )
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    _write_text(args.report, payload + "\n")
    _write_text(args.markdown, render_hatch_pet_imagegen_readiness_markdown(report))
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
