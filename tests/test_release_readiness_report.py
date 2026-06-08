import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "release_readiness_report.py"


def _copy_original_pack(target: Path) -> Path:
    source = REPO_ROOT / "assets" / "companion" / "original_oc"
    destination = target / "original_oc"
    shutil.copytree(source, destination)
    return destination


def _write_frozen_build(root: Path, *, include_license: bool = True) -> tuple[Path, Path]:
    app_dir = root / "dist" / "E-Moti"
    character_dir = app_dir / "_internal" / "assets" / "companion"
    _copy_original_pack(character_dir)
    if not include_license:
        (character_dir / "original_oc" / "LICENSE.md").unlink()
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "E-Moti.exe").write_bytes(b"MZ" + b"0" * 128)
    installer = root / "dist" / "installer" / "E-Moti_Setup_0.1.0.exe"
    installer.parent.mkdir(parents=True)
    installer.write_bytes(b"MZ" + b"1" * 128)
    return app_dir, installer


def _write_llm_report(path: Path, *, ok: bool = True) -> Path:
    payload: dict[str, object] = {
        "ok": ok,
        "reason": "" if ok else "cue:sadness:expected_expression:sadness",
        "diagnostic": {
            "ok": True,
            "stage": "event_validation",
            "reason": "",
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
        },
        "probe_count": 1,
        "passed_count": 1 if ok else 0,
        "failed_count": 0 if ok else 1,
        "cases": [
            {
                "case_id": "sadness",
                "expected_expression_id": "sadness",
                "ok": ok,
                "reason": "" if ok else "expected_expression:sadness",
                "speech_len": 18,
                "speech_preview": "那我靠近一点陪你。",
                "expression_ids": ["sadness"] if ok else ["calm"],
                "motion_ids": ["SwitchDown"],
                "fallback_reason": "",
            }
        ],
        "speech_quality": {
            "min_speech_chars": 8,
            "max_speech_chars": 80,
            "empty_count": 0,
            "short_count": 0,
            "long_count": 0,
            "violations": [],
        },
        "state_mutation_check": {"ok": True, "changed_fields": []},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_portrait_workflow_report(path: Path, *, ok: bool = False) -> Path:
    payload = {
        "ok": ok,
        "source_root": "artifacts/portrait-video-source",
        "handoff_dir": "artifacts/portrait-video-handoff",
        "candidate_root": "artifacts",
        "pack_count": 1,
        "missing_handoff_count": 0,
        "ready_count": 0,
        "waiting_count": 0,
        "insufficient_count": 0,
        "motion_candidate_count": 0,
        "items": [
            {
                "set_id": "xingxi-vn-neutral-20260608",
                "source_status": "ready_with_warnings",
                "frame_count": 60,
                "readable_frame_count": 60,
                "invalid_frame_count": 0,
                "size_mismatch_count": 60,
                "normalizable_size_mismatch_count": 60,
                "body_drift_warning_count": 0,
                "handoff_status": "present",
                "motion_candidate_status": "failed",
                "next_action": "regenerate_ai_video",
                "source_next_action": "normalize_frames",
                "motion_next_action": "regenerate_ai_video",
                "suggested_commands": [
                    "python tools\\art\\normalize_portrait_video_source_frames.py artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608 --output-pack-dir artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized --report artifacts\\portrait-video-frame-normalization.json",
                    "python tools\\art\\inspect_portrait_video_source_frames.py artifacts\\portrait-video-source --report artifacts\\portrait-video-frame-preflight.json",
                ],
                "attention_reasons": [
                    "normalizable_size_mismatch",
                    "failed_motion_extraction",
                ],
                "warnings": [],
                "errors": ["motion extraction failed: not enough stable frames after body drift filtering"],
            }
        ],
        "errors": ["motion extraction failed: not enough stable frames after body drift filtering"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_portrait_candidate_report(path: Path, *, decision_state: str = "needs_iteration") -> Path:
    payload = {
        "ok": True,
        "path": "artifacts\\portrait-candidate-xingxi-vn-20260607\\portrait_candidate.json",
        "status": "candidate",
        "image_count": 1,
        "decision_state": decision_state,
        "blockers": [
            "candidate status is not approved",
            "neutral expression requires blink_half and blink_closed frames",
        ],
        "warnings": ["neutral.open: light_edge_halo_risk"],
        "validation_errors": [],
        "next_human_decisions": [
            "approve edge cleanup and expression/blink generation for this candidate, or reject it and regenerate"
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _run_tool(
    character_pack: Path,
    app_dir: Path,
    installer: Path,
    tmp_path: Path,
    *,
    llm_reports: list[Path] | None = None,
    portrait_workflow_reports: list[Path] | None = None,
    portrait_candidate_reports: list[Path] | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        str(TOOL),
        "--character-pack",
        str(character_pack),
        "--app-dir",
        str(app_dir),
        "--installer",
        str(installer),
    ]
    for report in llm_reports or []:
        args.extend(["--llm-report", str(report)])
    for report in portrait_workflow_reports or []:
        args.extend(["--portrait-workflow-report", str(report)])
    for report in portrait_candidate_reports or []:
        args.extend(["--portrait-candidate-report", str(report)])
    args.extend(
        [
            "--json",
            str(tmp_path / "readiness.json"),
            "--markdown",
            str(tmp_path / "readiness.md"),
        ]
    )
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


def test_release_readiness_report_accepts_ready_source_and_frozen_artifacts(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")

    result = _run_tool(character_pack, app_dir, installer, tmp_path)

    payload = json.loads(result.stdout)
    saved = json.loads((tmp_path / "readiness.json").read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stderr
    assert payload == saved
    assert payload["ok"] is True
    assert payload["status"] == "ready"
    assert [check["id"] for check in payload["checks"]] == ["source_character_pack", "windows_build"]
    assert all(check["ok"] is True for check in payload["checks"])
    source_check = payload["checks"][0]
    assert source_check["manual_qa_required"] is False
    assert source_check["distribution_boundary"] == "shareable_after_review"
    assert "portrait_assets_provenance.md" in source_check["provenance_files"]
    assert "LICENSE.md" in source_check["license_files"]
    assert payload["next_actions"] == []
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert markdown.startswith("# E-Moti Release Readiness")
    assert "- Distribution boundary: `shareable_after_review`" in markdown
    assert "- Manual QA required: `no`" in markdown
    assert "- Provenance files:" in markdown
    assert "  - `portrait_assets_provenance.md`" in markdown
    assert "- License files:" in markdown
    assert "  - `LICENSE.md`" in markdown


def test_release_readiness_report_accepts_ready_llm_report(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    llm_report = _write_llm_report(tmp_path / "llm-cue.json", ok=True)

    result = _run_tool(character_pack, app_dir, installer, tmp_path, llm_reports=[llm_report])

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert [check["id"] for check in payload["checks"]] == [
        "source_character_pack",
        "windows_build",
        "llm_report",
    ]
    llm_check = payload["checks"][2]
    assert llm_check["ok"] is True
    assert llm_check["status"] == "passed"
    assert llm_check["provider"] == "deepseek"
    assert llm_check["report_type"] == "expression_cue_probe"
    assert llm_check["case_count"] == 1
    assert llm_check["speech_quality_violation_count"] == 0
    assert llm_check["state_mutation_ok"] is True
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "- Report type: `expression_cue_probe`" in markdown
    assert "- Provider: `deepseek`" in markdown
    assert "- Model: `deepseek-v4-flash`" in markdown
    assert "- Cue cases: `1`" in markdown
    assert "- Speech quality violations: `0`" in markdown
    assert "- State guard: `passed`" in markdown


def test_release_readiness_report_accepts_ready_llm_report_directory(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    llm_dir = tmp_path / "llm-smoke"
    llm_dir.mkdir()
    _write_llm_report(llm_dir / "llm-cue.json", ok=True)

    result = _run_tool(character_pack, app_dir, installer, tmp_path, llm_reports=[llm_dir])

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    llm_check = payload["checks"][2]
    assert llm_check["id"] == "llm_report_directory"
    assert llm_check["ok"] is True
    assert llm_check["status"] == "passed"
    assert llm_check["report_count"] == 1
    assert llm_check["passed_count"] == 1
    assert llm_check["needs_attention_count"] == 0
    assert llm_check["invalid_count"] == 0
    assert llm_check["next_actions"] == []
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### LLM Smoke Report Directory" in markdown
    assert "- Reports: `1`" in markdown
    assert "- Passed reports: `1`" in markdown
    assert "- Needs attention: `0`" in markdown
    assert "- Invalid reports: `0`" in markdown


def test_release_readiness_report_summarizes_llm_directory_attention_reports(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    llm_dir = tmp_path / "llm-smoke"
    llm_dir.mkdir()
    _write_llm_report(llm_dir / "llm-cue-ok.json", ok=True)
    _write_llm_report(llm_dir / "llm-cue-failing.json", ok=False)

    result = _run_tool(character_pack, app_dir, installer, tmp_path, llm_reports=[llm_dir])

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    llm_check = payload["checks"][2]
    assert llm_check["id"] == "llm_report_directory"
    assert llm_check["status"] == "needs_attention"
    assert llm_check["report_count"] == 2
    assert llm_check["passed_count"] == 1
    assert llm_check["needs_attention_count"] == 1
    assert llm_check["attention_reports"] == [
        "llm-cue-failing.json: needs_attention, issues=2, reason=cue:sadness:expected_expression:sadness"
    ]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "- Reports needing attention:" in markdown
    assert (
        "  - `llm-cue-failing.json: needs_attention, issues=2, "
        "reason=cue:sadness:expected_expression:sadness`"
    ) in markdown


def test_release_readiness_report_surfaces_source_pack_distribution_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    (character_pack / "LICENSE.md").unlink()
    app_dir, installer = _write_frozen_build(tmp_path / "build")

    result = _run_tool(character_pack, app_dir, installer, tmp_path)

    payload = json.loads(result.stdout)
    source_check = payload["checks"][0]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["status"] == "needs_attention"
    assert source_check["id"] == "source_character_pack"
    assert source_check["ok"] is False
    assert source_check["status"] == "needs_distribution_review"
    assert "add license or usage-rights note before sharing or bundling" in payload["next_actions"]


def test_release_readiness_report_surfaces_frozen_build_license_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build", include_license=False)

    result = _run_tool(character_pack, app_dir, installer, tmp_path)

    payload = json.loads(result.stdout)
    build_check = payload["checks"][1]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert build_check["id"] == "windows_build"
    assert build_check["ok"] is False
    assert "frozen character pack missing required bundled asset: LICENSE.md" in build_check["errors"]
    assert "rebuild Windows app and installer after fixing release artifacts" in payload["next_actions"]


def test_release_readiness_report_surfaces_llm_review_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    llm_report = _write_llm_report(tmp_path / "llm-cue-failing.json", ok=False)

    result = _run_tool(character_pack, app_dir, installer, tmp_path, llm_reports=[llm_report])

    payload = json.loads(result.stdout)
    llm_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["status"] == "needs_attention"
    assert llm_check["id"] == "llm_report"
    assert llm_check["ok"] is False
    assert llm_check["status"] == "needs_attention"
    assert "cue_case_failed" in llm_check["errors"][1]
    assert "review LLM smoke report before release" in payload["next_actions"]


def test_release_readiness_report_surfaces_portrait_workflow_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    workflow_report = _write_portrait_workflow_report(tmp_path / "portrait-workflow.json", ok=False)

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_workflow_reports=[workflow_report],
    )

    payload = json.loads(result.stdout)
    workflow_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["status"] == "needs_attention"
    assert workflow_check["id"] == "portrait_video_workflow"
    assert workflow_check["ok"] is False
    assert workflow_check["status"] == "needs_attention"
    assert workflow_check["attention_reasons"] == [
        "normalizable_size_mismatch",
        "failed_motion_extraction",
    ]
    assert workflow_check["next_actions"] == [
        "resolve portrait AI-video workflow blockers before promoting motion assets"
    ]
    assert workflow_check["suggested_commands"] == [
        "python tools\\art\\normalize_portrait_video_source_frames.py artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608 --output-pack-dir artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized --report artifacts\\portrait-video-frame-normalization.json",
        "python tools\\art\\inspect_portrait_video_source_frames.py artifacts\\portrait-video-source --report artifacts\\portrait-video-frame-preflight.json",
    ]
    assert "resolve portrait AI-video workflow blockers before promoting motion assets" in payload["next_actions"]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "- Attention reasons:" in markdown
    assert "  - `normalizable_size_mismatch`" in markdown
    assert "  - `failed_motion_extraction`" in markdown
    assert "- Suggested commands:\n" in markdown
    assert (
        "  - `python tools\\art\\normalize_portrait_video_source_frames.py "
        "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608 "
        "--output-pack-dir artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized "
        "--report artifacts\\portrait-video-frame-normalization.json`"
    ) in markdown


def test_release_readiness_report_surfaces_portrait_candidate_decision_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    candidate_report = _write_portrait_candidate_report(tmp_path / "portrait-candidate-decision.json")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_candidate_reports=[candidate_report],
    )

    payload = json.loads(result.stdout)
    candidate_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["status"] == "needs_attention"
    assert candidate_check["id"] == "portrait_candidate_decision"
    assert candidate_check["ok"] is False
    assert candidate_check["status"] == "needs_iteration"
    assert candidate_check["decision_state"] == "needs_iteration"
    assert candidate_check["candidate_status"] == "candidate"
    assert candidate_check["image_count"] == 1
    assert candidate_check["blocker_count"] == 2
    assert candidate_check["warning_count"] == 1
    assert candidate_check["blockers"] == [
        "candidate status is not approved",
        "neutral expression requires blink_half and blink_closed frames",
    ]
    assert candidate_check["warnings"] == ["neutral.open: light_edge_halo_risk"]
    assert candidate_check["next_human_decisions"] == [
        "approve edge cleanup and expression/blink generation for this candidate, or reject it and regenerate"
    ]
    assert "resolve portrait candidate blockers before manifest promotion" in payload["next_actions"]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### Portrait Candidate Decision" in markdown
    assert "- Decision state: `needs_iteration`" in markdown
    assert "- Candidate status: `candidate`" in markdown
    assert "- Blockers:" in markdown
    assert "  - `candidate status is not approved`" in markdown
    assert "- Candidate warnings:" in markdown
    assert "  - `neutral.open: light_edge_halo_risk`" in markdown
    assert "- Next human decisions:" in markdown
    assert (
        "  - `approve edge cleanup and expression/blink generation for this candidate, "
        "or reject it and regenerate`"
    ) in markdown
