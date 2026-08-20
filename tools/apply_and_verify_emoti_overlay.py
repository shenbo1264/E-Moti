from __future__ import annotations

"""One-command E-Moti overlay application and verification.

Run this script from the delivered overlay package and point it at a full
E-Moti checkout. It applies the reviewed overlay, then performs syntax,
focused/full tests, plugin smokes, manifest validation, and (optionally on
Windows) the existing application/installer build scripts.
"""

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Sequence

from apply_emoti_plugin_overlay import apply_overlay


@dataclass(slots=True)
class CommandResult:
    name: str
    argv: list[str]
    returncode: int
    duration_seconds: float
    stdout_tail: str
    stderr_tail: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "argv": self.argv,
            "returncode": self.returncode,
            "ok": self.ok,
            "duration_seconds": round(self.duration_seconds, 3),
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


@dataclass(slots=True)
class VerificationReport:
    target: str
    overlay: dict[str, object]
    commands: list[CommandResult] = field(default_factory=list)
    started_at: int = field(default_factory=lambda: int(time.time()))
    finished_at: int = 0

    @property
    def ok(self) -> bool:
        return bool(self.overlay.get("ok")) and all(command.ok for command in self.commands)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "ok": self.ok,
            "target": self.target,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "overlay": self.overlay,
            "commands": [command.to_dict() for command in self.commands],
        }


FOCUSED_TESTS = (
    "tests/test_memory.py",
    "tests/test_controller.py",
    "tests/test_app.py",
    "tests/test_desktop_pet_smoke.py",
    "tests/test_emotional_memory.py",
    "tests/test_emotional_memory_policy.py",
    "tests/test_emotional_memory_service.py",
    "tests/test_focus_companion.py",
    "tests/test_focus_companion_runtime.py",
    "tests/test_integrated_story_runtime.py",
    "tests/test_integrated_story_smoke_tool.py",
    "tests/test_memory_album_controller.py",
    "tests/test_memory_album_qt_contract.py",
    "tests/test_focus_companion_qt_contract.py",
    "tests/test_plugin_manifest.py",
    "tests/test_plugin_runtime.py",
    "tests/test_plugin_runtime_v2.py",
    "tests/test_plugin_host.py",
    "tests/test_plugin_package.py",
    "tests/test_plugin_subsystem.py",
    "tests/test_plugin_enabled_controller_behavior.py",
    "tests/test_plugin_enabled_controller_contract.py",
    "tests/test_plugin_center_controller.py",
    "tests/test_plugin_center_qt_contract.py",
    "tests/test_apply_emoti_plugin_overlay.py",
    "tests/test_apply_and_verify_emoti_overlay.py",
    "tests/test_render_plugin_center_preview.py",
    "tests/test_render_plugin_story_demo.py",
    "tests/test_render_story_feature_previews.py",
    "tests/test_overlay_contract_smoke_tool.py",
    "tests/test_private_provider_smoke_tool.py",
    "tests/test_release_security_cli.py",
    "tests/test_qt_optional_contracts.py",
    "tests/test_render_tools.py",
    "tests/test_xingxi_product_copy.py",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply and verify the E-Moti integration overlay.")
    parser.add_argument("target", type=Path, help="Full E-Moti repository checkout")
    parser.add_argument("--python", dest="python_path", default=sys.executable)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify an already reviewed integration without applying the overlay again",
    )
    parser.add_argument("--skip-copy-tuning", action="store_true")
    parser.add_argument("--skip-full-tests", action="store_true")
    parser.add_argument("--skip-focused-tests", action="store_true")
    parser.add_argument("--run-windows-build", action="store_true")
    parser.add_argument("--run-installer-build", action="store_true")
    parser.add_argument("--submission-zip", type=Path)
    parser.add_argument("--run-private-api-smoke", action="store_true")
    parser.add_argument("--require-online-providers", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    target = args.target.resolve()
    if args.verify_only:
        overlay_payload = {
            "ok": True,
            "dry_run": False,
            "verify_only": True,
            "target": str(target),
            "copied": [],
            "patched": [],
            "backups": [],
            "warnings": [],
        }
    else:
        overlay_report = apply_overlay(
            target,
            force=args.force,
            apply_copy_tuning=not args.skip_copy_tuning,
        )
        overlay_payload = overlay_report.to_dict()
    report = VerificationReport(target=str(target), overlay=overlay_payload)
    if not overlay_payload.get("ok"):
        return _finish(report, args.report, returncode=3)

    python_path = str(Path(args.python_path).resolve()) if os.path.sep in args.python_path else args.python_path
    artifacts = target / "artifacts" / "plugin-overlay-verification"
    artifacts.mkdir(parents=True, exist_ok=True)

    commands: list[tuple[str, Sequence[str]]] = [
        ("compileall", [python_path, "-m", "compileall", "-q", "src", "tests", "tools"]),
    ]
    if not args.skip_focused_tests:
        existing = [path for path in FOCUSED_TESTS if (target / path).is_file()]
        commands.append(("focused-pytest", [python_path, "-m", "pytest", "-q", *existing]))
    if not args.skip_full_tests:
        commands.append(("full-pytest", [python_path, "-m", "pytest", "-q"]))
    commands.extend(
        (
            (
                "overlay-contract-smoke",
                [
                    python_path,
                    "tools/run_overlay_contract_smoke.py",
                    "--report",
                    str(artifacts / "overlay_contract_smoke.json"),
                ],
            ),
            (
                "plugin-host-smoke",
                [
                    python_path,
                    "tools/run_plugin_smoke.py",
                    "--plugin-root",
                    "plugins",
                    "--report",
                    str(artifacts / "plugin_host_smoke.json"),
                ],
            ),
            (
                "plugin-runtime-v2-smoke",
                [
                    python_path,
                    "tools/run_plugin_runtime_v2_smoke.py",
                    "--report",
                    str(artifacts / "plugin_runtime_v2_smoke.json"),
                ],
            ),
            (
                "validate-plugin-capability-contracts",
                [
                    python_path,
                    "tools/validate_emoti_plugin.py",
                    "plugins/capability_contracts",
                    "--activate",
                    "--report",
                    str(artifacts / "capability_contracts_validation.json"),
                ],
            ),
            (
                "validate-plugin-local-expression",
                [
                    python_path,
                    "tools/validate_emoti_plugin.py",
                    "plugins/local_expression_fallback",
                    "--activate",
                    "--report",
                    str(artifacts / "local_expression_validation.json"),
                ],
            ),
            (
                "validate-plugin-stargazing",
                [
                    python_path,
                    "tools/validate_emoti_plugin.py",
                    "plugins/stargazing_moment",
                    "--activate",
                    "--report",
                    str(artifacts / "stargazing_validation.json"),
                ],
            ),
            (
                "render-plugin-center-preview",
                [
                    python_path,
                    "tools/render_plugin_center_preview.py",
                    "--output",
                    str(artifacts / "plugin_center_preview.html"),
                    "--png-output",
                    str(artifacts / "plugin_center_preview.png"),
                ],
            ),
            (
                "render-story-previews",
                [
                    python_path,
                    "tools/render_story_feature_previews.py",
                    "--output-dir",
                    str(artifacts / "story_feature_previews"),
                ],
            ),
            (
                "render-plugin-story-demo",
                [
                    python_path,
                    "tools/render_plugin_story_demo.py",
                    "--gif-output",
                    str(artifacts / "plugin_story_demo.gif"),
                    "--cover-output",
                    str(artifacts / "plugin_story_cover.png"),
                    "--report",
                    str(artifacts / "plugin_story_demo.json"),
                ],
            ),
            (
                "scan-public-config-secrets",
                [
                    python_path,
                    "-m",
                    "guanghe_companion.release_security",
                    "public_config_template",
                    "--report",
                    str(artifacts / "public_config_secret_scan.json"),
                ],
            ),
            (
                "scan-plugin-secrets",
                [
                    python_path,
                    "-m",
                    "guanghe_companion.release_security",
                    "plugins",
                    "--report",
                    str(artifacts / "plugin_secret_scan.json"),
                ],
            ),
            (
                "integrated-story-smoke",
                [
                    python_path,
                    "tools/run_integrated_story_smoke.py",
                    "--output-dir",
                    str(artifacts / "integrated_story"),
                ],
            ),
        )
    )

    if args.submission_zip is not None:
        for index, (name, command) in enumerate(commands):
            if name == "integrated-story-smoke":
                commands[index] = (name, [*command, "--submission-zip", str(args.submission_zip.resolve())])
                break
    if args.run_private_api_smoke:
        if args.submission_zip is None:
            report.commands.append(
                CommandResult(
                    "private-provider-smoke",
                    [python_path, "tools/run_private_provider_smoke.py"],
                    2,
                    0.0,
                    "",
                    "--run-private-api-smoke requires --submission-zip",
                )
            )
            return _finish(report, args.report, returncode=2)
        provider_command = [
            python_path,
            "tools/run_private_provider_smoke.py",
            "--submission-zip",
            str(args.submission_zip.resolve()),
            "--report",
            str(artifacts / "private_provider_smoke_redacted.json"),
        ]
        if args.require_online_providers:
            provider_command.append("--require-online")
        commands.append(("private-provider-smoke", provider_command))

    for name, command in commands:
        result = _run(name, command, cwd=target)
        report.commands.append(result)
        if not result.ok:
            return _finish(report, args.report, returncode=result.returncode or 1)

    if args.run_windows_build:
        if os.name != "nt":
            report.commands.append(
                CommandResult(
                    "windows-build",
                    ["powershell", "tools/build_windows_app.ps1"],
                    125,
                    0.0,
                    "",
                    "Windows build requested on a non-Windows host.",
                )
            )
            return _finish(report, args.report, returncode=125)
        result = _run(
            "windows-build",
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "tools/build_windows_app.ps1",
                "-PythonPath",
                python_path,
            ],
            cwd=target,
        )
        report.commands.append(result)
        if not result.ok:
            return _finish(report, args.report, returncode=result.returncode or 1)

    if args.run_installer_build:
        if os.name != "nt":
            return _finish(report, args.report, returncode=125)
        result = _run(
            "installer-build",
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "tools/build_windows_installer.ps1",
                "-SkipAppBuild",
                "-PythonPath",
                python_path,
            ],
            cwd=target,
        )
        report.commands.append(result)
        if not result.ok:
            return _finish(report, args.report, returncode=result.returncode or 1)

    return _finish(report, args.report, returncode=0)


def _run(name: str, argv: Sequence[str], *, cwd: Path) -> CommandResult:
    started = time.perf_counter()
    completed = subprocess.run(
        list(argv),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    elapsed = time.perf_counter() - started
    stdout_tail = completed.stdout[-12000:]
    stderr_tail = completed.stderr[-12000:]
    print(f"[{name}] returncode={completed.returncode} duration={elapsed:.2f}s")
    if stdout_tail:
        print(stdout_tail)
    if stderr_tail:
        print(stderr_tail, file=sys.stderr)
    return CommandResult(name, list(argv), completed.returncode, elapsed, stdout_tail, stderr_tail)


def _finish(report: VerificationReport, path: Path | None, *, returncode: int) -> int:
    report.finished_at = int(time.time())
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
    print(payload)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    return 0 if report.ok and returncode == 0 else (returncode or 1)


if __name__ == "__main__":
    raise SystemExit(main())
