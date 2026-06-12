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

from tools.art.review_pixel_pet_base import review_pixel_pet_base_candidate


DEFAULT_RECORD_SCRIPT = "$env:CODEX_HOME\\skills\\hatch-pet\\scripts\\record_imagegen_result.py"


@dataclass(frozen=True, slots=True)
class HatchPetBaseIntakePreflightReport:
    ok: bool
    status: str
    run_dir: str
    job_id: str
    source_path: str
    source_provenance: str
    generated_images_root: str
    job_ready: bool
    output_path: str
    output_exists: bool
    prompt_path: str
    character_definition_path: str
    base_review: dict[str, object]
    record_command: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    next_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "run_dir": self.run_dir,
            "job_id": self.job_id,
            "source_path": self.source_path,
            "source_provenance": self.source_provenance,
            "generated_images_root": self.generated_images_root,
            "job_ready": self.job_ready,
            "output_path": self.output_path,
            "output_exists": self.output_exists,
            "prompt_path": self.prompt_path,
            "character_definition_path": self.character_definition_path,
            "base_review": dict(self.base_review),
            "record_command": self.record_command,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }


def inspect_hatch_pet_base_intake_preflight(
    *,
    run_dir: Path | str,
    job_id: str,
    source: Path | str,
    character_id: str,
    character_definition_path: Path | str,
    prior_qa_path: Path | str | None = None,
    generated_images_root: Path | str | None = None,
    record_script: str = DEFAULT_RECORD_SCRIPT,
) -> HatchPetBaseIntakePreflightReport:
    root = Path(run_dir)
    source_path = Path(source)
    definition = Path(character_definition_path)
    generated_root = Path(generated_images_root) if generated_images_root else _default_generated_images_root()
    errors: list[str] = []
    warnings: list[str] = []

    manifest = _load_manifest(root, errors)
    jobs = _jobs(manifest)
    complete_ids = _complete_ids(jobs)
    job = _find_job(jobs, job_id)
    if job is None:
        errors.append(f"unknown job id: {job_id}")

    prompt_path = root / _string_value(job, "prompt_file") if job else Path("")
    output_path = root / _string_value(job, "output_path") if job else Path("")
    output_exists = output_path.is_file() if str(output_path) else False
    missing_dependencies = _missing_dependencies(job or {}, complete_ids)
    job_complete = bool(job and job.get("status") == "complete")
    job_ready = bool(job and not job_complete and not missing_dependencies)

    source_provenance = _source_provenance(source_path, root, generated_root, errors)
    if missing_dependencies:
        errors.append(f"missing dependency result(s): {', '.join(missing_dependencies)}")
    if job_complete:
        errors.append(f"job {job_id} is already complete")
    if output_exists:
        errors.append(f"{_display_relative(output_path, root)} already exists; recording would overwrite it")

    base_review: dict[str, object] = {}
    if source_path.is_file() and job is not None:
        review = review_pixel_pet_base_candidate(
            candidate_image=source_path,
            character_id=character_id,
            prompt_path=prompt_path,
            character_definition_path=definition,
            prior_qa_path=prior_qa_path,
            decision="accepted_for_row_testing",
        )
        base_review = review.to_dict()
        warnings.extend(review.warnings)
        if not review.ok:
            errors.extend(f"base review: {error}" for error in review.errors)

    status = _status(
        errors=errors,
        source_exists=source_path.is_file(),
        source_provenance=source_provenance,
        job=job,
        job_ready=job_ready,
        output_exists=output_exists,
        base_review=base_review,
    )
    ok = status == "ready_to_record"
    record_command = (
        _record_command(record_script, root, job_id, source_path)
        if ok
        else ""
    )
    return HatchPetBaseIntakePreflightReport(
        ok=ok,
        status=status,
        run_dir=str(root),
        job_id=job_id,
        source_path=str(source_path),
        source_provenance=source_provenance,
        generated_images_root=str(generated_root),
        job_ready=job_ready,
        output_path=str(output_path) if str(output_path) else "",
        output_exists=output_exists,
        prompt_path=str(prompt_path) if str(prompt_path) else "",
        character_definition_path=str(definition),
        base_review=base_review,
        record_command=record_command,
        errors=tuple(_dedupe(errors)),
        warnings=tuple(_dedupe(warnings)),
        next_actions=tuple(_next_actions(status, record_command)),
    )


def render_hatch_pet_base_intake_preflight_markdown(report: HatchPetBaseIntakePreflightReport) -> str:
    lines = [
        "# Hatch Pet Base Intake Preflight",
        "",
        f"- Run dir: `{report.run_dir}`",
        f"- Job id: `{report.job_id}`",
        f"- Status: `{report.status}`",
        f"- OK: `{'yes' if report.ok else 'no'}`",
        f"- Source provenance: `{report.source_provenance}`",
        f"- Source: `{report.source_path}`",
        f"- Job ready: `{'yes' if report.job_ready else 'no'}`",
        f"- Output path: `{report.output_path}`",
        f"- Output exists: `{'yes' if report.output_exists else 'no'}`",
        f"- Base review OK: `{'yes' if report.base_review.get('ok') else 'no'}`",
    ]
    if report.record_command:
        lines.extend(["", "## Record Command", "", "```powershell", report.record_command, "```"])
    lines.extend(["", "## Errors"])
    lines.extend(_markdown_list(report.errors))
    lines.extend(["", "## Warnings"])
    lines.extend(_markdown_list(report.warnings))
    lines.extend(["", "## Next Actions"])
    lines.extend(_markdown_list(report.next_actions))
    lines.append("")
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


def _find_job(jobs: list[dict[str, object]], job_id: str) -> dict[str, object] | None:
    for job in jobs:
        if job.get("id") == job_id:
            return job
    return None


def _job_id(job: dict[str, object]) -> str:
    value = job.get("id")
    return value if isinstance(value, str) else ""


def _string_value(job: dict[str, object] | None, key: str) -> str:
    if job is None:
        return ""
    value = job.get(key)
    return value if isinstance(value, str) else ""


def _missing_dependencies(job: dict[str, object], complete_ids: set[str]) -> list[str]:
    deps = job.get("depends_on")
    if not isinstance(deps, list):
        return []
    return [dep for dep in deps if isinstance(dep, str) and dep not in complete_ids]


def _source_provenance(source: Path, run_dir: Path, generated_root: Path, errors: list[str]) -> str:
    if not source.is_file():
        errors.append(f"source image not found: {source}")
        return ""
    if _is_relative_to(source, run_dir):
        errors.append(
            "source image is inside the hatch-pet run directory; use the original "
            "$CODEX_HOME/generated_images/.../ig_*.png output instead"
        )
        return "run-local-source"
    if not _is_relative_to(source, generated_root) or not source.name.startswith("ig_"):
        errors.append(
            "source image does not look like a built-in $imagegen output; expected "
            "$CODEX_HOME/generated_images/.../ig_*.png"
        )
        return "external-source"
    return "built-in-imagegen"


def _default_generated_images_root() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser()
    return codex_home / "generated_images"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _display_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _status(
    *,
    errors: list[str],
    source_exists: bool,
    source_provenance: str,
    job: dict[str, object] | None,
    job_ready: bool,
    output_exists: bool,
    base_review: dict[str, object],
) -> str:
    if not source_exists:
        return "missing_source"
    if source_provenance not in {"built-in-imagegen"}:
        return "source_not_built_in_imagegen"
    if job is None:
        return "unknown_job"
    if not job_ready:
        return "job_not_ready"
    if output_exists:
        return "recording_would_overwrite"
    if base_review and base_review.get("ok") is not True:
        return "candidate_review_failed"
    if errors:
        return "invalid_run"
    return "ready_to_record"


def _record_command(record_script: str, run_dir: Path, job_id: str, source: Path) -> str:
    return (
        f'python {record_script} --run-dir "{run_dir}" '
        f'--job-id {job_id} --source "{source}"'
    )


def _next_actions(status: str, record_command: str) -> list[str]:
    if status == "ready_to_record":
        return [
            "record the selected built-in $imagegen output with the suggested command",
            "review decoded/base.png before generating row-strip jobs",
        ]
    if status == "source_not_built_in_imagegen":
        return ["select the original built-in $imagegen ig_*.png output before recording"]
    if status == "missing_source":
        return ["provide an existing source image from the built-in $imagegen output directory"]
    if status == "job_not_ready":
        return ["complete missing upstream dependencies before recording this job"]
    if status == "recording_would_overwrite":
        return ["inspect the existing output; do not overwrite without an explicit force decision"]
    if status == "candidate_review_failed":
        return ["reject this base candidate or regenerate before recording it"]
    if status == "unknown_job":
        return ["use a job id present in imagegen-jobs.json"]
    if record_command:
        return [record_command]
    return ["repair the hatch-pet run before recording a base image"]


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
    parser = argparse.ArgumentParser(description="Preflight a hatch-pet base image before recording it.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--character-id", required=True)
    parser.add_argument("--character-definition", required=True)
    parser.add_argument("--prior-qa", default="")
    parser.add_argument("--generated-images-root", default="")
    parser.add_argument("--record-script", default=DEFAULT_RECORD_SCRIPT)
    parser.add_argument("--report", default="")
    parser.add_argument("--markdown", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = inspect_hatch_pet_base_intake_preflight(
        run_dir=args.run_dir,
        job_id=args.job_id,
        source=args.source,
        character_id=args.character_id,
        character_definition_path=args.character_definition,
        prior_qa_path=args.prior_qa or None,
        generated_images_root=args.generated_images_root or None,
        record_script=args.record_script,
    )
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    _write_text(args.report, payload + "\n")
    _write_text(args.markdown, render_hatch_pet_base_intake_preflight_markdown(report))
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
