from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.hatch_pet_imagegen_readiness import inspect_hatch_pet_imagegen_readiness


@dataclass(frozen=True, slots=True)
class HatchPetImagegenRoutePreflightReport:
    ok: bool
    status: str
    run_dir: str
    ready_job_ids: tuple[str, ...]
    blocked_job_ids: tuple[str, ...]
    secondary_fallback_status: str
    codex_exec_status: str
    codex_bin: str
    codex_exec_error: str
    raw_error_codes: tuple[str, ...]
    blockers: tuple[str, ...]
    next_actions: tuple[str, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "run_dir": self.run_dir,
            "ready_job_ids": list(self.ready_job_ids),
            "blocked_job_ids": list(self.blocked_job_ids),
            "secondary_fallback_status": self.secondary_fallback_status,
            "codex_exec_status": self.codex_exec_status,
            "codex_bin": self.codex_bin,
            "codex_exec_error": self.codex_exec_error,
            "raw_error_codes": list(self.raw_error_codes),
            "blockers": list(self.blockers),
            "next_actions": list(self.next_actions),
            "errors": list(self.errors),
        }


def inspect_hatch_pet_imagegen_route_preflight(
    run_dir: Path | str,
    *,
    openai_api_key_present: bool | None = None,
    check_codex_exec: bool = False,
    codex_bin: str = "codex",
) -> HatchPetImagegenRoutePreflightReport:
    readiness = inspect_hatch_pet_imagegen_readiness(
        run_dir,
        openai_api_key_present=openai_api_key_present,
    )
    codex_status, codex_error = _codex_exec_status(codex_bin) if check_codex_exec else ("not_checked", "")
    blockers = list(readiness.blockers)
    errors = list(readiness.errors)
    if codex_status == "access_denied":
        blockers.append("codex exec is not launchable: access denied")
    elif codex_status == "missing":
        blockers.append("codex exec binary not found")
    elif codex_status == "failed":
        blockers.append("codex exec version check failed")

    route_available = readiness.ok or codex_status == "available"
    status = "ready_for_base_generation" if route_available else "blocked_generation_route"
    next_actions = [] if route_available else _next_actions(readiness.status, codex_status)
    return HatchPetImagegenRoutePreflightReport(
        ok=route_available,
        status=status,
        run_dir=readiness.run_dir,
        ready_job_ids=readiness.ready_job_ids,
        blocked_job_ids=readiness.blocked_job_ids,
        secondary_fallback_status=readiness.status,
        codex_exec_status=codex_status,
        codex_bin=codex_bin,
        codex_exec_error=codex_error,
        raw_error_codes=readiness.raw_error_codes,
        blockers=tuple(_dedupe(blockers)),
        next_actions=tuple(next_actions),
        errors=tuple(errors),
    )


def render_hatch_pet_imagegen_route_preflight_markdown(
    report: HatchPetImagegenRoutePreflightReport,
) -> str:
    lines = [
        "# Hatch Pet Imagegen Route Preflight",
        "",
        f"- Run dir: `{report.run_dir}`",
        f"- Status: `{report.status}`",
        f"- OK: `{'yes' if report.ok else 'no'}`",
        f"- Ready jobs: `{', '.join(report.ready_job_ids) or 'none'}`",
        f"- Blocked jobs: `{', '.join(report.blocked_job_ids) or 'none'}`",
        f"- Secondary fallback status: `{report.secondary_fallback_status}`",
        f"- Codex exec status: `{report.codex_exec_status}`",
        f"- Codex bin: `{report.codex_bin}`",
        f"- Raw error codes: `{', '.join(report.raw_error_codes) or 'none'}`",
    ]
    if report.codex_exec_error:
        lines.append(f"- Codex exec error: `{report.codex_exec_error}`")
    lines.extend(["", "## Blockers"])
    lines.extend(_markdown_list(report.blockers))
    lines.extend(["", "## Next Actions"])
    lines.extend(_markdown_list(report.next_actions))
    lines.extend(["", "## Errors"])
    lines.extend(_markdown_list(report.errors))
    lines.append("")
    return "\n".join(lines)


def _codex_exec_status(codex_bin: str) -> tuple[str, str]:
    try:
        result = subprocess.run(
            [codex_bin, "--version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except FileNotFoundError:
        return "missing", ""
    except PermissionError:
        return "access_denied", "Access is denied"
    except OSError as exc:
        message = str(exc)
        lowered = message.lower()
        if "access is denied" in lowered or "permission denied" in lowered:
            return "access_denied", "Access is denied"
        return "failed", _safe_error(message)
    except subprocess.TimeoutExpired:
        return "failed", "codex --version timed out"
    if result.returncode == 0:
        return "available", ""
    output = "\n".join(part.strip() for part in (result.stderr, result.stdout) if part.strip())
    lowered = output.lower()
    if "access is denied" in lowered or "permission denied" in lowered:
        return "access_denied", "Access is denied"
    return "failed", _safe_error(output or f"codex --version exited with {result.returncode}")


def _next_actions(secondary_status: str, codex_status: str) -> list[str]:
    actions: list[str] = []
    if secondary_status == "blocked_invalid_openai_api_key":
        actions.append("fix OPENAI_API_KEY for secondary fallback or make native codex exec imagegen launchable")
    elif secondary_status == "waiting_for_generation_credentials":
        actions.append("set OPENAI_API_KEY for secondary fallback or use a native imagegen route")
    if codex_status in {"access_denied", "missing", "failed"}:
        actions.append("resolve codex exec imagegen launcher before using native image generation")
    actions.append("generate and inspect only the ready base job before row generation")
    return _dedupe(actions)


def _safe_error(value: str) -> str:
    text = value.replace("\r", " ").replace("\n", " ").strip()
    if len(text) > 180:
        text = text[:177] + "..."
    return text


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


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight hatch-pet image generation routes.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--check-codex-exec", action="store_true")
    parser.add_argument("--openai-api-key-present", action="store_true")
    parser.add_argument("--report", default="")
    parser.add_argument("--markdown", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = inspect_hatch_pet_imagegen_route_preflight(
        args.run_dir,
        openai_api_key_present=True if args.openai_api_key_present else None,
        check_codex_exec=args.check_codex_exec,
        codex_bin=args.codex_bin,
    )
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    _write_text(args.report, payload + "\n")
    _write_text(args.markdown, render_hatch_pet_imagegen_route_preflight_markdown(report))
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
