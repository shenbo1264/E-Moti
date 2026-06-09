import json
import shutil
import subprocess
import sys
import zipfile
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


def _write_portrait_source_create_report(
    path: Path,
    *,
    ok: bool = True,
    omitted_source_pack_paths: set[str] | None = None,
) -> Path:
    candidate_manifest = path.parent / "portrait_candidate.json"
    source_image = path.parent / "portraits" / "neutral_open.png"
    output_dir = path.parent / "portrait-video-source" / "xingxi-vn-neutral-20260608"
    candidate_manifest.write_text("{}", encoding="utf-8")
    source_image.parent.mkdir(parents=True, exist_ok=True)
    source_image.write_bytes(b"png")
    if ok:
        _write_portrait_video_source_pack_dir(output_dir, omitted_paths=omitted_source_pack_paths or set())
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": ok,
        "candidate_manifest_path": str(candidate_manifest),
        "output_root": str(path.parent / "portrait-video-source"),
        "requested_count": 1,
        "created_count": 1 if ok else 0,
        "failed_count": 0 if ok else 1,
        "packs": [
            {
                "expression_id": "neutral",
                "variant": "open",
                "set_id": "xingxi-vn-neutral-20260608",
                "source_image": str(source_image),
                "output_dir": str(output_dir),
                "status": "created" if ok else "failed",
                "errors": [] if ok else ["source image conversion failed"],
            }
        ],
        "errors": [] if ok else ["source image conversion failed"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_portrait_video_source_pack_dir(output_dir: Path, *, omitted_paths: set[str]) -> None:
    files = {
        "source_pack.json": b'{"set_id":"xingxi-vn-neutral-20260608","reference_image":"reference/neutral_open.png"}\n',
        "gemini_prompt.md": b"# Gemini Portrait Video Prompt\n",
        "provider_prompts.md": b"# Provider Prompts\n",
        "reference/neutral_open.png": b"png",
        "frames/README.md": b"exported frames go here\n",
        "video/README.md": b"provider video goes here\n",
    }
    for relative_path, content in files.items():
        if relative_path in omitted_paths:
            continue
        target = output_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    for relative_dir in ("reference", "frames", "video"):
        if relative_dir not in omitted_paths:
            (output_dir / relative_dir).mkdir(parents=True, exist_ok=True)


def _write_liveportrait_preflight_report(path: Path, *, ok: bool = False) -> Path:
    payload = {
        "ok": ok,
        "source_pack_dir": "artifacts/portrait-video-source/xingxi-vn-neutral-20260608",
        "liveportrait_root": "tmp/liveportrait_research/LivePortrait",
        "source_image_path": "artifacts/portrait-video-source/xingxi-vn-neutral-20260608/reference/neutral_open.png",
        "reference_size": [1024, 1536],
        "driving_path": "",
        "driving_status": "missing" if not ok else "valid_video",
        "ffmpeg_path": "ffmpeg",
        "next_action": "download_liveportrait_weights" if not ok else "run_liveportrait",
        "suggested_command": "" if not ok else "python inference.py -s source.png -d driver.mp4",
        "suggested_commands": [
            "Push-Location tmp\\liveportrait_research\\LivePortrait; huggingface-cli download KlingTeam/LivePortrait --local-dir pretrained_weights --exclude \"*.git*\" \"README.md\" \"docs\"; Pop-Location",
            "New-Item -ItemType Directory -Force tmp\\liveportrait_research\\drivers",
        ]
        if not ok
        else ["python inference.py -s source.png -d driver.mp4"],
        "errors": ["required pretrained weights are missing", "driving video or motion template not found"]
        if not ok
        else [],
        "missing_weight_paths": [
            "pretrained_weights/liveportrait/base_models/appearance_feature_extractor.pth",
            "pretrained_weights/liveportrait/base_models/motion_extractor.pth",
        ]
        if not ok
        else [],
        "warnings": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_portrait_frame_qa_report(
    path: Path,
    *,
    status: str = "ready_with_warnings",
    preview_exists: bool = True,
) -> Path:
    preview_path = path.parent / "portrait-frame-qa-preview.png"
    if preview_exists:
        preview_path.write_bytes(b"png")
    payload = {
        "ok": True,
        "source_pack_dir": "artifacts/portrait-video-source/xingxi-vn-neutral-20260608-normalized",
        "set_id": "xingxi-vn-neutral-20260608-normalized",
        "status": status,
        "next_action": "review_frame_warnings" if status != "ready" else "process_frames",
        "preview_path": str(preview_path),
        "reference_image": "artifacts/portrait-video-source/xingxi-vn-neutral-20260608-normalized/reference/neutral_open.png",
        "reference_size": [1024, 1536],
        "frame_count": 60,
        "sampled_frame_count": 12,
        "size_mismatch_count": 0,
        "max_body_drift": 44.72 if status != "ready" else 8.2,
        "frames": [],
        "errors": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_portrait_frame_preflight_report(path: Path, *, status: str = "ready_with_warnings") -> Path:
    is_ready = status == "ready"
    payload = {
        "ok": True,
        "source_root": "artifacts\\portrait-video-source",
        "pack_count": 1,
        "ready_count": 1 if is_ready else 0,
        "waiting_count": 0,
        "insufficient_count": 0,
        "invalid_count": 0,
        "warning_count": 0 if is_ready else 1,
        "items": [
            {
                "set_id": "xingxi-vn-neutral-20260608-normalized",
                "source_pack_dir": "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized",
                "reference_image": "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized\\reference\\neutral_open.png",
                "frames_dir": "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized\\frames",
                "frame_count": 60,
                "readable_frame_count": 60,
                "invalid_frame_count": 0,
                "size_mismatch_count": 0,
                "normalizable_size_mismatch_count": 0,
                "body_drift_warning_count": 0 if is_ready else 60,
                "status": status,
                "next_action": "process_frames" if is_ready else "review_frame_warnings",
                "warnings": [] if is_ready else ["frame_00001.png body drift 26.6 exceeds 16.0"],
                "errors": [],
            }
        ],
        "errors": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_portrait_frame_normalization_report(path: Path, *, ok: bool = True) -> Path:
    payload = {
        "ok": ok,
        "source_set_id": "xingxi-vn-neutral-20260608",
        "set_id": "xingxi-vn-neutral-20260608-normalized",
        "source_pack_dir": "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608",
        "output_pack_dir": "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized",
        "reference_image": "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized\\reference\\neutral_open.png",
        "source_frames_dir": "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608\\frames",
        "output_frames_dir": "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized\\frames",
        "reference_size": [1024, 1536],
        "input_frame_count": 60,
        "normalized_frame_count": 60 if ok else 0,
        "resized_frame_count": 60 if ok else 0,
        "copied_frame_count": 0,
        "invalid_frame_count": 0 if ok else 1,
        "aspect_mismatch_count": 0 if ok else 1,
        "warnings": ["frame_00001.png resized from 496x744 to 1024x1536"] if ok else [],
        "errors": [] if ok else ["frame_00001.png aspect ratio differs from reference"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_portrait_source_batch_report(path: Path, *, status: str = "ready_with_warnings") -> Path:
    is_processed = status == "processed"
    payload = {
        "ok": True,
        "source_root": "artifacts\\portrait-video-source",
        "process_ready": True,
        "pack_count": 1,
        "ready_count": 0,
        "warning_count": 0 if is_processed else 1,
        "waiting_count": 0,
        "insufficient_count": 0,
        "processed_count": 1 if is_processed else 0,
        "failed_count": 0,
        "packs": [
            {
                "set_id": "xingxi-vn-neutral-20260608",
                "source_pack_dir": "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608",
                "frame_count": 60,
                "status": status,
                "output_dir": "artifacts\\portrait-candidate-xingxi-vn-neutral-20260608-motion" if is_processed else "",
                "warnings": [] if is_processed else ["frame_00001.png size 496x744 differs from reference 1024x1536"],
                "errors": [],
            }
        ],
        "errors": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_portrait_video_handoff_report(
    path: Path,
    *,
    missing_zip: bool = False,
    omitted_zip_entries: dict[str, set[str]] | None = None,
) -> Path:
    output_dir = path.parent / "portrait-video-handoff"
    output_dir.mkdir(parents=True, exist_ok=True)
    original_zip = output_dir / "xingxi-vn-neutral-20260608.zip"
    normalized_zip = output_dir / "xingxi-vn-neutral-20260608-normalized.zip"
    omitted_entries = omitted_zip_entries or {}
    _write_video_handoff_zip(
        original_zip,
        omitted_entries=omitted_entries.get("xingxi-vn-neutral-20260608", set()),
    )
    if not missing_zip:
        _write_video_handoff_zip(
            normalized_zip,
            omitted_entries=omitted_entries.get("xingxi-vn-neutral-20260608-normalized", set()),
        )
    payload = {
        "ok": True,
        "source_root": str(path.parent / "portrait-video-source"),
        "output_dir": str(output_dir),
        "pack_count": 2,
        "bundle_count": 2,
        "failed_count": 0,
        "bundles": [
            {
                "set_id": "xingxi-vn-neutral-20260608",
                "source_pack_dir": str(path.parent / "portrait-video-source" / "xingxi-vn-neutral-20260608"),
                "zip_path": str(original_zip),
                "status": "bundled",
                "errors": [],
            },
            {
                "set_id": "xingxi-vn-neutral-20260608-normalized",
                "source_pack_dir": str(
                    path.parent / "portrait-video-source" / "xingxi-vn-neutral-20260608-normalized"
                ),
                "zip_path": str(normalized_zip),
                "status": "bundled",
                "errors": [],
            },
        ],
        "errors": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_video_handoff_zip(path: Path, *, omitted_entries: set[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = {
        "AI_VIDEO_HANDOFF_README.md": b"# AI Video Portrait Handoff\n",
        "gemini_prompt.md": b"Keep identity, same canvas, subtle blink only.",
        "provider_prompts.md": b"Pika/Runway/Krea prompt variants.",
        "source_pack.json": b'{"set_id":"xingxi-vn-neutral-20260608","reference_image":"reference/neutral_open.png"}\n',
        "reference/neutral_open.png": b"png",
    }
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for arcname, content in entries.items():
            if arcname not in omitted_entries:
                archive.writestr(arcname, content)
    return path


def _write_portrait_regeneration_brief_report(
    path: Path,
    *,
    decision_state: str = "regenerate_ai_video",
    blockers: list[str] | None = None,
    reference_exists: bool = True,
    preview_exists: bool = True,
) -> Path:
    source_pack_dir = path.parent / "portrait-video-source" / "xingxi-vn-neutral-20260608-normalized"
    reference_image_path = source_pack_dir / "reference" / "neutral_open.png"
    preview_path = path.parent / "portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.png"
    if reference_exists:
        reference_image_path.parent.mkdir(parents=True, exist_ok=True)
        reference_image_path.write_bytes(b"png")
    if preview_exists:
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_bytes(b"png")
    issue_blockers = blockers
    if issue_blockers is None:
        issue_blockers = [
            "workflow attention: body_drift_warnings",
            "frame visual QA status: ready_with_warnings",
            "max body drift 44.72 exceeds 16.0",
        ]
    payload = {
        "ok": True,
        "workflow_report_path": "artifacts\\portrait-video-workflow-report.json",
        "frame_qa_report_path": "artifacts\\portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.json",
        "set_id": "xingxi-vn-neutral-20260608-normalized",
        "source_pack_dir": str(source_pack_dir),
        "reference_image_path": str(reference_image_path),
        "decision_state": decision_state,
        "frame_status": "ready_with_warnings",
        "frame_count": 60,
        "sampled_frame_count": 12,
        "size_mismatch_count": 0,
        "max_body_drift": 44.72,
        "preview_path": str(preview_path),
        "blockers": issue_blockers,
        "retry_prompt": (
            "Previous attempt failed because body drift was too high: max body drift 44.72 exceeded 16.0. "
            "Use a locked static camera with same canvas, same crop, same full-body framing."
        ),
        "negative_prompt": "No camera movement, zoom, pan, crop, reframing, body recomposition, or pose change.",
        "prompt_constraints": [
            "Keep the exact same canvas, aspect ratio, crop, camera, and full-body framing as the reference.",
            "Only eyelids, tiny chest breathing, and slight hair-tip movement may animate.",
        ],
        "suggested_commands": [
            "python tools\\art\\portrait_video_frame_visual_qa.py artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized --preview artifacts\\portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.png --report artifacts\\portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.json",
        ],
        "errors": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_portrait_retry_handoff_report(
    path: Path,
    *,
    ok: bool = True,
    omitted_zip_entries: set[str] | None = None,
) -> Path:
    zip_path = path.parent / "portrait-video-retry-handoff" / "xingxi-vn-neutral-20260608-normalized-retry.zip"
    if ok:
        _write_retry_handoff_zip(zip_path, omitted_entries=omitted_zip_entries or set())
    payload = {
        "ok": ok,
        "set_id": "xingxi-vn-neutral-20260608-normalized",
        "regeneration_brief_path": "artifacts\\portrait-video-regeneration-brief-xingxi-vn-neutral-20260608-normalized.json",
        "reference_image_path": "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized\\reference\\neutral_open.png",
        "output_dir": str(path.parent / "portrait-video-retry-handoff") if ok else "artifacts\\portrait-video-retry-handoff",
        "zip_path": str(zip_path) if ok else "",
        "errors": [] if ok else ["reference_image_path must point to an existing file"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_retry_handoff_zip(path: Path, *, omitted_entries: set[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = {
        "reference/neutral_open.png": b"png",
        "retry_prompt.txt": b"same canvas, no crop, subtle blink only",
        "negative_prompt.txt": b"no body recomposition, no camera movement",
        "regeneration_brief.json": b'{"set_id":"xingxi-vn-neutral-20260608-normalized"}\n',
        "source_pack_reference.txt": b"source_pack_dir=artifacts/portrait-video-source/xingxi\n",
        "AI_VIDEO_RETRY_README.md": b"# AI Video Retry Handoff\n",
    }
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for arcname, content in entries.items():
            if arcname not in omitted_entries:
                archive.writestr(arcname, content)
    return path


def _write_portrait_video_import_report(
    path: Path,
    *,
    frames_exist: bool = True,
    frame_count: int = 3,
) -> Path:
    source_pack_dir = path.parent / "portrait-video-source" / "xingxi-vn-neutral-20260608"
    video_path = source_pack_dir / "video" / "pika.mp4"
    frames_dir = source_pack_dir / "frames"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"video")
    if frames_exist:
        frames_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, frame_count + 1):
            (frames_dir / f"frame_{index:05d}.png").write_bytes(b"png")
    payload = {
        "ok": True,
        "set_id": "xingxi-vn-neutral-20260608",
        "source_pack_dir": str(source_pack_dir),
        "input_video_path": str(path.parent / "downloads" / "pika.mp4"),
        "copied_video_path": str(video_path),
        "frames_dir": str(frames_dir),
        "report_path": str(path),
        "source_tool": "Pika",
        "fps": 12,
        "replace_frames": False,
        "frame_count": frame_count,
        "next_commands": [
            "python tools\\art\\inspect_portrait_video_source_frames.py artifacts\\portrait-video-source --report artifacts\\portrait-video-frame-preflight.json",
        ],
        "errors": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_full_local_snapshot_artifacts(root: Path) -> Path:
    (root / "llm_smoke").mkdir(parents=True, exist_ok=True)
    candidate_root = root / "portrait-candidate-xingxi-vn-20260607"
    candidate_root.mkdir(parents=True, exist_ok=True)
    _write_llm_report(root / "llm_smoke" / "deepseek-expression-cue-probe-20260609-rerun.json", ok=True)
    _write_llm_report(root / "llm_smoke" / "deepseek-speech-quality-live-20260609-rerun.json", ok=True)
    _write_portrait_candidate_report(candidate_root / "portrait-decision-brief.json")
    _write_portrait_workflow_report(root / "portrait-video-workflow-report.json")
    _write_portrait_source_create_report(root / "portrait-video-source-create-report.json")
    _write_liveportrait_preflight_report(root / "liveportrait-preflight-xingxi-vn-neutral.json")
    _write_portrait_video_handoff_report(root / "portrait-video-handoff-report.json")
    _write_portrait_frame_preflight_report(root / "portrait-video-frame-preflight.json")
    _write_portrait_frame_normalization_report(root / "portrait-video-frame-normalization.json")
    _write_portrait_source_batch_report(root / "portrait-video-source-batch-report.json")
    _write_portrait_frame_qa_report(root / "portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.json")
    _write_portrait_regeneration_brief_report(
        root / "portrait-video-regeneration-brief-xingxi-vn-neutral-20260608-normalized.json"
    )
    _write_portrait_retry_handoff_report(root / "portrait-video-retry-handoff-report.json")
    return root


def _run_tool(
    character_pack: Path,
    app_dir: Path,
    installer: Path,
    tmp_path: Path,
    *,
    llm_reports: list[Path] | None = None,
    portrait_workflow_reports: list[Path] | None = None,
    portrait_candidate_reports: list[Path] | None = None,
    portrait_source_create_reports: list[Path] | None = None,
    liveportrait_preflight_reports: list[Path] | None = None,
    portrait_frame_preflight_reports: list[Path] | None = None,
    portrait_frame_normalization_reports: list[Path] | None = None,
    portrait_source_batch_reports: list[Path] | None = None,
    portrait_video_handoff_reports: list[Path] | None = None,
    portrait_frame_qa_reports: list[Path] | None = None,
    portrait_regeneration_brief_reports: list[Path] | None = None,
    portrait_retry_handoff_reports: list[Path] | None = None,
    portrait_video_import_reports: list[Path] | None = None,
    full_local_snapshot: bool = False,
    snapshot_artifact_root: Path | None = None,
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
    for report in portrait_source_create_reports or []:
        args.extend(["--portrait-source-create-report", str(report)])
    for report in liveportrait_preflight_reports or []:
        args.extend(["--liveportrait-preflight-report", str(report)])
    for report in portrait_frame_preflight_reports or []:
        args.extend(["--portrait-frame-preflight-report", str(report)])
    for report in portrait_frame_normalization_reports or []:
        args.extend(["--portrait-frame-normalization-report", str(report)])
    for report in portrait_source_batch_reports or []:
        args.extend(["--portrait-source-batch-report", str(report)])
    for report in portrait_video_handoff_reports or []:
        args.extend(["--portrait-video-handoff-report", str(report)])
    for report in portrait_frame_qa_reports or []:
        args.extend(["--portrait-frame-qa-report", str(report)])
    for report in portrait_regeneration_brief_reports or []:
        args.extend(["--portrait-regeneration-brief-report", str(report)])
    for report in portrait_retry_handoff_reports or []:
        args.extend(["--portrait-retry-handoff-report", str(report)])
    for report in portrait_video_import_reports or []:
        args.extend(["--portrait-video-import-report", str(report)])
    if full_local_snapshot:
        args.append("--full-local-snapshot")
    if snapshot_artifact_root is not None:
        args.extend(["--snapshot-artifact-root", str(snapshot_artifact_root)])
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
    assert payload["check_count"] == 2
    assert payload["ready_check_count"] == 2
    assert payload["attention_check_count"] == 0
    assert payload["attention_checks"] == []
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
    assert "- Ready checks: `2`" in markdown
    assert "- Attention checks: `0`" in markdown
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
    assert payload["check_count"] == 3
    assert payload["ready_check_count"] == 2
    assert payload["attention_check_count"] == 1
    assert payload["attention_checks"] == [
        {
            "id": "llm_report_directory",
            "label": "LLM Smoke Report Directory",
            "status": "needs_attention",
            "next_actions": ["review LLM smoke artifact directory before release"],
        }
    ]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "## Attention Checks" in markdown
    assert (
        "- `LLM Smoke Report Directory` (`needs_attention`): "
        "`review LLM smoke artifact directory before release`"
    ) in markdown
    assert "- Reports needing attention:" in markdown
    assert (
        "  - `llm-cue-failing.json: needs_attention, issues=2, "
        "reason=cue:sadness:expected_expression:sadness`"
    ) in markdown


def test_release_readiness_report_full_local_snapshot_preset_uses_current_artifacts(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    artifact_root = _write_full_local_snapshot_artifacts(tmp_path / "artifacts")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        full_local_snapshot=True,
        snapshot_artifact_root=artifact_root,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["status"] == "needs_attention"
    assert payload["check_count"] == 15
    assert payload["ready_check_count"] == 8
    assert payload["attention_check_count"] == 7
    assert [item["id"] for item in payload["attention_checks"]] == [
        "portrait_video_workflow",
        "portrait_candidate_decision",
        "liveportrait_preflight",
        "portrait_frame_preflight",
        "portrait_source_batch",
        "portrait_frame_visual_qa",
        "portrait_video_regeneration_brief",
    ]
    assert [check["id"] for check in payload["checks"]] == [
        "source_character_pack",
        "windows_build",
        "llm_report",
        "llm_report",
        "portrait_video_workflow",
        "portrait_candidate_decision",
        "portrait_source_create",
        "liveportrait_preflight",
        "portrait_frame_preflight",
        "portrait_frame_normalization",
        "portrait_source_batch",
        "portrait_video_handoff",
        "portrait_frame_visual_qa",
        "portrait_video_regeneration_brief",
        "portrait_video_retry_handoff",
    ]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "- Checks: `15`" in markdown
    assert "- Ready checks: `8`" in markdown
    assert "- Attention checks: `7`" in markdown
    assert "## Attention Checks" in markdown


def test_release_readiness_report_full_local_snapshot_includes_existing_video_import_report(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    artifact_root = _write_full_local_snapshot_artifacts(tmp_path / "artifacts")
    _write_portrait_video_import_report(
        artifact_root / "portrait-video-source" / "xingxi-vn-neutral-20260608" / "video_import_report.json"
    )

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        full_local_snapshot=True,
        snapshot_artifact_root=artifact_root,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["status"] == "needs_attention"
    assert payload["check_count"] == 16
    assert payload["ready_check_count"] == 9
    assert payload["attention_check_count"] == 7
    assert "portrait_video_import" in [check["id"] for check in payload["checks"]]
    import_check = next(check for check in payload["checks"] if check["id"] == "portrait_video_import")
    assert import_check["ok"] is True
    assert import_check["status"] == "ready"
    assert import_check["frame_count"] == 3


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


def test_release_readiness_report_accepts_portrait_source_create(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    source_create = _write_portrait_source_create_report(tmp_path / "portrait-source-create.json")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_source_create_reports=[source_create],
    )

    payload = json.loads(result.stdout)
    create_check = payload["checks"][2]
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert create_check["id"] == "portrait_source_create"
    assert create_check["ok"] is True
    assert create_check["status"] == "ready"
    assert create_check["requested_count"] == 1
    assert create_check["created_count"] == 1
    assert create_check["failed_count"] == 0
    assert create_check["source_create_summaries"] == [
        "xingxi-vn-neutral-20260608: created, expression=neutral, variant=open, "
        f"output={tmp_path / 'portrait-video-source' / 'xingxi-vn-neutral-20260608'}"
    ]
    assert create_check["source_pack_content_summaries"] == [
        "xingxi-vn-neutral-20260608: source_pack.json, gemini_prompt.md, provider_prompts.md, reference/neutral_open.png, frames/, video/"
    ]
    assert create_check["next_actions"] == []
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### Portrait Source Create" in markdown
    assert "- Candidate manifest:" in markdown
    assert "- Output root:" in markdown
    assert "- Requested packs: `1`" in markdown
    assert "- Created packs: `1`" in markdown
    assert "- Failed packs: `0`" in markdown
    assert "- Source create packs:" in markdown
    assert "xingxi-vn-neutral-20260608: created, expression=neutral, variant=open" in markdown
    assert "- Source pack contents:" in markdown
    assert "provider_prompts.md" in markdown


def test_release_readiness_report_surfaces_portrait_source_create_content_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    source_create = _write_portrait_source_create_report(
        tmp_path / "portrait-source-create.json",
        omitted_source_pack_paths={"provider_prompts.md"},
    )

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_source_create_reports=[source_create],
    )

    payload = json.loads(result.stdout)
    create_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert create_check["id"] == "portrait_source_create"
    assert create_check["ok"] is False
    assert create_check["status"] == "needs_attention"
    assert create_check["errors"] == [
        "xingxi-vn-neutral-20260608: source pack missing required file: provider_prompts.md"
    ]
    assert create_check["next_actions"] == [
        "create or repair portrait AI-video source packs before provider handoff"
    ]


def test_release_readiness_report_surfaces_liveportrait_preflight_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    liveportrait_report = _write_liveportrait_preflight_report(tmp_path / "liveportrait-preflight.json")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        liveportrait_preflight_reports=[liveportrait_report],
    )

    payload = json.loads(result.stdout)
    preflight_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert preflight_check["id"] == "liveportrait_preflight"
    assert preflight_check["ok"] is False
    assert preflight_check["status"] == "download_liveportrait_weights"
    assert preflight_check["driving_status"] == "missing"
    assert preflight_check["missing_weight_count"] == 2
    assert preflight_check["missing_weight_paths"] == [
        "pretrained_weights/liveportrait/base_models/appearance_feature_extractor.pth",
        "pretrained_weights/liveportrait/base_models/motion_extractor.pth",
    ]
    assert preflight_check["errors"] == [
        "required pretrained weights are missing",
        "driving video or motion template not found",
    ]
    assert preflight_check["suggested_commands"] == [
        "Push-Location tmp\\liveportrait_research\\LivePortrait; huggingface-cli download KlingTeam/LivePortrait --local-dir pretrained_weights --exclude \"*.git*\" \"README.md\" \"docs\"; Pop-Location",
        "New-Item -ItemType Directory -Force tmp\\liveportrait_research\\drivers",
    ]
    assert "resolve LivePortrait preflight blockers before local inference" in payload["next_actions"]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### LivePortrait Preflight" in markdown
    assert "- Driving status: `missing`" in markdown
    assert "- Missing weights: `2`" in markdown
    assert "- Missing weight paths:" in markdown
    assert "  - `pretrained_weights/liveportrait/base_models/appearance_feature_extractor.pth`" in markdown
    assert "- Suggested commands:" in markdown
    assert "  - `New-Item -ItemType Directory -Force tmp\\liveportrait_research\\drivers`" in markdown


def test_release_readiness_report_surfaces_portrait_frame_visual_qa_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    frame_qa_report = _write_portrait_frame_qa_report(tmp_path / "portrait-frame-qa.json")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_frame_qa_reports=[frame_qa_report],
    )

    payload = json.loads(result.stdout)
    frame_qa_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert frame_qa_check["id"] == "portrait_frame_visual_qa"
    assert frame_qa_check["ok"] is False
    assert frame_qa_check["status"] == "ready_with_warnings"
    assert frame_qa_check["set_id"] == "xingxi-vn-neutral-20260608-normalized"
    assert frame_qa_check["preview_path"] == str(tmp_path / "portrait-frame-qa-preview.png")
    assert frame_qa_check["frame_count"] == 60
    assert frame_qa_check["sampled_frame_count"] == 12
    assert frame_qa_check["size_mismatch_count"] == 0
    assert frame_qa_check["max_body_drift"] == 44.72
    assert frame_qa_check["next_actions"] == [
        "review portrait AI-video frame visual QA before motion extraction"
    ]
    assert "review portrait AI-video frame visual QA before motion extraction" in payload["next_actions"]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### Portrait Frame Visual QA" in markdown
    assert "- Set: `xingxi-vn-neutral-20260608-normalized`" in markdown
    assert f"- Preview: `{tmp_path / 'portrait-frame-qa-preview.png'}`" in markdown
    assert "- Frames: `60`" in markdown
    assert "- Sampled frames: `12`" in markdown
    assert "- Max body drift: `44.72`" in markdown


def test_release_readiness_report_surfaces_portrait_frame_visual_qa_missing_preview(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    frame_qa_report = _write_portrait_frame_qa_report(
        tmp_path / "portrait-frame-qa.json",
        status="ready",
        preview_exists=False,
    )

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_frame_qa_reports=[frame_qa_report],
    )

    payload = json.loads(result.stdout)
    frame_qa_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert frame_qa_check["id"] == "portrait_frame_visual_qa"
    assert frame_qa_check["ok"] is False
    assert frame_qa_check["status"] == "needs_attention"
    assert frame_qa_check["errors"] == [
        f"frame visual QA preview not found: {tmp_path / 'portrait-frame-qa-preview.png'}"
    ]
    assert frame_qa_check["next_actions"] == [
        "review portrait AI-video frame visual QA before motion extraction"
    ]


def test_release_readiness_report_accepts_ready_portrait_frame_preflight(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    frame_preflight = _write_portrait_frame_preflight_report(tmp_path / "portrait-frame-preflight.json", status="ready")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_frame_preflight_reports=[frame_preflight],
    )

    payload = json.loads(result.stdout)
    preflight_check = payload["checks"][2]
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert preflight_check["id"] == "portrait_frame_preflight"
    assert preflight_check["ok"] is True
    assert preflight_check["status"] == "ready"
    assert preflight_check["source_root"] == "artifacts\\portrait-video-source"
    assert preflight_check["pack_count"] == 1
    assert preflight_check["ready_count"] == 1
    assert preflight_check["warning_pack_count"] == 0
    assert preflight_check["item_summaries"] == [
        "xingxi-vn-neutral-20260608-normalized: ready, next_action=process_frames, frames=60"
    ]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### Portrait Frame Preflight" in markdown
    assert "- Source root: `artifacts\\portrait-video-source`" in markdown
    assert "- Ready packs: `1`" in markdown
    assert "- Frame preflight items:" in markdown
    assert "  - `xingxi-vn-neutral-20260608-normalized: ready, next_action=process_frames, frames=60`" in markdown


def test_release_readiness_report_surfaces_portrait_frame_preflight_warnings(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    frame_preflight = _write_portrait_frame_preflight_report(tmp_path / "portrait-frame-preflight.json")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_frame_preflight_reports=[frame_preflight],
    )

    payload = json.loads(result.stdout)
    preflight_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert preflight_check["id"] == "portrait_frame_preflight"
    assert preflight_check["ok"] is False
    assert preflight_check["status"] == "needs_attention"
    assert preflight_check["pack_count"] == 1
    assert preflight_check["ready_count"] == 0
    assert preflight_check["warning_pack_count"] == 1
    assert preflight_check["item_summaries"] == [
        "xingxi-vn-neutral-20260608-normalized: ready_with_warnings, next_action=review_frame_warnings, frames=60"
    ]
    assert preflight_check["next_actions"] == [
        "resolve portrait AI-video frame preflight warnings before motion extraction"
    ]
    assert "resolve portrait AI-video frame preflight warnings before motion extraction" in payload["next_actions"]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "- Warning packs: `1`" in markdown
    assert "ready_with_warnings, next_action=review_frame_warnings" in markdown


def test_release_readiness_report_accepts_portrait_frame_normalization(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    normalization = _write_portrait_frame_normalization_report(tmp_path / "portrait-frame-normalization.json")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_frame_normalization_reports=[normalization],
    )

    payload = json.loads(result.stdout)
    normalization_check = payload["checks"][2]
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert normalization_check["id"] == "portrait_frame_normalization"
    assert normalization_check["ok"] is True
    assert normalization_check["status"] == "completed"
    assert normalization_check["source_set_id"] == "xingxi-vn-neutral-20260608"
    assert normalization_check["set_id"] == "xingxi-vn-neutral-20260608-normalized"
    assert normalization_check["input_frame_count"] == 60
    assert normalization_check["normalized_frame_count"] == 60
    assert normalization_check["resized_frame_count"] == 60
    assert normalization_check["invalid_frame_count"] == 0
    assert normalization_check["aspect_mismatch_count"] == 0
    assert normalization_check["next_actions"] == []
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### Portrait Frame Normalization" in markdown
    assert "- Source set: `xingxi-vn-neutral-20260608`" in markdown
    assert "- Set: `xingxi-vn-neutral-20260608-normalized`" in markdown
    assert "- Normalized frames: `60`" in markdown
    assert "- Resized frames: `60`" in markdown


def test_release_readiness_report_surfaces_portrait_frame_normalization_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    normalization = _write_portrait_frame_normalization_report(tmp_path / "portrait-frame-normalization.json", ok=False)

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_frame_normalization_reports=[normalization],
    )

    payload = json.loads(result.stdout)
    normalization_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert normalization_check["id"] == "portrait_frame_normalization"
    assert normalization_check["ok"] is False
    assert normalization_check["status"] == "needs_attention"
    assert normalization_check["invalid_frame_count"] == 1
    assert normalization_check["aspect_mismatch_count"] == 1
    assert normalization_check["errors"] == ["frame_00001.png aspect ratio differs from reference"]
    assert normalization_check["next_actions"] == [
        "repair portrait AI-video frame normalization before preflight rerun"
    ]
    assert "repair portrait AI-video frame normalization before preflight rerun" in payload["next_actions"]


def test_release_readiness_report_accepts_processed_portrait_source_batch(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    source_batch = _write_portrait_source_batch_report(tmp_path / "portrait-source-batch.json", status="processed")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_source_batch_reports=[source_batch],
    )

    payload = json.loads(result.stdout)
    batch_check = payload["checks"][2]
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert batch_check["id"] == "portrait_source_batch"
    assert batch_check["ok"] is True
    assert batch_check["status"] == "ready"
    assert batch_check["process_ready"] is True
    assert batch_check["pack_count"] == 1
    assert batch_check["processed_count"] == 1
    assert batch_check["warning_pack_count"] == 0
    assert batch_check["source_batch_summaries"] == [
        "xingxi-vn-neutral-20260608: processed, frames=60, output=artifacts\\portrait-candidate-xingxi-vn-neutral-20260608-motion"
    ]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### Portrait Source Batch" in markdown
    assert "- Process ready requested: `yes`" in markdown
    assert "- Processed packs: `1`" in markdown
    assert "- Source batch packs:" in markdown
    assert "  - `xingxi-vn-neutral-20260608: processed, frames=60" in markdown


def test_release_readiness_report_surfaces_portrait_source_batch_warnings(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    source_batch = _write_portrait_source_batch_report(tmp_path / "portrait-source-batch.json")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_source_batch_reports=[source_batch],
    )

    payload = json.loads(result.stdout)
    batch_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert batch_check["id"] == "portrait_source_batch"
    assert batch_check["ok"] is False
    assert batch_check["status"] == "needs_attention"
    assert batch_check["process_ready"] is True
    assert batch_check["processed_count"] == 0
    assert batch_check["warning_pack_count"] == 1
    assert batch_check["source_batch_summaries"] == [
        "xingxi-vn-neutral-20260608: ready_with_warnings, frames=60"
    ]
    assert batch_check["next_actions"] == [
        "resolve portrait AI-video source batch warnings before motion extraction"
    ]
    assert "resolve portrait AI-video source batch warnings before motion extraction" in payload["next_actions"]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "- Warning packs: `1`" in markdown
    assert "ready_with_warnings, frames=60" in markdown


def test_release_readiness_report_accepts_portrait_video_handoff(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    handoff = _write_portrait_video_handoff_report(tmp_path / "portrait-video-handoff-report.json")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_video_handoff_reports=[handoff],
    )

    payload = json.loads(result.stdout)
    handoff_check = payload["checks"][2]
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert handoff_check["id"] == "portrait_video_handoff"
    assert handoff_check["ok"] is True
    assert handoff_check["status"] == "ready"
    assert handoff_check["pack_count"] == 2
    assert handoff_check["bundle_count"] == 2
    assert handoff_check["handoff_failed_count"] == 0
    assert handoff_check["handoff_bundle_summaries"] == [
        "xingxi-vn-neutral-20260608: bundled, zip="
        + str(tmp_path / "portrait-video-handoff" / "xingxi-vn-neutral-20260608.zip"),
        "xingxi-vn-neutral-20260608-normalized: bundled, zip="
        + str(tmp_path / "portrait-video-handoff" / "xingxi-vn-neutral-20260608-normalized.zip"),
    ]
    assert handoff_check["handoff_bundle_zip_summaries"] == [
        "xingxi-vn-neutral-20260608: entries=AI_VIDEO_HANDOFF_README.md, gemini_prompt.md, provider_prompts.md, reference/neutral_open.png, source_pack.json",
        "xingxi-vn-neutral-20260608-normalized: entries=AI_VIDEO_HANDOFF_README.md, gemini_prompt.md, provider_prompts.md, reference/neutral_open.png, source_pack.json",
    ]
    assert handoff_check["next_actions"] == []
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### Portrait Video Handoff" in markdown
    assert "- Bundles: `2`" in markdown
    assert "- Failed bundles: `0`" in markdown
    assert "- Handoff bundles:" in markdown
    assert "xingxi-vn-neutral-20260608-normalized: bundled" in markdown
    assert "- Handoff bundle zip entries:" in markdown
    assert "provider_prompts.md" in markdown


def test_release_readiness_report_surfaces_portrait_video_handoff_zip_content_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    handoff = _write_portrait_video_handoff_report(
        tmp_path / "portrait-video-handoff-report.json",
        omitted_zip_entries={
            "xingxi-vn-neutral-20260608-normalized": {"provider_prompts.md"},
        },
    )

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_video_handoff_reports=[handoff],
    )

    payload = json.loads(result.stdout)
    handoff_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert handoff_check["id"] == "portrait_video_handoff"
    assert handoff_check["ok"] is False
    assert handoff_check["status"] == "needs_attention"
    assert handoff_check["errors"] == [
        "xingxi-vn-neutral-20260608-normalized: handoff zip missing required entry: provider_prompts.md"
    ]
    assert handoff_check["next_actions"] == [
        "create or repair portrait AI-video handoff zips before manual provider upload"
    ]


def test_release_readiness_report_surfaces_portrait_video_handoff_missing_zip(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    handoff = _write_portrait_video_handoff_report(
        tmp_path / "portrait-video-handoff-report.json",
        missing_zip=True,
    )

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_video_handoff_reports=[handoff],
    )

    payload = json.loads(result.stdout)
    handoff_check = payload["checks"][2]
    missing_zip = str(tmp_path / "portrait-video-handoff" / "xingxi-vn-neutral-20260608-normalized.zip")
    assert result.returncode == 1
    assert payload["ok"] is False
    assert handoff_check["id"] == "portrait_video_handoff"
    assert handoff_check["ok"] is False
    assert handoff_check["status"] == "needs_attention"
    assert f"handoff zip not found: {missing_zip}" in handoff_check["errors"]
    assert handoff_check["next_actions"] == [
        "create or repair portrait AI-video handoff zips before manual provider upload"
    ]
    assert "create or repair portrait AI-video handoff zips before manual provider upload" in payload["next_actions"]


def test_release_readiness_report_surfaces_portrait_regeneration_brief_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    regeneration_brief = _write_portrait_regeneration_brief_report(tmp_path / "portrait-regeneration-brief.json")
    report_payload = json.loads(regeneration_brief.read_text(encoding="utf-8"))

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_regeneration_brief_reports=[regeneration_brief],
    )

    payload = json.loads(result.stdout)
    regeneration_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert regeneration_check["id"] == "portrait_video_regeneration_brief"
    assert regeneration_check["ok"] is False
    assert regeneration_check["status"] == "regenerate_ai_video"
    assert regeneration_check["set_id"] == "xingxi-vn-neutral-20260608-normalized"
    assert regeneration_check["source_pack_dir"] == report_payload["source_pack_dir"]
    assert regeneration_check["reference_image_path"] == report_payload["reference_image_path"]
    assert regeneration_check["preview_path"] == report_payload["preview_path"]
    assert regeneration_check["decision_state"] == "regenerate_ai_video"
    assert regeneration_check["frame_status"] == "ready_with_warnings"
    assert regeneration_check["frame_count"] == 60
    assert regeneration_check["sampled_frame_count"] == 12
    assert regeneration_check["max_body_drift"] == 44.72
    assert "max body drift 44.72 exceeds 16.0" in regeneration_check["blockers"]
    assert "Previous attempt failed because body drift was too high" in regeneration_check["retry_prompt"]
    assert "body recomposition" in regeneration_check["negative_prompt"]
    assert regeneration_check["next_actions"] == [
        "regenerate portrait AI-video using the brief retry prompts before motion extraction"
    ]
    assert "regenerate portrait AI-video using the brief retry prompts before motion extraction" in payload["next_actions"]
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### Portrait Video Regeneration Brief" in markdown
    assert f"- Source pack: `{report_payload['source_pack_dir']}`" in markdown
    assert f"- Reference image: `{report_payload['reference_image_path']}`" in markdown
    assert "- Decision state: `regenerate_ai_video`" in markdown
    assert "- Frame status: `ready_with_warnings`" in markdown
    assert f"- Preview: `{report_payload['preview_path']}`" in markdown
    assert "- Max body drift: `44.72`" in markdown
    assert "- Retry prompt:" in markdown
    assert "Previous attempt failed because body drift was too high" in markdown
    assert "- Negative prompt:" in markdown
    assert "body recomposition" in markdown


def test_release_readiness_report_blocks_portrait_regeneration_brief_missing_reference(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    regeneration_brief = _write_portrait_regeneration_brief_report(
        tmp_path / "portrait-regeneration-brief.json",
        decision_state="process_frames",
        blockers=[],
        reference_exists=False,
    )
    report_payload = json.loads(regeneration_brief.read_text(encoding="utf-8"))

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_regeneration_brief_reports=[regeneration_brief],
    )

    payload = json.loads(result.stdout)
    regeneration_check = payload["checks"][2]
    expected_error = f"regeneration reference image not found: {report_payload['reference_image_path']}"
    assert result.returncode == 1
    assert payload["ok"] is False
    assert regeneration_check["id"] == "portrait_video_regeneration_brief"
    assert regeneration_check["ok"] is False
    assert regeneration_check["status"] == "needs_attention"
    assert expected_error in regeneration_check["errors"]
    assert "review portrait AI-video regeneration brief before release" in payload["next_actions"]


def test_release_readiness_report_blocks_portrait_regeneration_brief_missing_preview(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    regeneration_brief = _write_portrait_regeneration_brief_report(
        tmp_path / "portrait-regeneration-brief.json",
        decision_state="process_frames",
        blockers=[],
        preview_exists=False,
    )
    report_payload = json.loads(regeneration_brief.read_text(encoding="utf-8"))

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_regeneration_brief_reports=[regeneration_brief],
    )

    payload = json.loads(result.stdout)
    regeneration_check = payload["checks"][2]
    expected_error = f"regeneration frame QA preview not found: {report_payload['preview_path']}"
    assert result.returncode == 1
    assert payload["ok"] is False
    assert regeneration_check["id"] == "portrait_video_regeneration_brief"
    assert regeneration_check["ok"] is False
    assert regeneration_check["status"] == "needs_attention"
    assert expected_error in regeneration_check["errors"]
    assert "review portrait AI-video regeneration brief before release" in payload["next_actions"]


def test_release_readiness_report_surfaces_portrait_video_import(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    import_report = _write_portrait_video_import_report(tmp_path / "video-import-report.json")
    report_payload = json.loads(import_report.read_text(encoding="utf-8"))

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_video_import_reports=[import_report],
    )

    payload = json.loads(result.stdout)
    import_check = payload["checks"][2]
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert import_check["id"] == "portrait_video_import"
    assert import_check["ok"] is True
    assert import_check["status"] == "ready"
    assert import_check["set_id"] == "xingxi-vn-neutral-20260608"
    assert import_check["source_pack_dir"] == report_payload["source_pack_dir"]
    assert import_check["copied_video_path"] == report_payload["copied_video_path"]
    assert import_check["frames_dir"] == report_payload["frames_dir"]
    assert import_check["frame_count"] == 3
    assert import_check["source_tool"] == "Pika"
    assert import_check["next_actions"] == []
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### Portrait Video Import" in markdown
    assert f"- Source pack: `{report_payload['source_pack_dir']}`" in markdown
    assert f"- Copied video: `{report_payload['copied_video_path']}`" in markdown
    assert f"- Frames dir: `{report_payload['frames_dir']}`" in markdown
    assert "- Frames: `3`" in markdown


def test_release_readiness_report_blocks_portrait_video_import_missing_frames(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    import_report = _write_portrait_video_import_report(
        tmp_path / "video-import-report.json",
        frames_exist=False,
    )
    report_payload = json.loads(import_report.read_text(encoding="utf-8"))

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_video_import_reports=[import_report],
    )

    payload = json.loads(result.stdout)
    import_check = payload["checks"][2]
    expected_error = f"video import frames_dir not found: {report_payload['frames_dir']}"
    assert result.returncode == 1
    assert payload["ok"] is False
    assert import_check["id"] == "portrait_video_import"
    assert import_check["ok"] is False
    assert import_check["status"] == "needs_attention"
    assert expected_error in import_check["errors"]
    assert "repair portrait AI-video import before frame preflight" in payload["next_actions"]


def test_release_readiness_report_surfaces_portrait_retry_handoff(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    retry_handoff = _write_portrait_retry_handoff_report(tmp_path / "portrait-retry-handoff.json")

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_retry_handoff_reports=[retry_handoff],
    )

    payload = json.loads(result.stdout)
    retry_check = payload["checks"][2]
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert retry_check["id"] == "portrait_video_retry_handoff"
    assert retry_check["ok"] is True
    assert retry_check["status"] == "ready"
    assert retry_check["set_id"] == "xingxi-vn-neutral-20260608-normalized"
    assert (
        retry_check["regeneration_brief_path"]
        == "artifacts\\portrait-video-regeneration-brief-xingxi-vn-neutral-20260608-normalized.json"
    )
    assert (
        retry_check["reference_image_path"]
        == "artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized\\reference\\neutral_open.png"
    )
    assert retry_check["output_dir"] == str(tmp_path / "portrait-video-retry-handoff")
    assert retry_check["zip_path"] == str(
        tmp_path / "portrait-video-retry-handoff" / "xingxi-vn-neutral-20260608-normalized-retry.zip"
    )
    assert retry_check["retry_handoff_zip_entries"] == [
        "AI_VIDEO_RETRY_README.md",
        "negative_prompt.txt",
        "reference/neutral_open.png",
        "regeneration_brief.json",
        "retry_prompt.txt",
        "source_pack_reference.txt",
    ]
    assert retry_check["next_actions"] == []
    markdown = (tmp_path / "readiness.md").read_text(encoding="utf-8")
    assert "### Portrait Video Retry Handoff" in markdown
    assert "- Set: `xingxi-vn-neutral-20260608-normalized`" in markdown
    assert (
        "- Regeneration brief: `artifacts\\portrait-video-regeneration-brief-xingxi-vn-neutral-20260608-normalized.json`"
        in markdown
    )
    assert (
        f"- Retry handoff zip: `{tmp_path / 'portrait-video-retry-handoff' / 'xingxi-vn-neutral-20260608-normalized-retry.zip'}`"
        in markdown
    )
    assert "- Retry handoff zip entries:" in markdown
    assert "  - `negative_prompt.txt`" in markdown


def test_release_readiness_report_surfaces_portrait_retry_handoff_zip_content_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    retry_handoff = _write_portrait_retry_handoff_report(
        tmp_path / "portrait-retry-handoff.json",
        omitted_zip_entries={"negative_prompt.txt"},
    )

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_retry_handoff_reports=[retry_handoff],
    )

    payload = json.loads(result.stdout)
    retry_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert retry_check["id"] == "portrait_video_retry_handoff"
    assert retry_check["ok"] is False
    assert retry_check["status"] == "needs_attention"
    assert retry_check["errors"] == ["retry handoff zip missing required entry: negative_prompt.txt"]
    assert retry_check["next_actions"] == [
        "create or repair portrait AI-video retry handoff zip before manual provider upload"
    ]


def test_release_readiness_report_surfaces_portrait_retry_handoff_issue(tmp_path: Path):
    character_pack = _copy_original_pack(tmp_path / "source")
    app_dir, installer = _write_frozen_build(tmp_path / "build")
    retry_handoff = _write_portrait_retry_handoff_report(tmp_path / "portrait-retry-handoff.json", ok=False)

    result = _run_tool(
        character_pack,
        app_dir,
        installer,
        tmp_path,
        portrait_retry_handoff_reports=[retry_handoff],
    )

    payload = json.loads(result.stdout)
    retry_check = payload["checks"][2]
    assert result.returncode == 1
    assert payload["ok"] is False
    assert retry_check["id"] == "portrait_video_retry_handoff"
    assert retry_check["ok"] is False
    assert retry_check["status"] == "needs_attention"
    assert retry_check["errors"] == [
        "reference_image_path must point to an existing file",
        "retry handoff zip_path is missing",
    ]
    assert retry_check["next_actions"] == [
        "create or repair portrait AI-video retry handoff zip before manual provider upload"
    ]
    assert "create or repair portrait AI-video retry handoff zip before manual provider upload" in payload["next_actions"]
