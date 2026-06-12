from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections.abc import Iterable
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.review_character_pack_status import review_character_pack_status
from tools.review_llm_smoke_report import review_llm_smoke_report, review_llm_smoke_reports_in_directory
from tools.validate_windows_build import DEFAULT_APP_DIR, DEFAULT_INSTALLER, validate_windows_build


DEFAULT_CHARACTER_PACK = REPO_ROOT / "assets" / "companion" / "original_oc"
DEFAULT_SNAPSHOT_ARTIFACT_ROOT = Path("artifacts")
REQUIRED_SOURCE_PACK_FILES = ("source_pack.json", "gemini_prompt.md", "provider_prompts.md")
REQUIRED_SOURCE_PACK_DIRS = ("reference", "frames", "video")
REQUIRED_VIDEO_HANDOFF_ZIP_ENTRIES = frozenset(
    {
        "AI_VIDEO_HANDOFF_README.md",
        "gemini_prompt.md",
        "provider_prompts.md",
        "source_pack.json",
    }
)
REQUIRED_RETRY_HANDOFF_ZIP_ENTRIES = frozenset(
    {
        "AI_VIDEO_RETRY_README.md",
        "negative_prompt.txt",
        "reference/neutral_open.png",
        "regeneration_brief.json",
        "retry_prompt.txt",
        "source_pack_reference.txt",
    }
)
FULL_LOCAL_SNAPSHOT_REPORT_KEYS = (
    "llm_reports",
    "portrait_workflow_reports",
    "portrait_candidate_reports",
    "portrait_source_create_reports",
    "liveportrait_preflight_reports",
    "portrait_frame_preflight_reports",
    "portrait_frame_normalization_reports",
    "portrait_source_batch_reports",
    "portrait_source_process_reports",
    "portrait_video_handoff_reports",
    "portrait_video_import_reports",
    "portrait_frame_qa_reports",
    "portrait_regeneration_brief_reports",
    "portrait_retry_handoff_reports",
    "hatch_pet_imagegen_readiness_reports",
    "hatch_pet_imagegen_route_preflight_reports",
    "hatch_pet_base_intake_reports",
    "pixel_pet_emote_mapping_reports",
    "pixel_pet_visual_qa_reports",
    "pixel_pet_edge_style_brief_reports",
)


def build_release_readiness_report(
    *,
    character_pack: Path | str = DEFAULT_CHARACTER_PACK,
    app_dir: Path | str = DEFAULT_APP_DIR,
    installer_path: Path | str | None = DEFAULT_INSTALLER,
    llm_reports: Iterable[Path | str] = (),
    portrait_workflow_reports: Iterable[Path | str] = (),
    portrait_candidate_reports: Iterable[Path | str] = (),
    portrait_source_create_reports: Iterable[Path | str] = (),
    liveportrait_preflight_reports: Iterable[Path | str] = (),
    portrait_frame_preflight_reports: Iterable[Path | str] = (),
    portrait_frame_normalization_reports: Iterable[Path | str] = (),
    portrait_source_batch_reports: Iterable[Path | str] = (),
    portrait_source_process_reports: Iterable[Path | str] = (),
    portrait_video_handoff_reports: Iterable[Path | str] = (),
    portrait_video_import_reports: Iterable[Path | str] = (),
    portrait_frame_qa_reports: Iterable[Path | str] = (),
    portrait_regeneration_brief_reports: Iterable[Path | str] = (),
    portrait_retry_handoff_reports: Iterable[Path | str] = (),
    hatch_pet_imagegen_readiness_reports: Iterable[Path | str] = (),
    hatch_pet_imagegen_route_preflight_reports: Iterable[Path | str] = (),
    hatch_pet_base_intake_reports: Iterable[Path | str] = (),
    pixel_pet_emote_mapping_reports: Iterable[Path | str] = (),
    pixel_pet_visual_qa_reports: Iterable[Path | str] = (),
    pixel_pet_edge_style_brief_reports: Iterable[Path | str] = (),
) -> dict[str, object]:
    source_check = _source_character_pack_check(Path(character_pack))
    build_check = _windows_build_check(Path(app_dir), Path(installer_path) if installer_path is not None else None)
    checks = [source_check, build_check]
    checks.extend(_llm_report_check(Path(report_path)) for report_path in llm_reports)
    checks.extend(_portrait_workflow_report_check(Path(report_path)) for report_path in portrait_workflow_reports)
    checks.extend(_portrait_candidate_report_check(Path(report_path)) for report_path in portrait_candidate_reports)
    checks.extend(_portrait_source_create_report_check(Path(report_path)) for report_path in portrait_source_create_reports)
    checks.extend(_liveportrait_preflight_report_check(Path(report_path)) for report_path in liveportrait_preflight_reports)
    checks.extend(_portrait_frame_preflight_report_check(Path(report_path)) for report_path in portrait_frame_preflight_reports)
    checks.extend(
        _portrait_frame_normalization_report_check(Path(report_path))
        for report_path in portrait_frame_normalization_reports
    )
    checks.extend(_portrait_source_batch_report_check(Path(report_path)) for report_path in portrait_source_batch_reports)
    checks.extend(
        _portrait_source_process_report_check(Path(report_path))
        for report_path in portrait_source_process_reports
    )
    checks.extend(_portrait_video_handoff_report_check(Path(report_path)) for report_path in portrait_video_handoff_reports)
    checks.extend(_portrait_video_import_report_check(Path(report_path)) for report_path in portrait_video_import_reports)
    checks.extend(_portrait_frame_qa_report_check(Path(report_path)) for report_path in portrait_frame_qa_reports)
    checks.extend(
        _portrait_regeneration_brief_report_check(Path(report_path))
        for report_path in portrait_regeneration_brief_reports
    )
    checks.extend(
        _portrait_retry_handoff_report_check(Path(report_path))
        for report_path in portrait_retry_handoff_reports
    )
    checks.extend(
        _hatch_pet_imagegen_readiness_report_check(Path(report_path))
        for report_path in hatch_pet_imagegen_readiness_reports
    )
    checks.extend(
        _hatch_pet_imagegen_route_preflight_report_check(Path(report_path))
        for report_path in hatch_pet_imagegen_route_preflight_reports
    )
    checks.extend(
        _hatch_pet_base_intake_report_check(Path(report_path))
        for report_path in hatch_pet_base_intake_reports
    )
    checks.extend(
        _pixel_pet_emote_mapping_report_check(Path(report_path))
        for report_path in pixel_pet_emote_mapping_reports
    )
    checks.extend(
        _pixel_pet_visual_qa_report_check(Path(report_path))
        for report_path in pixel_pet_visual_qa_reports
    )
    checks.extend(
        _pixel_pet_edge_style_brief_report_check(Path(report_path))
        for report_path in pixel_pet_edge_style_brief_reports
    )
    _apply_normalization_resolutions(checks)
    ok = all(check["ok"] is True for check in checks)
    attention_checks = _attention_checks(checks)
    return {
        "ok": ok,
        "status": "ready" if ok else "needs_attention",
        "check_count": len(checks),
        "ready_check_count": sum(1 for check in checks if check.get("ok") is True),
        "attention_check_count": len(attention_checks),
        "attention_checks": attention_checks,
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
        f"- Ready checks: `{_nonnegative_int(payload.get('ready_check_count'))}`",
        f"- Attention checks: `{_nonnegative_int(payload.get('attention_check_count'))}`",
    ]
    next_actions = _string_list(payload.get("next_actions"))
    if next_actions:
        lines.extend(["", "## Next Actions", ""])
        lines.extend(f"- {item}" for item in next_actions)
    attention_checks = _list_of_mappings(payload.get("attention_checks"))
    if attention_checks:
        lines.extend(["", "## Attention Checks", ""])
        for item in attention_checks:
            label = _optional_string(item.get("label")) or _optional_string(item.get("id")) or "unknown"
            status = _optional_string(item.get("status")) or "unknown"
            actions = _string_list(item.get("next_actions"))
            action_text = "; ".join(actions) if actions else "inspect check details"
            line = f"- `{label}` (`{status}`): `{action_text}`"
            reasons = _string_list(item.get("reasons"))
            if reasons:
                line += " Reasons: `" + "; ".join(reasons) + "`"
            lines.append(line)
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
        if warnings and check.get("id") == "portrait_candidate_decision":
            lines.append("- Candidate warnings:")
            lines.extend(f"  - `{warning}`" for warning in warnings)
        elif warnings:
            lines.append("- Warnings: `" + "; ".join(warnings) + "`")
        distribution_boundary = _optional_string(check.get("distribution_boundary"))
        if distribution_boundary:
            lines.append(f"- Distribution boundary: `{distribution_boundary}`")
        if isinstance(check.get("manual_qa_required"), bool):
            lines.append(f"- Manual QA required: `{'yes' if check.get('manual_qa_required') else 'no'}`")
        provenance_files = _string_list(check.get("provenance_files"))
        if provenance_files:
            lines.append("- Provenance files:")
            lines.extend(f"  - `{filename}`" for filename in provenance_files)
        license_files = _string_list(check.get("license_files"))
        if license_files:
            lines.append("- License files:")
            lines.extend(f"  - `{filename}`" for filename in license_files)
        report_type = _optional_string(check.get("report_type"))
        if report_type:
            lines.append(f"- Report type: `{report_type}`")
        provider = _optional_string(check.get("provider"))
        if provider:
            lines.append(f"- Provider: `{provider}`")
        source_tool = _optional_string(check.get("source_tool"))
        if source_tool:
            lines.append(f"- Source tool: `{source_tool}`")
        run_dir = _optional_string(check.get("run_dir"))
        if run_dir:
            lines.append(f"- Run dir: `{run_dir}`")
        job_id = _optional_string(check.get("job_id"))
        if job_id:
            lines.append(f"- Job id: `{job_id}`")
        source_provenance = _optional_string(check.get("source_provenance"))
        if source_provenance:
            lines.append(f"- Source provenance: `{source_provenance}`")
        source_path = _optional_string(check.get("source_path"))
        if source_path:
            lines.append(f"- Source: `{source_path}`")
        if isinstance(check.get("job_ready"), bool):
            lines.append(f"- Job ready: `{'yes' if check.get('job_ready') else 'no'}`")
        output_path = _optional_string(check.get("output_path"))
        if output_path:
            lines.append(f"- Output path: `{output_path}`")
        if isinstance(check.get("output_exists"), bool):
            lines.append(f"- Output exists: `{'yes' if check.get('output_exists') else 'no'}`")
        record_command = _optional_string(check.get("record_command"))
        if record_command:
            lines.append("- Record command:")
            lines.append(f"  - `{record_command}`")
        secondary_fallback_status = _optional_string(check.get("secondary_fallback_status"))
        if secondary_fallback_status:
            lines.append(f"- Secondary fallback status: `{secondary_fallback_status}`")
        codex_exec_status = _optional_string(check.get("codex_exec_status"))
        if codex_exec_status:
            lines.append(f"- Codex exec status: `{codex_exec_status}`")
        codex_bin = _optional_string(check.get("codex_bin"))
        if codex_bin:
            lines.append(f"- Codex bin: `{codex_bin}`")
        codex_exec_error = _optional_string(check.get("codex_exec_error"))
        if codex_exec_error:
            lines.append(f"- Codex exec error: `{codex_exec_error}`")
        model = _optional_string(check.get("model"))
        if model:
            lines.append(f"- Model: `{model}`")
        character_pack_path = _optional_string(check.get("character_pack_path"))
        if character_pack_path:
            lines.append(f"- Character pack: `{character_pack_path}`")
        motion_manifest_path = _optional_string(check.get("motion_manifest_path"))
        if motion_manifest_path:
            lines.append(f"- Motion manifest: `{motion_manifest_path}`")
        spritesheet_path = _optional_string(check.get("spritesheet_path"))
        if spritesheet_path:
            lines.append(f"- Spritesheet: `{spritesheet_path}`")
        visual_qa_report_path = _optional_string(check.get("visual_qa_report_path"))
        if visual_qa_report_path:
            lines.append(f"- Visual QA report: `{visual_qa_report_path}`")
        if isinstance(check.get("default_promotion_allowed"), bool):
            lines.append(
                f"- Default promotion allowed: `{'yes' if check.get('default_promotion_allowed') else 'no'}`"
            )
        for key, label in (
            ("required_motion_ids", "Required motions"),
            ("available_motion_ids", "Available motions"),
            ("missing_motion_ids", "Missing motions"),
            ("supported_expression_ids", "Supported expressions"),
            ("unsupported_expression_ids", "Unsupported expressions"),
        ):
            if key in check:
                lines.append(f"- {label}: `{_inline_code_list(check.get(key))}`")
        for key, label in (
            ("visible_pixel_count", "Visible pixels"),
            ("edge_pixel_count", "Edge pixels"),
            ("suspicious_edge_halo_pixel_count", "Suspicious edge halo pixels"),
        ):
            value = _optional_int(check.get(key))
            if value is not None:
                lines.append(f"- {label}: `{value}`")
        suspicious_edge_halo_ratio = _optional_float(check.get("suspicious_edge_halo_ratio"))
        if suspicious_edge_halo_ratio is not None:
            lines.append(f"- Suspicious edge halo ratio: `{suspicious_edge_halo_ratio}`")
        for key, label in (
            ("report_count", "Reports"),
            ("passed_count", "Passed reports"),
            ("needs_attention_count", "Needs attention"),
            ("invalid_count", "Invalid reports"),
            ("turn_count", "Turns"),
            ("case_count", "Cue cases"),
            ("cue_failed_count", "Cue failures"),
            ("fallback_count", "Fallback turns"),
            ("issue_count", "Issues"),
            ("speech_quality_violation_count", "Speech quality violations"),
            ("total_job_count", "Total jobs"),
            ("complete_job_count", "Complete jobs"),
            ("ready_job_count", "Ready jobs"),
            ("blocked_job_count", "Blocked jobs"),
        ):
            value = _optional_int(check.get(key))
            if value is not None:
                lines.append(f"- {label}: `{value}`")
        if isinstance(check.get("state_mutation_ok"), bool):
            lines.append(f"- State guard: `{'passed' if check.get('state_mutation_ok') else 'failed'}`")
        decision_state = _optional_string(check.get("decision_state"))
        if decision_state:
            lines.append(f"- Decision state: `{decision_state}`")
        frame_status = _optional_string(check.get("frame_status"))
        if frame_status:
            lines.append(f"- Frame status: `{frame_status}`")
        preflight_status = _optional_string(check.get("preflight_status"))
        if preflight_status:
            lines.append(f"- Preflight status: `{preflight_status}`")
        candidate_status = _optional_string(check.get("candidate_status"))
        if candidate_status:
            lines.append(f"- Candidate status: `{candidate_status}`")
        for key, label in (
            ("image_count", "Images"),
            ("blocker_count", "Blockers"),
            ("warning_count", "Candidate warnings"),
        ):
            value = _optional_int(check.get(key))
            if value is not None:
                lines.append(f"- {label}: `{value}`")
        blockers = _string_list(check.get("blockers"))
        if blockers:
            lines.append("- Blockers:")
            lines.extend(f"  - `{blocker}`" for blocker in blockers)
        retry_prompt = _optional_string(check.get("retry_prompt"))
        if retry_prompt:
            lines.append("- Retry prompt:")
            lines.append(f"  - `{retry_prompt}`")
        negative_prompt = _optional_string(check.get("negative_prompt"))
        if negative_prompt:
            lines.append("- Negative prompt:")
            lines.append(f"  - `{negative_prompt}`")
        prompt_constraints = _string_list(check.get("prompt_constraints"))
        if prompt_constraints:
            lines.append("- Prompt constraints:")
            lines.extend(f"  - `{constraint}`" for constraint in prompt_constraints)
        validation_errors = _string_list(check.get("validation_errors"))
        if validation_errors:
            lines.append("- Validation errors:")
            lines.extend(f"  - `{error}`" for error in validation_errors)
        next_human_decisions = _string_list(check.get("next_human_decisions"))
        if next_human_decisions:
            lines.append("- Next human decisions:")
            lines.extend(f"  - `{decision}`" for decision in next_human_decisions)
        attention_reports = _string_list(check.get("attention_reports"))
        if attention_reports:
            lines.append("- Reports needing attention:")
            lines.extend(f"  - `{report}`" for report in attention_reports)
        attention_reasons = _string_list(check.get("attention_reasons"))
        if attention_reasons:
            lines.append("- Attention reasons:")
            lines.extend(f"  - `{reason}`" for reason in attention_reasons)
        raw_error_codes = _string_list(check.get("raw_error_codes"))
        if raw_error_codes:
            lines.append("- Raw error codes:")
            lines.extend(f"  - `{code}`" for code in raw_error_codes)
        ready_job_ids = _string_list(check.get("ready_job_ids"))
        if ready_job_ids:
            lines.append("- Ready job ids:")
            lines.extend(f"  - `{job_id}`" for job_id in ready_job_ids)
        blocked_job_ids = _string_list(check.get("blocked_job_ids"))
        if blocked_job_ids:
            lines.append("- Blocked job ids:")
            lines.extend(f"  - `{job_id}`" for job_id in blocked_job_ids)
        normalization_resolved = _string_list(check.get("normalization_resolved_summaries"))
        if normalization_resolved:
            lines.append("- Normalization resolved:")
            lines.extend(f"  - `{item}`" for item in normalization_resolved)
        source_root = _optional_string(check.get("source_root"))
        if source_root:
            lines.append(f"- Source root: `{source_root}`")
        candidate_manifest_path = _optional_string(check.get("candidate_manifest_path"))
        if candidate_manifest_path:
            lines.append(f"- Candidate manifest: `{candidate_manifest_path}`")
        output_root = _optional_string(check.get("output_root"))
        if output_root:
            lines.append(f"- Output root: `{output_root}`")
        for key, label in (
            ("pack_count", "Packs"),
            ("requested_count", "Requested packs"),
            ("created_count", "Created packs"),
            ("ready_count", "Ready packs"),
            ("waiting_count", "Waiting packs"),
            ("insufficient_count", "Insufficient packs"),
            ("invalid_frame_pack_count", "Invalid frame packs"),
            ("warning_pack_count", "Warning packs"),
            ("bundle_count", "Bundles"),
            ("handoff_failed_count", "Failed bundles"),
        ):
            value = _optional_int(check.get(key))
            if value is not None:
                lines.append(f"- {label}: `{value}`")
        item_summaries = _string_list(check.get("item_summaries"))
        if item_summaries:
            lines.append("- Frame preflight items:")
            lines.extend(f"  - `{item}`" for item in item_summaries)
        if isinstance(check.get("process_ready"), bool):
            lines.append(f"- Process ready requested: `{'yes' if check.get('process_ready') else 'no'}`")
        for key, label in (
            ("processed_count", "Processed packs"),
            ("failed_count", "Failed packs"),
        ):
            value = _optional_int(check.get(key))
            if value is not None:
                lines.append(f"- {label}: `{value}`")
        source_batch_summaries = _string_list(check.get("source_batch_summaries"))
        if source_batch_summaries:
            lines.append("- Source batch packs:")
            lines.extend(f"  - `{item}`" for item in source_batch_summaries)
        source_create_summaries = _string_list(check.get("source_create_summaries"))
        if source_create_summaries:
            lines.append("- Source create packs:")
            lines.extend(f"  - `{item}`" for item in source_create_summaries)
        source_pack_content_summaries = _string_list(check.get("source_pack_content_summaries"))
        if source_pack_content_summaries:
            lines.append("- Source pack contents:")
            lines.extend(f"  - `{item}`" for item in source_pack_content_summaries)
        handoff_bundle_summaries = _string_list(check.get("handoff_bundle_summaries"))
        if handoff_bundle_summaries:
            lines.append("- Handoff bundles:")
            lines.extend(f"  - `{item}`" for item in handoff_bundle_summaries)
        handoff_bundle_zip_summaries = _string_list(check.get("handoff_bundle_zip_summaries"))
        if handoff_bundle_zip_summaries:
            lines.append("- Handoff bundle zip entries:")
            lines.extend(f"  - `{item}`" for item in handoff_bundle_zip_summaries)
        set_id = _optional_string(check.get("set_id"))
        if set_id:
            lines.append(f"- Set: `{set_id}`")
        source_set_id = _optional_string(check.get("source_set_id"))
        if source_set_id:
            lines.append(f"- Source set: `{source_set_id}`")
        source_pack_dir = _optional_string(check.get("source_pack_dir"))
        if source_pack_dir:
            lines.append(f"- Source pack: `{source_pack_dir}`")
        output_pack_dir = _optional_string(check.get("output_pack_dir"))
        if output_pack_dir:
            lines.append(f"- Output pack: `{output_pack_dir}`")
        reference_image_path = _optional_string(check.get("reference_image_path"))
        if reference_image_path:
            lines.append(f"- Reference image: `{reference_image_path}`")
        prompt_path = _optional_string(check.get("prompt_path"))
        if prompt_path:
            lines.append(f"- Prompt: `{prompt_path}`")
        regeneration_brief_path = _optional_string(check.get("regeneration_brief_path"))
        if regeneration_brief_path:
            lines.append(f"- Regeneration brief: `{regeneration_brief_path}`")
        extraction_report_path = _optional_string(check.get("extraction_report_path"))
        if extraction_report_path:
            lines.append(f"- Extraction report: `{extraction_report_path}`")
        process_report_path = _optional_string(check.get("process_report_path"))
        if process_report_path:
            lines.append(f"- Process report: `{process_report_path}`")
        output_dir = _optional_string(check.get("output_dir"))
        if output_dir:
            lines.append(f"- Output dir: `{output_dir}`")
        input_video_path = _optional_string(check.get("input_video_path"))
        if input_video_path:
            lines.append(f"- Input video: `{input_video_path}`")
        copied_video_path = _optional_string(check.get("copied_video_path"))
        if copied_video_path:
            lines.append(f"- Copied video: `{copied_video_path}`")
        frames_dir = _optional_string(check.get("frames_dir"))
        if frames_dir:
            lines.append(f"- Frames dir: `{frames_dir}`")
        zip_path = _optional_string(check.get("zip_path"))
        if zip_path:
            lines.append(f"- Retry handoff zip: `{zip_path}`")
        retry_handoff_zip_entries = _string_list(check.get("retry_handoff_zip_entries"))
        if retry_handoff_zip_entries:
            lines.append("- Retry handoff zip entries:")
            lines.extend(f"  - `{entry}`" for entry in retry_handoff_zip_entries)
        preview_path = _optional_string(check.get("preview_path"))
        if preview_path:
            lines.append(f"- Preview: `{preview_path}`")
        for key, label in (
            ("frame_count", "Frames"),
            ("input_frame_count", "Input frames"),
            ("normalized_frame_count", "Normalized frames"),
            ("resized_frame_count", "Resized frames"),
            ("copied_frame_count", "Copied frames"),
            ("invalid_frame_count", "Invalid frames"),
            ("aspect_mismatch_count", "Aspect mismatches"),
            ("normalization_warning_count", "Normalization warnings"),
            ("sampled_frame_count", "Sampled frames"),
            ("size_mismatch_count", "Size mismatches"),
            ("actual_frame_count", "Actual PNG frames"),
            ("motion_frame_count", "Motion frames"),
        ):
            value = _optional_int(check.get(key))
            if value is not None:
                lines.append(f"- {label}: `{value}`")
        max_body_drift = _optional_float(check.get("max_body_drift"))
        if max_body_drift is not None:
            lines.append(f"- Max body drift: `{max_body_drift}`")
        driving_status = _optional_string(check.get("driving_status"))
        if driving_status:
            lines.append(f"- Driving status: `{driving_status}`")
        missing_weight_count = _optional_int(check.get("missing_weight_count"))
        if missing_weight_count is not None:
            lines.append(f"- Missing weights: `{missing_weight_count}`")
        missing_weight_paths = _string_list(check.get("missing_weight_paths"))
        if missing_weight_paths:
            lines.append("- Missing weight paths:")
            lines.extend(f"  - `{path}`" for path in missing_weight_paths)
        commands = _string_list(check.get("suggested_commands"))
        if commands:
            lines.append("- Suggested commands:")
            lines.extend(f"  - `{command}`" for command in commands)
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
        "manual_qa_required": report.get("manual_qa_required") is True,
        "distribution_boundary": str(report.get("distribution_boundary") or "unknown"),
        "provenance_files": _string_list(report.get("provenance_files")),
        "license_files": _string_list(report.get("license_files")),
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
    if report_path.is_dir():
        return _llm_report_directory_check(report_path)

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
        "turn_count": review.turn_count,
        "case_count": review.case_count,
        "cue_failed_count": review.cue_failed_count,
        "fallback_count": review.fallback_count,
        "issue_count": review.issue_count,
        "speech_quality_violation_count": _nonnegative_int(review.speech_quality.get("violation_count")),
        "state_mutation_ok": review.state_mutation_check.get("ok") is not False,
        "errors": [f"{issue.kind}: {issue.message}" for issue in review.issues],
        "warnings": [],
        "next_actions": [] if review.ok else ["review LLM smoke report before release"],
    }


def _llm_report_directory_check(report_path: Path) -> dict[str, object]:
    review = review_llm_smoke_reports_in_directory(report_path)
    ok = review.get("ok") is True
    return {
        "id": "llm_report_directory",
        "label": "LLM Smoke Report Directory",
        "ok": ok,
        "status": str(review.get("status") or "unknown"),
        "path": str(report_path),
        "report_count": _nonnegative_int(review.get("report_count")),
        "passed_count": _nonnegative_int(review.get("passed_count")),
        "needs_attention_count": _nonnegative_int(review.get("needs_attention_count")),
        "invalid_count": _nonnegative_int(review.get("invalid_count")),
        "attention_reports": _llm_directory_attention_reports(review),
        "errors": _string_list(review.get("errors")),
        "warnings": [],
        "next_actions": [] if ok else ["review LLM smoke artifact directory before release"],
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
    normalizable_source_set_ids = _dedupe(
        _optional_string(item.get("set_id"))
        for item in items
        if "normalizable_size_mismatch" in _string_list(item.get("attention_reasons"))
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
        "normalizable_source_set_ids": normalizable_source_set_ids,
        "suggested_commands": suggested_commands,
        "errors": _dedupe(errors),
        "warnings": [],
        "next_actions": [] if ok else ["resolve portrait AI-video workflow blockers before promoting motion assets"],
    }


def _portrait_candidate_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_candidate_decision",
            "label": "Portrait Candidate Decision",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "decision_state": "",
            "candidate_status": "",
            "image_count": 0,
            "blocker_count": 0,
            "warning_count": 0,
            "blockers": [],
            "warnings": [],
            "validation_errors": ["portrait candidate decision report must be a JSON object"],
            "next_human_decisions": [],
            "errors": ["portrait candidate decision report must be a JSON object"],
            "next_actions": ["review portrait candidate decision report before release"],
        }
    decision_state = _optional_string(payload.get("decision_state")) or "unknown"
    blockers = _string_list(payload.get("blockers"))
    warnings = _string_list(payload.get("warnings"))
    validation_errors = _string_list(payload.get("validation_errors"))
    next_human_decisions = _string_list(payload.get("next_human_decisions"))
    ok = payload.get("ok") is True and decision_state == "ready_for_pack_promotion_review"
    return {
        "id": "portrait_candidate_decision",
        "label": "Portrait Candidate Decision",
        "ok": ok,
        "status": "ready" if ok else decision_state,
        "path": str(report_path),
        "decision_state": decision_state,
        "candidate_status": _optional_string(payload.get("status")),
        "image_count": _nonnegative_int(payload.get("image_count")),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "validation_errors": validation_errors,
        "next_human_decisions": next_human_decisions,
        "errors": validation_errors,
        "next_actions": [] if ok else ["resolve portrait candidate blockers before manifest promotion"],
    }


def _portrait_source_create_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_source_create",
            "label": "Portrait Source Create",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "candidate_manifest_path": "",
            "output_root": "",
            "requested_count": 0,
            "created_count": 0,
            "failed_count": 0,
            "source_create_summaries": [],
            "source_pack_content_summaries": [],
            "errors": ["portrait source create report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review portrait AI-video source create report before provider handoff"],
        }
    packs = _list_of_mappings(payload.get("packs"))
    errors = _string_list(payload.get("errors"))
    source_pack_content_summaries: list[str] = []
    candidate_manifest_path = _optional_string(payload.get("candidate_manifest_path"))
    if not candidate_manifest_path:
        errors.append("candidate_manifest_path is missing")
    elif not _reported_file_exists(candidate_manifest_path):
        errors.append(f"candidate manifest not found: {candidate_manifest_path}")
    for pack in packs:
        set_id = _optional_string(pack.get("set_id")) or "unknown"
        status = _optional_string(pack.get("status")) or "unknown"
        errors.extend(_string_list(pack.get("errors")))
        if status != "created":
            errors.append(f"{set_id}: source create status {status}")
        source_image = _optional_string(pack.get("source_image"))
        if not source_image:
            errors.append(f"{set_id}: source_image is missing")
        elif not _reported_file_exists(source_image):
            errors.append(f"{set_id}: source image not found: {source_image}")
        output_dir = _optional_string(pack.get("output_dir"))
        if not output_dir:
            errors.append(f"{set_id}: output_dir is missing")
        elif not _reported_dir_exists(output_dir):
            errors.append(f"{set_id}: source pack output dir not found: {output_dir}")
        elif status == "created":
            summary, content_errors = _source_pack_content_summary(set_id=set_id, output_dir=output_dir)
            if summary:
                source_pack_content_summaries.append(summary)
            errors.extend(content_errors)
    requested_count = _nonnegative_int(payload.get("requested_count"))
    created_count = _nonnegative_int(payload.get("created_count"))
    failed_count = _nonnegative_int(payload.get("failed_count"))
    ok = (
        payload.get("ok") is True
        and requested_count > 0
        and len(packs) == requested_count
        and created_count == requested_count
        and failed_count == 0
        and not errors
    )
    return {
        "id": "portrait_source_create",
        "label": "Portrait Source Create",
        "ok": ok,
        "status": "ready" if ok else "needs_attention",
        "path": str(report_path),
        "candidate_manifest_path": candidate_manifest_path,
        "output_root": _optional_string(payload.get("output_root")),
        "requested_count": requested_count,
        "created_count": created_count,
        "failed_count": failed_count,
        "source_create_summaries": _source_create_summaries(packs),
        "source_pack_content_summaries": source_pack_content_summaries,
        "errors": _dedupe(errors),
        "warnings": [],
        "next_actions": [] if ok else ["create or repair portrait AI-video source packs before provider handoff"],
    }


def _liveportrait_preflight_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "liveportrait_preflight",
            "label": "LivePortrait Preflight",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "driving_status": "",
            "missing_weight_count": 0,
            "missing_weight_paths": [],
            "suggested_commands": [],
            "errors": ["LivePortrait preflight report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review LivePortrait preflight report before release"],
        }
    ok = payload.get("ok") is True
    legacy_suggested_command = _optional_string(payload.get("suggested_command"))
    suggested_commands = _dedupe(
        [
            *_string_list(payload.get("suggested_commands")),
            *([legacy_suggested_command] if legacy_suggested_command else []),
        ]
    )
    return {
        "id": "liveportrait_preflight",
        "label": "LivePortrait Preflight",
        "ok": ok,
        "status": "ready" if ok else (_optional_string(payload.get("next_action")) or "needs_attention"),
        "path": str(report_path),
        "source_pack_dir": _optional_string(payload.get("source_pack_dir")),
        "liveportrait_root": _optional_string(payload.get("liveportrait_root")),
        "reference_size": _int_list(payload.get("reference_size")),
        "driving_status": _optional_string(payload.get("driving_status")),
        "missing_weight_count": len(_string_list(payload.get("missing_weight_paths"))),
        "missing_weight_paths": _string_list(payload.get("missing_weight_paths")),
        "suggested_commands": suggested_commands,
        "errors": _string_list(payload.get("errors")),
        "warnings": _string_list(payload.get("warnings")),
        "next_actions": [] if ok else ["resolve LivePortrait preflight blockers before local inference"],
    }


def _portrait_frame_qa_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_frame_visual_qa",
            "label": "Portrait Frame Visual QA",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "set_id": "",
            "preview_path": "",
            "frame_count": 0,
            "sampled_frame_count": 0,
            "size_mismatch_count": 0,
            "max_body_drift": 0.0,
            "errors": ["portrait frame visual QA report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review portrait AI-video frame visual QA report before release"],
        }
    status = _optional_string(payload.get("status")) or "unknown"
    preview_path = _optional_string(payload.get("preview_path"))
    errors = _string_list(payload.get("errors"))
    if not preview_path:
        errors.append("frame visual QA preview_path is missing")
    elif not _reported_file_exists(preview_path):
        errors.append(f"frame visual QA preview not found: {preview_path}")
    ok = payload.get("ok") is True and status == "ready" and not errors
    return {
        "id": "portrait_frame_visual_qa",
        "label": "Portrait Frame Visual QA",
        "ok": ok,
        "status": "ready" if ok else ("needs_attention" if errors else status),
        "path": str(report_path),
        "set_id": _optional_string(payload.get("set_id")),
        "source_pack_dir": _optional_string(payload.get("source_pack_dir")),
        "preview_path": preview_path,
        "reference_size": _int_list(payload.get("reference_size")),
        "frame_count": _nonnegative_int(payload.get("frame_count")),
        "sampled_frame_count": _nonnegative_int(payload.get("sampled_frame_count")),
        "size_mismatch_count": _nonnegative_int(payload.get("size_mismatch_count")),
        "max_body_drift": _nonnegative_float(payload.get("max_body_drift")),
        "errors": _dedupe(errors),
        "warnings": [],
        "next_actions": [] if ok else ["review portrait AI-video frame visual QA before motion extraction"],
    }


def _portrait_frame_preflight_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_frame_preflight",
            "label": "Portrait Frame Preflight",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "source_root": "",
            "pack_count": 0,
            "ready_count": 0,
            "waiting_count": 0,
            "insufficient_count": 0,
            "invalid_frame_pack_count": 0,
            "warning_pack_count": 0,
            "item_summaries": [],
            "errors": ["portrait frame preflight report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review portrait AI-video frame preflight report before release"],
        }
    items = _list_of_mappings(payload.get("items"))
    errors = _string_list(payload.get("errors"))
    for item in items:
        errors.extend(_string_list(item.get("errors")))
    pack_count = _nonnegative_int(payload.get("pack_count"))
    ready_count = _nonnegative_int(payload.get("ready_count"))
    waiting_count = _nonnegative_int(payload.get("waiting_count"))
    insufficient_count = _nonnegative_int(payload.get("insufficient_count"))
    invalid_count = _nonnegative_int(payload.get("invalid_count"))
    warning_count = _nonnegative_int(payload.get("warning_count"))
    ok = (
        payload.get("ok") is True
        and pack_count > 0
        and ready_count == pack_count
        and waiting_count == 0
        and insufficient_count == 0
        and invalid_count == 0
        and warning_count == 0
        and not errors
    )
    return {
        "id": "portrait_frame_preflight",
        "label": "Portrait Frame Preflight",
        "ok": ok,
        "status": "ready" if ok else "needs_attention",
        "path": str(report_path),
        "source_root": _optional_string(payload.get("source_root")),
        "pack_count": pack_count,
        "ready_count": ready_count,
        "waiting_count": waiting_count,
        "insufficient_count": insufficient_count,
        "invalid_frame_pack_count": invalid_count,
        "warning_pack_count": warning_count,
        "item_summaries": _frame_preflight_item_summaries(items),
        "errors": _dedupe(errors),
        "warnings": [],
        "next_actions": [] if ok else ["resolve portrait AI-video frame preflight warnings before motion extraction"],
    }


def _portrait_frame_normalization_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_frame_normalization",
            "label": "Portrait Frame Normalization",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "source_set_id": "",
            "set_id": "",
            "source_pack_dir": "",
            "output_pack_dir": "",
            "reference_image_path": "",
            "input_frame_count": 0,
            "normalized_frame_count": 0,
            "resized_frame_count": 0,
            "copied_frame_count": 0,
            "invalid_frame_count": 0,
            "aspect_mismatch_count": 0,
            "normalization_warning_count": 0,
            "errors": ["portrait frame normalization report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review portrait AI-video frame normalization report before release"],
        }
    errors = _string_list(payload.get("errors"))
    if payload.get("ok") is True:
        errors.extend(
            _normalization_output_metadata_errors(
                output_pack_dir=_optional_string(payload.get("output_pack_dir")),
                set_id=_optional_string(payload.get("set_id")),
            )
        )
    input_frame_count = _nonnegative_int(payload.get("input_frame_count"))
    normalized_frame_count = _nonnegative_int(payload.get("normalized_frame_count"))
    invalid_frame_count = _nonnegative_int(payload.get("invalid_frame_count"))
    aspect_mismatch_count = _nonnegative_int(payload.get("aspect_mismatch_count"))
    ok = (
        payload.get("ok") is True
        and input_frame_count > 0
        and normalized_frame_count == input_frame_count
        and invalid_frame_count == 0
        and aspect_mismatch_count == 0
        and not errors
    )
    return {
        "id": "portrait_frame_normalization",
        "label": "Portrait Frame Normalization",
        "ok": ok,
        "status": "completed" if ok else "needs_attention",
        "path": str(report_path),
        "source_set_id": _optional_string(payload.get("source_set_id")),
        "set_id": _optional_string(payload.get("set_id")),
        "source_pack_dir": _optional_string(payload.get("source_pack_dir")),
        "output_pack_dir": _optional_string(payload.get("output_pack_dir")),
        "reference_image_path": _optional_string(payload.get("reference_image")),
        "input_frame_count": input_frame_count,
        "normalized_frame_count": normalized_frame_count,
        "resized_frame_count": _nonnegative_int(payload.get("resized_frame_count")),
        "copied_frame_count": _nonnegative_int(payload.get("copied_frame_count")),
        "invalid_frame_count": invalid_frame_count,
        "aspect_mismatch_count": aspect_mismatch_count,
        "normalization_warning_count": len(_string_list(payload.get("warnings"))),
        "errors": errors,
        "warnings": [],
        "next_actions": [] if ok else ["repair portrait AI-video frame normalization before preflight rerun"],
    }


def _normalization_output_metadata_errors(*, output_pack_dir: str, set_id: str) -> list[str]:
    errors: list[str] = []
    if not output_pack_dir:
        return ["normalization output_pack_dir is missing"]
    metadata_path = _reported_path(output_pack_dir) / "source_pack.json"
    metadata = _load_json_object(metadata_path)
    if not isinstance(metadata, dict):
        return [f"normalized source metadata not found or invalid: {metadata_path}"]
    metadata_set_id = _optional_string(metadata.get("set_id"))
    if metadata_set_id != set_id:
        errors.append(f"normalized source metadata set_id mismatch: {metadata_set_id or 'missing'}")
    next_command = _optional_string(metadata.get("next_command"))
    if not next_command:
        errors.append("normalized source next_command is missing")
        return errors
    if not _command_references_path(next_command, output_pack_dir):
        errors.append("normalized source next_command does not reference output_pack_dir")
    expected_output = f"portrait-candidate-{set_id}-motion" if set_id else ""
    if expected_output and expected_output not in next_command:
        errors.append("normalized source next_command does not reference normalized motion output")
    return errors


def _command_references_path(command: str, path_string: str) -> bool:
    return path_string in command or str(_reported_path(path_string)) in command


def _portrait_source_batch_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_source_batch",
            "label": "Portrait Source Batch",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "source_root": "",
            "process_ready": False,
            "pack_count": 0,
            "ready_count": 0,
            "warning_pack_count": 0,
            "waiting_count": 0,
            "insufficient_count": 0,
            "processed_count": 0,
            "failed_count": 0,
            "source_batch_summaries": [],
            "errors": ["portrait source batch report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review portrait AI-video source batch report before release"],
        }
    packs = _list_of_mappings(payload.get("packs"))
    errors = _string_list(payload.get("errors"))
    for pack in packs:
        errors.extend(_string_list(pack.get("errors")))
        set_id = _optional_string(pack.get("set_id")) or "unknown"
        status = _optional_string(pack.get("status")) or "unknown"
        if status != "processed":
            continue
        output_dir = _optional_string(pack.get("output_dir"))
        process_report_path = _optional_string(pack.get("process_report_path"))
        if not output_dir:
            errors.append(f"{set_id}: processed source batch output_dir is missing")
        elif not _reported_dir_exists(output_dir):
            errors.append(f"{set_id}: processed source batch output dir not found: {output_dir}")
        if not process_report_path:
            errors.append(f"{set_id}: processed source batch process_report_path is missing")
        elif not _reported_file_exists(process_report_path):
            errors.append(f"{set_id}: processed source batch process report not found: {process_report_path}")
    pack_count = _nonnegative_int(payload.get("pack_count"))
    processed_count = _nonnegative_int(payload.get("processed_count"))
    failed_count = _nonnegative_int(payload.get("failed_count"))
    warning_count = _nonnegative_int(payload.get("warning_count"))
    waiting_count = _nonnegative_int(payload.get("waiting_count"))
    insufficient_count = _nonnegative_int(payload.get("insufficient_count"))
    ready_count = _nonnegative_int(payload.get("ready_count"))
    ok = (
        payload.get("ok") is True
        and pack_count > 0
        and failed_count == 0
        and warning_count == 0
        and waiting_count == 0
        and insufficient_count == 0
        and not errors
        and (processed_count > 0 or ready_count == pack_count)
    )
    return {
        "id": "portrait_source_batch",
        "label": "Portrait Source Batch",
        "ok": ok,
        "status": "ready" if ok else "needs_attention",
        "path": str(report_path),
        "source_root": _optional_string(payload.get("source_root")),
        "process_ready": payload.get("process_ready") is True,
        "pack_count": pack_count,
        "ready_count": ready_count,
        "warning_pack_count": warning_count,
        "waiting_count": waiting_count,
        "insufficient_count": insufficient_count,
        "processed_count": processed_count,
        "failed_count": failed_count,
        "source_batch_summaries": _source_batch_summaries(packs),
        "errors": _dedupe(errors),
        "warnings": [],
        "next_actions": [] if ok else ["resolve portrait AI-video source batch warnings before motion extraction"],
    }


def _portrait_source_process_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_source_process",
            "label": "Portrait Source Process",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "set_id": "",
            "source_pack_dir": "",
            "output_dir": "",
            "reference_image_path": "",
            "frames_dir": "",
            "prompt_path": "",
            "candidate_manifest_path": "",
            "extraction_report_path": "",
            "process_report_path": "",
            "motion_frame_count": 0,
            "preflight_status": "",
            "preflight_warnings": [],
            "errors": ["portrait source process report must be a JSON object"],
            "warnings": [],
            "next_actions": ["repair portrait source process report before candidate QA"],
        }
    errors = _string_list(payload.get("errors"))
    source_pack_dir = _optional_string(payload.get("source_pack_dir"))
    output_dir = _optional_string(payload.get("output_dir"))
    reference_image_path = _optional_string(payload.get("reference_image"))
    frames_dir = _optional_string(payload.get("frames_dir"))
    prompt_path = _optional_string(payload.get("prompt_path"))
    candidate_manifest_path = _optional_string(payload.get("candidate_manifest_path"))
    extraction_report_path = _optional_string(payload.get("extraction_report_path"))
    motion_frame_count = _nonnegative_int(payload.get("motion_frame_count"))
    preflight_status = _optional_string(payload.get("preflight_status"))

    if not source_pack_dir:
        errors.append("source process source_pack_dir is missing")
    elif not _reported_dir_exists(source_pack_dir):
        errors.append(f"source process source pack not found: {source_pack_dir}")
    if not output_dir:
        errors.append("source process output_dir is missing")
    elif not _reported_dir_exists(output_dir):
        errors.append(f"source process output dir not found: {output_dir}")
    if not reference_image_path:
        errors.append("source process reference_image is missing")
    elif not _reported_file_exists(reference_image_path):
        errors.append(f"source process reference image not found: {reference_image_path}")
    if not frames_dir:
        errors.append("source process frames_dir is missing")
    elif not _reported_dir_exists(frames_dir):
        errors.append(f"source process frames dir not found: {frames_dir}")
    if not prompt_path:
        errors.append("source process prompt_path is missing")
    elif not _reported_file_exists(prompt_path):
        errors.append(f"source process prompt not found: {prompt_path}")
    if not candidate_manifest_path:
        errors.append("source process candidate_manifest_path is missing")
    elif not _reported_file_exists(candidate_manifest_path):
        errors.append(f"source process candidate manifest not found: {candidate_manifest_path}")
    if not extraction_report_path:
        errors.append("source process extraction_report_path is missing")
    elif not _reported_file_exists(extraction_report_path):
        errors.append(f"source process extraction report not found: {extraction_report_path}")
    if motion_frame_count <= 0:
        errors.append("source process motion_frame_count must be positive")
    if preflight_status != "ready":
        errors.append(f"source process preflight status is not ready: {preflight_status or 'missing'}")

    errors = _dedupe(errors)
    ok = payload.get("ok") is True and motion_frame_count > 0 and preflight_status == "ready" and not errors
    return {
        "id": "portrait_source_process",
        "label": "Portrait Source Process",
        "ok": ok,
        "status": "ready" if ok else "needs_attention",
        "path": str(report_path),
        "set_id": _optional_string(payload.get("set_id")),
        "source_pack_dir": source_pack_dir,
        "output_dir": output_dir,
        "reference_image_path": reference_image_path,
        "frames_dir": frames_dir,
        "prompt_path": prompt_path,
        "candidate_manifest_path": candidate_manifest_path,
        "extraction_report_path": extraction_report_path,
        "process_report_path": _optional_string(payload.get("process_report_path")),
        "motion_frame_count": motion_frame_count,
        "preflight_status": preflight_status,
        "preflight_warnings": _string_list(payload.get("preflight_warnings")),
        "errors": errors,
        "warnings": [],
        "next_actions": [] if ok else ["repair portrait source process report before candidate QA"],
    }


def _portrait_video_handoff_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_video_handoff",
            "label": "Portrait Video Handoff",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "source_root": "",
            "output_dir": "",
            "pack_count": 0,
            "bundle_count": 0,
            "handoff_failed_count": 0,
            "handoff_bundle_summaries": [],
            "handoff_bundle_zip_summaries": [],
            "errors": ["portrait video handoff report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review portrait AI-video handoff report before release"],
        }
    bundles = _list_of_mappings(payload.get("bundles"))
    errors = _string_list(payload.get("errors"))
    handoff_zip_entries_by_set_id: dict[str, list[str]] = {}
    for bundle in bundles:
        errors.extend(_string_list(bundle.get("errors")))
        set_id = _optional_string(bundle.get("set_id")) or "unknown"
        status = _optional_string(bundle.get("status")) or "unknown"
        zip_path = _optional_string(bundle.get("zip_path"))
        if status != "bundled":
            errors.append(f"{set_id}: handoff bundle status {status}")
            continue
        if not zip_path:
            errors.append(f"{set_id}: handoff zip_path is missing")
            continue
        zip_entries = _zip_entries(zip_path, errors, label="handoff zip")
        handoff_zip_entries_by_set_id[set_id] = zip_entries
        for required_entry in sorted(REQUIRED_VIDEO_HANDOFF_ZIP_ENTRIES):
            if required_entry not in zip_entries:
                errors.append(f"{set_id}: handoff zip missing required entry: {required_entry}")
        if not any(entry.startswith("reference/") for entry in zip_entries):
            errors.append(f"{set_id}: handoff zip missing reference image entry")
    pack_count = _nonnegative_int(payload.get("pack_count"))
    bundle_count = _nonnegative_int(payload.get("bundle_count"))
    failed_count = _nonnegative_int(payload.get("failed_count"))
    ok = (
        payload.get("ok") is True
        and pack_count > 0
        and bundle_count == pack_count
        and failed_count == 0
        and not errors
    )
    return {
        "id": "portrait_video_handoff",
        "label": "Portrait Video Handoff",
        "ok": ok,
        "status": "ready" if ok else "needs_attention",
        "path": str(report_path),
        "source_root": _optional_string(payload.get("source_root")),
        "output_dir": _optional_string(payload.get("output_dir")),
        "pack_count": pack_count,
        "bundle_count": bundle_count,
        "handoff_failed_count": failed_count,
        "handoff_bundle_summaries": _handoff_bundle_summaries(bundles),
        "handoff_bundle_zip_summaries": _handoff_bundle_zip_summaries(handoff_zip_entries_by_set_id),
        "errors": _dedupe(errors),
        "warnings": [],
        "next_actions": [] if ok else ["create or repair portrait AI-video handoff zips before manual provider upload"],
    }


def _portrait_video_import_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_video_import",
            "label": "Portrait Video Import",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "set_id": "",
            "source_pack_dir": "",
            "input_video_path": "",
            "copied_video_path": "",
            "frames_dir": "",
            "source_tool": "",
            "fps": 0,
            "frame_count": 0,
            "actual_frame_count": 0,
            "suggested_commands": [],
            "errors": ["portrait video import report must be a JSON object"],
            "warnings": [],
            "next_actions": ["repair portrait AI-video import before frame preflight"],
        }
    errors = _string_list(payload.get("errors"))
    copied_video_path = _optional_string(payload.get("copied_video_path"))
    frames_dir = _optional_string(payload.get("frames_dir"))
    frame_count = _nonnegative_int(payload.get("frame_count"))
    actual_frame_count = 0
    if not copied_video_path:
        errors.append("video import copied_video_path is missing")
    elif not _reported_file_exists(copied_video_path):
        errors.append(f"video import copied video not found: {copied_video_path}")
    if not frames_dir:
        errors.append("video import frames_dir is missing")
    elif not _reported_dir_exists(frames_dir):
        errors.append(f"video import frames_dir not found: {frames_dir}")
    else:
        actual_frame_count = _reported_png_count(frames_dir)
        if actual_frame_count <= 0:
            errors.append(f"video import frames_dir contains no PNG frames: {frames_dir}")
        elif frame_count != actual_frame_count:
            errors.append(f"video import frame_count mismatch: report={frame_count}, actual={actual_frame_count}")
    errors = _dedupe(errors)
    ok = payload.get("ok") is True and frame_count > 0 and not errors
    return {
        "id": "portrait_video_import",
        "label": "Portrait Video Import",
        "ok": ok,
        "status": "ready" if ok else "needs_attention",
        "path": str(report_path),
        "set_id": _optional_string(payload.get("set_id")),
        "source_pack_dir": _optional_string(payload.get("source_pack_dir")),
        "input_video_path": _optional_string(payload.get("input_video_path")),
        "copied_video_path": copied_video_path,
        "frames_dir": frames_dir,
        "source_tool": _optional_string(payload.get("source_tool")),
        "fps": _nonnegative_int(payload.get("fps")),
        "replace_frames": payload.get("replace_frames") is True,
        "frame_count": frame_count,
        "actual_frame_count": actual_frame_count,
        "suggested_commands": _string_list(payload.get("next_commands")),
        "errors": errors,
        "warnings": [],
        "next_actions": [] if ok else ["repair portrait AI-video import before frame preflight"],
    }


def _portrait_regeneration_brief_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_video_regeneration_brief",
            "label": "Portrait Video Regeneration Brief",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "set_id": "",
            "source_pack_dir": "",
            "reference_image_path": "",
            "decision_state": "",
            "frame_status": "",
            "preview_path": "",
            "frame_count": 0,
            "sampled_frame_count": 0,
            "size_mismatch_count": 0,
            "max_body_drift": 0.0,
            "blockers": [],
            "retry_prompt": "",
            "negative_prompt": "",
            "prompt_constraints": [],
            "suggested_commands": [],
            "errors": ["portrait regeneration brief report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review portrait AI-video regeneration brief before release"],
        }
    decision_state = _optional_string(payload.get("decision_state")) or "unknown"
    blockers = _string_list(payload.get("blockers"))
    errors = _string_list(payload.get("errors"))
    reference_image_path = _optional_string(payload.get("reference_image_path"))
    preview_path = _optional_string(payload.get("preview_path"))
    if not reference_image_path:
        errors.append("regeneration reference_image_path is missing")
    elif not _reported_file_exists(reference_image_path):
        errors.append(f"regeneration reference image not found: {reference_image_path}")
    if not preview_path:
        errors.append("regeneration preview_path is missing")
    elif not _reported_file_exists(preview_path):
        errors.append(f"regeneration frame QA preview not found: {preview_path}")
    errors = _dedupe(errors)
    ok = payload.get("ok") is True and decision_state == "process_frames" and not blockers and not errors
    status = "ready" if ok else "needs_attention" if errors else decision_state
    next_actions: list[str] = []
    if not ok:
        next_actions = [
            "review portrait AI-video regeneration brief before release"
            if errors
            else "regenerate portrait AI-video using the brief retry prompts before motion extraction"
        ]
    return {
        "id": "portrait_video_regeneration_brief",
        "label": "Portrait Video Regeneration Brief",
        "ok": ok,
        "status": status,
        "path": str(report_path),
        "set_id": _optional_string(payload.get("set_id")),
        "source_pack_dir": _optional_string(payload.get("source_pack_dir")),
        "reference_image_path": reference_image_path,
        "decision_state": decision_state,
        "frame_status": _optional_string(payload.get("frame_status")),
        "preview_path": preview_path,
        "frame_count": _nonnegative_int(payload.get("frame_count")),
        "sampled_frame_count": _nonnegative_int(payload.get("sampled_frame_count")),
        "size_mismatch_count": _nonnegative_int(payload.get("size_mismatch_count")),
        "max_body_drift": _nonnegative_float(payload.get("max_body_drift")),
        "blockers": blockers,
        "retry_prompt": _optional_string(payload.get("retry_prompt")),
        "negative_prompt": _optional_string(payload.get("negative_prompt")),
        "prompt_constraints": _string_list(payload.get("prompt_constraints")),
        "suggested_commands": _string_list(payload.get("suggested_commands")),
        "errors": errors,
        "warnings": [],
        "next_actions": next_actions,
    }


def _portrait_retry_handoff_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "portrait_video_retry_handoff",
            "label": "Portrait Video Retry Handoff",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "set_id": "",
            "regeneration_brief_path": "",
            "reference_image_path": "",
            "output_dir": "",
            "zip_path": "",
            "retry_handoff_zip_entries": [],
            "errors": ["portrait retry handoff report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review portrait AI-video retry handoff report before release"],
        }
    errors = _string_list(payload.get("errors"))
    zip_path = _optional_string(payload.get("zip_path"))
    zip_entries: list[str] = []
    if not zip_path:
        errors.append("retry handoff zip_path is missing")
    else:
        zip_entries = _zip_entries(zip_path, errors)
        for required_entry in sorted(REQUIRED_RETRY_HANDOFF_ZIP_ENTRIES):
            if required_entry not in zip_entries:
                errors.append(f"retry handoff zip missing required entry: {required_entry}")
    ok = payload.get("ok") is True and bool(zip_path) and not errors
    return {
        "id": "portrait_video_retry_handoff",
        "label": "Portrait Video Retry Handoff",
        "ok": ok,
        "status": "ready" if ok else "needs_attention",
        "path": str(report_path),
        "set_id": _optional_string(payload.get("set_id")),
        "regeneration_brief_path": _optional_string(payload.get("regeneration_brief_path")),
        "reference_image_path": _optional_string(payload.get("reference_image_path")),
        "output_dir": _optional_string(payload.get("output_dir")),
        "zip_path": zip_path,
        "retry_handoff_zip_entries": zip_entries,
        "errors": _dedupe(errors),
        "warnings": [],
        "next_actions": []
        if ok
        else ["create or repair portrait AI-video retry handoff zip before manual provider upload"],
    }


def _hatch_pet_imagegen_readiness_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "hatch_pet_imagegen_readiness",
            "label": "Hatch Pet Imagegen Readiness",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "run_dir": "",
            "total_job_count": 0,
            "complete_job_count": 0,
            "ready_job_count": 0,
            "blocked_job_count": 0,
            "ready_job_ids": [],
            "blocked_job_ids": [],
            "openai_api_key_present": False,
            "raw_error_codes": [],
            "blockers": [],
            "errors": ["hatch-pet imagegen readiness report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review hatch-pet imagegen readiness before retrying image generation"],
        }
    status = _optional_string(payload.get("status")) or "unknown"
    blockers = _string_list(payload.get("blockers"))
    errors = _string_list(payload.get("errors"))
    raw_error_codes = _string_list(payload.get("raw_error_codes"))
    ok = payload.get("ok") is True and status == "ready" and not blockers and not errors and not raw_error_codes
    next_actions = _string_list(payload.get("next_actions"))
    if not ok and not next_actions:
        next_actions = ["review hatch-pet imagegen readiness before retrying image generation"]
    return {
        "id": "hatch_pet_imagegen_readiness",
        "label": "Hatch Pet Imagegen Readiness",
        "ok": ok,
        "status": "ready" if ok else status,
        "path": str(report_path),
        "run_dir": _optional_string(payload.get("run_dir")),
        "total_job_count": _nonnegative_int(payload.get("total_job_count")),
        "complete_job_count": _nonnegative_int(payload.get("complete_job_count")),
        "ready_job_count": _nonnegative_int(payload.get("ready_job_count")),
        "blocked_job_count": _nonnegative_int(payload.get("blocked_job_count")),
        "ready_job_ids": _string_list(payload.get("ready_job_ids")),
        "blocked_job_ids": _string_list(payload.get("blocked_job_ids")),
        "openai_api_key_present": payload.get("openai_api_key_present") is True,
        "raw_error_codes": raw_error_codes,
        "blockers": blockers,
        "errors": errors,
        "warnings": _string_list(payload.get("warnings")),
        "next_actions": next_actions,
    }


def _hatch_pet_imagegen_route_preflight_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "hatch_pet_imagegen_route_preflight",
            "label": "Hatch Pet Imagegen Route Preflight",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "run_dir": "",
            "ready_job_ids": [],
            "blocked_job_ids": [],
            "secondary_fallback_status": "",
            "codex_exec_status": "",
            "codex_bin": "",
            "codex_exec_error": "",
            "raw_error_codes": [],
            "blockers": [],
            "errors": ["hatch-pet imagegen route preflight report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review hatch-pet imagegen route preflight before retrying generation"],
        }
    status = _optional_string(payload.get("status")) or "unknown"
    blockers = _string_list(payload.get("blockers"))
    errors = _string_list(payload.get("errors"))
    raw_error_codes = _string_list(payload.get("raw_error_codes"))
    ok = payload.get("ok") is True and status == "ready_for_base_generation" and not blockers and not errors
    next_actions = _string_list(payload.get("next_actions"))
    if not ok and not next_actions:
        next_actions = ["review hatch-pet imagegen route preflight before retrying generation"]
    return {
        "id": "hatch_pet_imagegen_route_preflight",
        "label": "Hatch Pet Imagegen Route Preflight",
        "ok": ok,
        "status": status,
        "path": str(report_path),
        "run_dir": _optional_string(payload.get("run_dir")),
        "ready_job_ids": _string_list(payload.get("ready_job_ids")),
        "blocked_job_ids": _string_list(payload.get("blocked_job_ids")),
        "secondary_fallback_status": _optional_string(payload.get("secondary_fallback_status")),
        "codex_exec_status": _optional_string(payload.get("codex_exec_status")),
        "codex_bin": _optional_string(payload.get("codex_bin")),
        "codex_exec_error": _optional_string(payload.get("codex_exec_error")),
        "raw_error_codes": raw_error_codes,
        "blockers": blockers,
        "errors": errors,
        "warnings": _string_list(payload.get("warnings")),
        "next_actions": next_actions,
    }


def _hatch_pet_base_intake_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "hatch_pet_base_intake_preflight",
            "label": "Hatch Pet Base Intake Preflight",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "run_dir": "",
            "job_id": "",
            "source_path": "",
            "source_provenance": "",
            "job_ready": False,
            "output_path": "",
            "output_exists": False,
            "prompt_path": "",
            "character_definition_path": "",
            "record_command": "",
            "errors": ["hatch-pet base intake report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review hatch-pet base intake before recording a base image"],
        }
    status = _optional_string(payload.get("status")) or "unknown"
    errors = _string_list(payload.get("errors"))
    warnings = _string_list(payload.get("warnings"))
    source_provenance = _optional_string(payload.get("source_provenance"))
    record_command = _optional_string(payload.get("record_command"))
    job_ready = payload.get("job_ready") is True
    output_exists = payload.get("output_exists") is True
    ok = (
        payload.get("ok") is True
        and status == "ready_to_record"
        and source_provenance == "built-in-imagegen"
        and job_ready
        and not output_exists
        and bool(record_command)
        and not errors
    )
    next_actions = _string_list(payload.get("next_actions"))
    if not ok and not next_actions:
        next_actions = ["review hatch-pet base intake before recording a base image"]
    return {
        "id": "hatch_pet_base_intake_preflight",
        "label": "Hatch Pet Base Intake Preflight",
        "ok": ok,
        "status": status,
        "path": str(report_path),
        "run_dir": _optional_string(payload.get("run_dir")),
        "job_id": _optional_string(payload.get("job_id")),
        "source_path": _optional_string(payload.get("source_path")),
        "source_provenance": source_provenance,
        "generated_images_root": _optional_string(payload.get("generated_images_root")),
        "job_ready": job_ready,
        "output_path": _optional_string(payload.get("output_path")),
        "output_exists": output_exists,
        "prompt_path": _optional_string(payload.get("prompt_path")),
        "character_definition_path": _optional_string(payload.get("character_definition_path")),
        "record_command": record_command,
        "errors": errors,
        "warnings": warnings,
        "next_actions": next_actions,
    }


def _pixel_pet_emote_mapping_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "pixel_pet_emote_mapping",
            "label": "Pixel Pet Emote Mapping",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "character_pack_path": "",
            "motion_manifest_path": "",
            "available_motion_ids": [],
            "required_motion_ids": [],
            "missing_motion_ids": [],
            "supported_expression_ids": [],
            "unsupported_expression_ids": [],
            "errors": ["pixel-pet emote mapping report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review pixel-pet emote mapping before promoting LLM expression coverage"],
        }
    status = _optional_string(payload.get("status")) or "unknown"
    errors = _string_list(payload.get("errors"))
    warnings = _string_list(payload.get("warnings"))
    missing_motion_ids = _string_list(payload.get("missing_motion_ids"))
    unsupported_expression_ids = _string_list(payload.get("unsupported_expression_ids"))
    ok = (
        payload.get("ok") is True
        and status == "ready"
        and not missing_motion_ids
        and not unsupported_expression_ids
        and not errors
    )
    next_actions = _string_list(payload.get("next_actions"))
    if not ok and not next_actions:
        next_actions = ["review pixel-pet emote mapping before promoting LLM expression coverage"]
    return {
        "id": "pixel_pet_emote_mapping",
        "label": "Pixel Pet Emote Mapping",
        "ok": ok,
        "status": status,
        "path": str(report_path),
        "character_pack_path": _optional_string(payload.get("character_pack_path")),
        "motion_manifest_path": _optional_string(payload.get("motion_manifest_path")),
        "available_motion_ids": _string_list(payload.get("available_motion_ids")),
        "required_motion_ids": _string_list(payload.get("required_motion_ids")),
        "missing_motion_ids": missing_motion_ids,
        "supported_expression_ids": _string_list(payload.get("supported_expression_ids")),
        "unsupported_expression_ids": unsupported_expression_ids,
        "errors": errors,
        "warnings": warnings,
        "next_actions": next_actions,
    }


def _pixel_pet_visual_qa_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "pixel_pet_visual_qa",
            "label": "Pixel Pet Visual QA",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "spritesheet_path": "",
            "motion_manifest_path": "",
            "preview_path": "",
            "visible_pixel_count": 0,
            "edge_pixel_count": 0,
            "suspicious_edge_halo_pixel_count": 0,
            "suspicious_edge_halo_ratio": 0.0,
            "errors": ["pixel-pet visual QA report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review pixel-pet visual QA before default promotion"],
        }
    status = _optional_string(payload.get("status")) or "unknown"
    errors = _string_list(payload.get("errors"))
    warnings = _string_list(payload.get("warnings"))
    preview_path = _optional_string(payload.get("preview_path"))
    ok = payload.get("ok") is True and status == "ready" and not warnings and not errors
    next_actions = _string_list(payload.get("next_actions"))
    if not ok and not next_actions:
        next_actions = ["resolve pixel-pet visual QA warnings before default promotion"]
    return {
        "id": "pixel_pet_visual_qa",
        "label": "Pixel Pet Visual QA",
        "ok": ok,
        "status": status,
        "path": str(report_path),
        "spritesheet_path": _optional_string(payload.get("spritesheet_path")),
        "motion_manifest_path": _optional_string(payload.get("motion_manifest_path")),
        "preview_path": preview_path,
        "width": _nonnegative_int(payload.get("width")),
        "height": _nonnegative_int(payload.get("height")),
        "mode": _optional_string(payload.get("mode")),
        "visible_pixel_count": _nonnegative_int(payload.get("visible_pixel_count")),
        "edge_pixel_count": _nonnegative_int(payload.get("edge_pixel_count")),
        "suspicious_edge_halo_pixel_count": _nonnegative_int(payload.get("suspicious_edge_halo_pixel_count")),
        "suspicious_edge_halo_ratio": _nonnegative_float(payload.get("suspicious_edge_halo_ratio")),
        "errors": errors,
        "warnings": warnings,
        "next_actions": next_actions,
    }


def _pixel_pet_edge_style_brief_report_check(report_path: Path) -> dict[str, object]:
    payload = _load_json_object(report_path)
    if not isinstance(payload, dict):
        return {
            "id": "pixel_pet_edge_style_brief",
            "label": "Pixel Pet Edge Style Brief",
            "ok": False,
            "status": "invalid_report",
            "path": str(report_path),
            "character_id": "",
            "visual_qa_report_path": "",
            "spritesheet_path": "",
            "motion_manifest_path": "",
            "preview_path": "",
            "decision_state": "",
            "default_promotion_allowed": False,
            "blockers": [],
            "errors": ["pixel-pet edge style brief report must be a JSON object"],
            "warnings": [],
            "next_actions": ["review pixel-pet edge style brief before default promotion"],
        }
    decision_state = _optional_string(payload.get("decision_state")) or "unknown"
    blockers = _string_list(payload.get("blockers"))
    errors = _string_list(payload.get("errors"))
    default_promotion_allowed = payload.get("default_promotion_allowed") is True
    ok = (
        payload.get("ok") is True
        and decision_state == "eligible_for_manual_default_review"
        and default_promotion_allowed
        and not blockers
        and not errors
    )
    next_actions = _string_list(payload.get("next_actions"))
    if not ok and not next_actions:
        next_actions = ["review pixel-pet edge style brief before default promotion"]
    return {
        "id": "pixel_pet_edge_style_brief",
        "label": "Pixel Pet Edge Style Brief",
        "ok": ok,
        "status": "ready" if ok else decision_state,
        "path": str(report_path),
        "character_id": _optional_string(payload.get("character_id")),
        "visual_qa_report_path": _optional_string(payload.get("visual_qa_report_path")),
        "spritesheet_path": _optional_string(payload.get("spritesheet_path")),
        "motion_manifest_path": _optional_string(payload.get("motion_manifest_path")),
        "preview_path": _optional_string(payload.get("preview_path")),
        "decision_state": decision_state,
        "default_promotion_allowed": default_promotion_allowed,
        "edge_pixel_count": _nonnegative_int(payload.get("edge_pixel_count")),
        "suspicious_edge_halo_pixel_count": _nonnegative_int(payload.get("suspicious_edge_halo_pixel_count")),
        "suspicious_edge_halo_ratio": _nonnegative_float(payload.get("suspicious_edge_halo_ratio")),
        "blockers": blockers,
        "prompt_locks": _string_list(payload.get("prompt_locks")),
        "suggested_commands": _string_list(payload.get("suggested_commands")),
        "acceptance_gates": _string_list(payload.get("acceptance_gates")),
        "errors": errors,
        "warnings": _string_list(payload.get("warnings")),
        "next_actions": next_actions,
    }


def _full_local_snapshot_report_paths(artifact_root: Path) -> dict[str, list[Path]]:
    root = artifact_root
    source_root = root / "portrait-video-source"
    video_import_reports = (
        sorted(source_root.glob("*/video_import_report.json")) if source_root.is_dir() else []
    )
    source_process_reports = sorted(root.glob("portrait-video-source-process-*.json"))
    if source_root.is_dir():
        for report_path in sorted(source_root.glob("*/source_pack_process_report.json")):
            if report_path not in source_process_reports:
                source_process_reports.append(report_path)
    for report_path in sorted(root.glob("portrait-candidate-*-motion/source_pack_process_report.json")):
        if report_path not in source_process_reports:
            source_process_reports.append(report_path)
    return {
        "llm_reports": [
            root / "llm_smoke" / "deepseek-expression-cue-probe-20260609-rerun.json",
            root / "llm_smoke" / "deepseek-speech-quality-live-20260609-rerun.json",
        ],
        "portrait_workflow_reports": [root / "portrait-video-workflow-report.json"],
        "portrait_candidate_reports": [
            root / "portrait-candidate-xingxi-vn-20260607" / "portrait-decision-brief.json"
        ],
        "portrait_source_create_reports": [root / "portrait-video-source-create-report.json"],
        "liveportrait_preflight_reports": [root / "liveportrait-preflight-xingxi-vn-neutral.json"],
        "portrait_frame_preflight_reports": [root / "portrait-video-frame-preflight.json"],
        "portrait_frame_normalization_reports": [root / "portrait-video-frame-normalization.json"],
        "portrait_source_batch_reports": [root / "portrait-video-source-batch-report.json"],
        "portrait_source_process_reports": source_process_reports,
        "portrait_video_handoff_reports": [root / "portrait-video-handoff-report.json"],
        "portrait_video_import_reports": video_import_reports,
        "portrait_frame_qa_reports": [
            root / "portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.json"
        ],
        "portrait_regeneration_brief_reports": [
            root / "portrait-video-regeneration-brief-xingxi-vn-neutral-20260608-normalized.json"
        ],
        "portrait_retry_handoff_reports": [root / "portrait-video-retry-handoff-report.json"],
        "hatch_pet_imagegen_readiness_reports": sorted(
            (root / "pixel-pet-sequence-drafts").glob("*/imagegen-readiness.json")
        )
        if (root / "pixel-pet-sequence-drafts").is_dir()
        else [],
        "hatch_pet_imagegen_route_preflight_reports": sorted(
            (root / "pixel-pet-sequence-drafts").glob("*/imagegen-route-preflight.json")
        )
        if (root / "pixel-pet-sequence-drafts").is_dir()
        else [],
        "hatch_pet_base_intake_reports": sorted(
            (root / "pixel-pet-sequence-drafts").glob("*/base-intake-preflight.json")
        )
        if (root / "pixel-pet-sequence-drafts").is_dir()
        else [],
        "pixel_pet_emote_mapping_reports": sorted(root.glob("route-scan-*/*emote-mapping.json")),
        "pixel_pet_visual_qa_reports": sorted(
            (root / "character-library-qa").glob("*pixel-pet-visual-qa*.json")
        )
        if (root / "character-library-qa").is_dir()
        else [],
        "pixel_pet_edge_style_brief_reports": sorted(
            (root / "character-library-qa").glob("*pixel-pet-edge-style-brief*.json")
        )
        if (root / "character-library-qa").is_dir()
        else [],
    }


def _empty_snapshot_report_paths() -> dict[str, list[Path]]:
    return {key: [] for key in FULL_LOCAL_SNAPSHOT_REPORT_KEYS}


def _snapshot_paths(args: argparse.Namespace) -> dict[str, list[Path]]:
    if not args.full_local_snapshot:
        return _empty_snapshot_report_paths()
    return _full_local_snapshot_report_paths(Path(args.snapshot_artifact_root))


def _load_json_object(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _llm_directory_attention_reports(payload: dict[str, object]) -> list[str]:
    reports = _list_of_mappings(payload.get("reports"))
    summaries: list[str] = []
    for item in reports:
        status = _optional_string(item.get("status")) or "unknown"
        if status == "passed":
            continue
        path_name = Path(_optional_string(item.get("path"))).name or "unknown"
        issue_count = _nonnegative_int(item.get("issue_count"))
        reason = _optional_string(item.get("reason"))
        summary = f"{path_name}: {status}, issues={issue_count}"
        if reason:
            summary += f", reason={reason}"
        summaries.append(summary)
    return summaries


def _frame_preflight_item_summaries(items: list[dict[str, object]]) -> list[str]:
    summaries: list[str] = []
    for item in items:
        set_id = _optional_string(item.get("set_id")) or "unknown"
        status = _optional_string(item.get("status")) or "unknown"
        next_action = _optional_string(item.get("next_action")) or "inspect_manually"
        frame_count = _nonnegative_int(item.get("frame_count"))
        summaries.append(f"{set_id}: {status}, next_action={next_action}, frames={frame_count}")
    return summaries


def _source_batch_summaries(packs: list[dict[str, object]]) -> list[str]:
    summaries: list[str] = []
    for pack in packs:
        set_id = _optional_string(pack.get("set_id")) or "unknown"
        status = _optional_string(pack.get("status")) or "unknown"
        frame_count = _nonnegative_int(pack.get("frame_count"))
        output_dir = _optional_string(pack.get("output_dir"))
        summary = f"{set_id}: {status}, frames={frame_count}"
        if output_dir:
            summary += f", output={output_dir}"
        summaries.append(summary)
    return summaries


def _source_create_summaries(packs: list[dict[str, object]]) -> list[str]:
    summaries: list[str] = []
    for pack in packs:
        set_id = _optional_string(pack.get("set_id")) or "unknown"
        status = _optional_string(pack.get("status")) or "unknown"
        expression_id = _optional_string(pack.get("expression_id")) or "unknown"
        variant = _optional_string(pack.get("variant")) or "unknown"
        output_dir = _optional_string(pack.get("output_dir"))
        summary = f"{set_id}: {status}, expression={expression_id}, variant={variant}"
        if output_dir:
            summary += f", output={output_dir}"
        summaries.append(summary)
    return summaries


def _source_pack_content_summary(*, set_id: str, output_dir: str) -> tuple[str, list[str]]:
    root = _reported_path(output_dir)
    errors: list[str] = []
    present_entries: list[str] = []
    for relative_path in REQUIRED_SOURCE_PACK_FILES:
        path = root / relative_path
        if path.is_file():
            present_entries.append(relative_path)
        else:
            errors.append(f"{set_id}: source pack missing required file: {relative_path}")
    for relative_dir in REQUIRED_SOURCE_PACK_DIRS:
        path = root / relative_dir
        if not path.is_dir():
            errors.append(f"{set_id}: source pack missing required directory: {relative_dir}")
            continue
        if relative_dir == "reference":
            reference_files = sorted(item for item in path.iterdir() if item.is_file())
            if not reference_files:
                errors.append(f"{set_id}: source pack reference directory is empty")
                continue
            present_entries.append(f"reference/{reference_files[0].name}")
        else:
            present_entries.append(f"{relative_dir}/")
    return f"{set_id}: {', '.join(present_entries)}", errors


def _handoff_bundle_summaries(bundles: list[dict[str, object]]) -> list[str]:
    summaries: list[str] = []
    for bundle in bundles:
        set_id = _optional_string(bundle.get("set_id")) or "unknown"
        status = _optional_string(bundle.get("status")) or "unknown"
        zip_path = _optional_string(bundle.get("zip_path"))
        summary = f"{set_id}: {status}"
        if zip_path:
            summary += f", zip={zip_path}"
        summaries.append(summary)
    return summaries


def _handoff_bundle_zip_summaries(entries_by_set_id: dict[str, list[str]]) -> list[str]:
    summaries: list[str] = []
    for set_id in sorted(entries_by_set_id):
        entries = ", ".join(entries_by_set_id[set_id])
        summaries.append(f"{set_id}: entries={entries}")
    return summaries


def _reported_file_exists(path_string: str) -> bool:
    path = Path(path_string)
    return path.is_file() if path.is_absolute() else (REPO_ROOT / path).is_file()


def _reported_dir_exists(path_string: str) -> bool:
    return _reported_path(path_string).is_dir()


def _reported_path(path_string: str) -> Path:
    path = Path(path_string)
    return path if path.is_absolute() else REPO_ROOT / path


def _reported_png_count(path_string: str) -> int:
    directory = _reported_path(path_string)
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".png")


def _zip_entries(path_string: str, errors: list[str], *, label: str = "retry handoff zip") -> list[str]:
    path = Path(path_string)
    target = path if path.is_absolute() else REPO_ROOT / path
    if not target.is_file():
        errors.append(f"{label} not found: {path_string}")
        return []
    try:
        with zipfile.ZipFile(target) as archive:
            return sorted(item.filename for item in archive.infolist() if not item.is_dir())
    except (OSError, zipfile.BadZipFile):
        errors.append(f"{label} is not readable: {path_string}")
        return []


def _apply_normalization_resolutions(checks: list[dict[str, object]]) -> None:
    resolutions = _normalization_resolutions(checks)
    if not resolutions:
        return
    for check in checks:
        check_id = _optional_string(check.get("id"))
        if check_id == "portrait_video_workflow":
            _resolve_workflow_normalization_attention(check, resolutions=resolutions)
        elif check_id == "portrait_frame_preflight":
            _resolve_summary_normalization_attention(
                check,
                summary_key="item_summaries",
                count_key="warning_pack_count",
                resolutions=resolutions,
                resolved_statuses=("next_action=normalize_frames",),
            )
            _mark_check_ready_if_no_unresolved_source_warnings(check)
        elif check_id == "portrait_source_batch":
            _resolve_summary_normalization_attention(
                check,
                summary_key="source_batch_summaries",
                count_key="warning_pack_count",
                resolutions=resolutions,
                resolved_statuses=("ready_with_warnings",),
            )
            _mark_check_ready_if_no_unresolved_source_warnings(check)


def _normalization_resolutions(checks: list[dict[str, object]]) -> dict[str, str]:
    resolutions: dict[str, str] = {}
    for check in checks:
        if check.get("id") != "portrait_frame_normalization" or check.get("ok") is not True:
            continue
        source_set_id = _optional_string(check.get("source_set_id"))
        set_id = _optional_string(check.get("set_id"))
        if source_set_id and set_id:
            resolutions[source_set_id] = set_id
    return resolutions


def _resolve_workflow_normalization_attention(
    check: dict[str, object],
    *,
    resolutions: dict[str, str],
) -> None:
    normalizable_source_ids = _string_list(check.get("normalizable_source_set_ids"))
    resolved_source_ids = [source_id for source_id in normalizable_source_ids if source_id in resolutions]
    if not resolved_source_ids:
        return
    check["normalization_resolved_summaries"] = _resolution_summaries(resolved_source_ids, resolutions)
    if set(normalizable_source_ids).issubset(resolutions):
        check["attention_reasons"] = [
            reason
            for reason in _string_list(check.get("attention_reasons"))
            if reason != "normalizable_size_mismatch"
        ]
    check["suggested_commands"] = [
        command
        for command in _string_list(check.get("suggested_commands"))
        if not _resolved_normalization_command(command, resolved_source_ids)
    ]
    if not _string_list(check.get("attention_reasons")) and not _string_list(check.get("errors")):
        check["ok"] = True
        check["status"] = "ready"
        check["next_actions"] = []


def _resolve_summary_normalization_attention(
    check: dict[str, object],
    *,
    summary_key: str,
    count_key: str,
    resolutions: dict[str, str],
    resolved_statuses: tuple[str, ...],
) -> None:
    summaries = _string_list(check.get(summary_key))
    filtered: list[str] = []
    resolved_source_ids: list[str] = []
    for summary in summaries:
        set_id = summary.split(":", 1)[0].strip()
        is_resolved = set_id in resolutions and any(marker in summary for marker in resolved_statuses)
        if is_resolved:
            resolved_source_ids.append(set_id)
            continue
        filtered.append(summary)
    if not resolved_source_ids:
        return
    check[summary_key] = filtered
    check["normalization_resolved_summaries"] = _resolution_summaries(resolved_source_ids, resolutions)
    count = _nonnegative_int(check.get(count_key))
    check[count_key] = max(0, count - len(_dedupe(resolved_source_ids)))


def _mark_check_ready_if_no_unresolved_source_warnings(check: dict[str, object]) -> None:
    if _string_list(check.get("errors")):
        return
    if _nonnegative_int(check.get("warning_pack_count")) > 0:
        return
    if _nonnegative_int(check.get("waiting_count")) > 0 or _nonnegative_int(check.get("insufficient_count")) > 0:
        return
    if _nonnegative_int(check.get("invalid_frame_pack_count")) > 0 or _nonnegative_int(check.get("failed_count")) > 0:
        return
    if not _string_list(check.get("normalization_resolved_summaries")):
        return
    check["ok"] = True
    check["status"] = "ready"
    check["next_actions"] = []


def _resolution_summaries(source_set_ids: Iterable[str], resolutions: dict[str, str]) -> list[str]:
    return [f"{source_id}: normalized as {resolutions[source_id]}" for source_id in _dedupe(source_set_ids)]


def _resolved_normalization_command(command: str, resolved_source_ids: Iterable[str]) -> bool:
    return "normalize_portrait_video_source_frames.py" in command and any(
        source_id in command for source_id in resolved_source_ids
    )


def _next_actions(checks: Iterable[dict[str, object]]) -> list[str]:
    actions: list[str] = []
    for check in checks:
        if check.get("ok") is True:
            continue
        actions.extend(_string_list(check.get("next_actions")))
    return _dedupe(actions)


def _attention_checks(checks: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "id": _optional_string(check.get("id")),
            "label": _optional_string(check.get("label")) or _optional_string(check.get("id")),
            "status": _optional_string(check.get("status")) or "unknown",
            "reasons": _attention_reasons(check),
            "next_actions": _string_list(check.get("next_actions")),
        }
        for check in checks
        if check.get("ok") is not True
    ]


def _attention_reasons(check: dict[str, object]) -> list[str]:
    if check.get("id") == "hatch_pet_imagegen_route_preflight":
        reasons: list[str] = []
        reasons.extend(_string_list(check.get("blockers")))
        reasons.extend(_string_list(check.get("errors")))
        reasons.extend(f"raw error code: {code}" for code in _string_list(check.get("raw_error_codes")))
        secondary_status = _optional_string(check.get("secondary_fallback_status"))
        if secondary_status:
            reasons.append(f"secondary fallback: {secondary_status}")
        codex_status = _optional_string(check.get("codex_exec_status"))
        if codex_status:
            reasons.append(f"codex exec: {codex_status}")
        ready_job_ids = _string_list(check.get("ready_job_ids"))
        if ready_job_ids:
            reasons.append("ready jobs: " + ", ".join(ready_job_ids))
        return _dedupe(reasons)
    if check.get("id") == "hatch_pet_imagegen_readiness":
        reasons: list[str] = []
        reasons.extend(_string_list(check.get("blockers")))
        reasons.extend(_string_list(check.get("errors")))
        reasons.extend(f"raw error code: {code}" for code in _string_list(check.get("raw_error_codes")))
        ready_job_ids = _string_list(check.get("ready_job_ids"))
        if ready_job_ids:
            reasons.append("ready jobs: " + ", ".join(ready_job_ids))
        blocked_job_count = _optional_int(check.get("blocked_job_count"))
        if blocked_job_count:
            reasons.append(f"blocked jobs: {blocked_job_count}")
        return _dedupe(reasons)
    if check.get("id") == "hatch_pet_base_intake_preflight":
        reasons: list[str] = []
        reasons.extend(_string_list(check.get("errors")))
        reasons.extend(_string_list(check.get("warnings")))
        source_provenance = _optional_string(check.get("source_provenance"))
        if source_provenance:
            reasons.append(f"source provenance: {source_provenance}")
        if isinstance(check.get("job_ready"), bool):
            reasons.append(f"job ready: {'yes' if check.get('job_ready') else 'no'}")
        if check.get("output_exists") is True:
            reasons.append("output already exists")
        return _dedupe(reasons)
    if check.get("id") == "pixel_pet_emote_mapping":
        reasons: list[str] = []
        reasons.extend(_string_list(check.get("errors")))
        reasons.extend(_string_list(check.get("warnings")))
        missing_motion_ids = _string_list(check.get("missing_motion_ids"))
        if missing_motion_ids:
            reasons.append("missing motions: " + ", ".join(missing_motion_ids))
        unsupported_expression_ids = _string_list(check.get("unsupported_expression_ids"))
        if unsupported_expression_ids:
            reasons.append("unsupported expressions: " + ", ".join(unsupported_expression_ids))
        return _dedupe(reasons)
    if check.get("id") == "pixel_pet_visual_qa":
        reasons: list[str] = []
        reasons.extend(_string_list(check.get("errors")))
        reasons.extend(_string_list(check.get("warnings")))
        suspicious_pixels = _optional_int(check.get("suspicious_edge_halo_pixel_count"))
        if suspicious_pixels:
            reasons.append(f"suspicious edge halo pixels: {suspicious_pixels}")
        suspicious_ratio = _optional_float(check.get("suspicious_edge_halo_ratio"))
        if suspicious_ratio:
            reasons.append(f"suspicious edge halo ratio: {suspicious_ratio}")
        return _dedupe(reasons)
    if check.get("id") == "pixel_pet_edge_style_brief":
        reasons: list[str] = []
        reasons.extend(_string_list(check.get("errors")))
        reasons.extend(_string_list(check.get("warnings")))
        reasons.extend(_string_list(check.get("blockers")))
        if isinstance(check.get("default_promotion_allowed"), bool):
            reasons.append(f"default promotion allowed: {'yes' if check.get('default_promotion_allowed') else 'no'}")
        suspicious_ratio = _optional_float(check.get("suspicious_edge_halo_ratio"))
        if suspicious_ratio:
            reasons.append(f"suspicious edge halo ratio: {suspicious_ratio}")
        return _dedupe(reasons)
    reasons: list[str] = []
    for key in (
        "attention_reports",
        "attention_reasons",
        "blockers",
        "errors",
        "validation_errors",
        "warnings",
        "item_summaries",
        "source_batch_summaries",
    ):
        reasons.extend(_string_list(check.get(key)))
    if check.get("id") == "portrait_frame_visual_qa":
        status = _optional_string(check.get("status"))
        if status:
            reasons.append(f"frame visual QA status: {status}")
        size_mismatch_count = _optional_int(check.get("size_mismatch_count"))
        if size_mismatch_count:
            reasons.append(f"size mismatches: {size_mismatch_count}")
        max_body_drift = _optional_float(check.get("max_body_drift"))
        if max_body_drift:
            reasons.append(f"max body drift: {max_body_drift}")
    return _dedupe(reasons)


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


def _inline_code_list(value: object) -> str:
    items = _string_list(value)
    return ", ".join(items) if items else "[]"


def _optional_string(value: object) -> str:
    return value if isinstance(value, str) and value else ""


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _optional_float(value: object) -> float | None:
    return value if isinstance(value, float) and value >= 0 else None


def _int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, int)]


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _nonnegative_float(value: object) -> float:
    if isinstance(value, int) and value >= 0:
        return float(value)
    return value if isinstance(value, float) and value >= 0 else 0.0


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
    parser.add_argument(
        "--portrait-candidate-report",
        action="append",
        default=[],
        help="Optional portrait candidate decision brief JSON report to include.",
    )
    parser.add_argument(
        "--portrait-source-create-report",
        action="append",
        default=[],
        help="Optional portrait AI-video source pack creation JSON report to include.",
    )
    parser.add_argument(
        "--liveportrait-preflight-report",
        action="append",
        default=[],
        help="Optional LivePortrait preflight JSON report to include.",
    )
    parser.add_argument(
        "--portrait-frame-preflight-report",
        action="append",
        default=[],
        help="Optional portrait AI-video frame preflight JSON report to include.",
    )
    parser.add_argument(
        "--portrait-frame-normalization-report",
        action="append",
        default=[],
        help="Optional portrait AI-video frame normalization JSON report to include.",
    )
    parser.add_argument(
        "--portrait-source-batch-report",
        action="append",
        default=[],
        help="Optional portrait AI-video source batch JSON report to include.",
    )
    parser.add_argument(
        "--portrait-source-process-report",
        action="append",
        default=[],
        help="Optional portrait AI-video source-pack process JSON report to include.",
    )
    parser.add_argument(
        "--portrait-video-handoff-report",
        action="append",
        default=[],
        help="Optional portrait AI-video handoff bundle JSON report to include.",
    )
    parser.add_argument(
        "--portrait-video-import-report",
        action="append",
        default=[],
        help="Optional portrait AI-video source-pack video import JSON report to include.",
    )
    parser.add_argument(
        "--portrait-frame-qa-report",
        action="append",
        default=[],
        help="Optional portrait AI-video frame visual QA JSON report to include.",
    )
    parser.add_argument(
        "--portrait-regeneration-brief-report",
        action="append",
        default=[],
        help="Optional portrait AI-video regeneration brief JSON report to include.",
    )
    parser.add_argument(
        "--portrait-retry-handoff-report",
        action="append",
        default=[],
        help="Optional portrait AI-video retry handoff JSON report to include.",
    )
    parser.add_argument(
        "--hatch-pet-imagegen-readiness-report",
        action="append",
        default=[],
        help="Optional hatch-pet imagegen readiness JSON report to include.",
    )
    parser.add_argument(
        "--hatch-pet-imagegen-route-preflight-report",
        action="append",
        default=[],
        help="Optional hatch-pet imagegen route preflight JSON report to include.",
    )
    parser.add_argument(
        "--hatch-pet-base-intake-report",
        action="append",
        default=[],
        help="Optional hatch-pet base intake preflight JSON report to include.",
    )
    parser.add_argument(
        "--pixel-pet-emote-mapping-report",
        action="append",
        default=[],
        help="Optional pixel-pet LLM expression-to-motion mapping JSON report to include.",
    )
    parser.add_argument(
        "--pixel-pet-visual-qa-report",
        action="append",
        default=[],
        help="Optional pixel-pet visual QA JSON report to include.",
    )
    parser.add_argument(
        "--pixel-pet-edge-style-brief-report",
        action="append",
        default=[],
        help="Optional pixel-pet edge-style decision brief JSON report to include.",
    )
    parser.add_argument(
        "--full-local-snapshot",
        action="store_true",
        help="Include the current local release QA artifact set under --snapshot-artifact-root.",
    )
    parser.add_argument(
        "--snapshot-artifact-root",
        default=str(DEFAULT_SNAPSHOT_ARTIFACT_ROOT),
        help="Artifact root used by --full-local-snapshot.",
    )
    parser.add_argument("--json", default="", help="Optional JSON output path.")
    parser.add_argument("--markdown", default="", help="Optional Markdown output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    snapshot = _snapshot_paths(args)
    payload = build_release_readiness_report(
        character_pack=Path(args.character_pack),
        app_dir=Path(args.app_dir),
        installer_path=None if args.skip_installer else Path(args.installer),
        llm_reports=[Path(item) for item in args.llm_report] + snapshot["llm_reports"],
        portrait_workflow_reports=[
            Path(item) for item in args.portrait_workflow_report
        ] + snapshot["portrait_workflow_reports"],
        portrait_candidate_reports=[
            Path(item) for item in args.portrait_candidate_report
        ] + snapshot["portrait_candidate_reports"],
        portrait_source_create_reports=[
            Path(item) for item in args.portrait_source_create_report
        ] + snapshot["portrait_source_create_reports"],
        liveportrait_preflight_reports=[
            Path(item) for item in args.liveportrait_preflight_report
        ] + snapshot["liveportrait_preflight_reports"],
        portrait_frame_preflight_reports=[
            Path(item) for item in args.portrait_frame_preflight_report
        ] + snapshot["portrait_frame_preflight_reports"],
        portrait_frame_normalization_reports=[
            Path(item) for item in args.portrait_frame_normalization_report
        ] + snapshot["portrait_frame_normalization_reports"],
        portrait_source_batch_reports=[
            Path(item) for item in args.portrait_source_batch_report
        ] + snapshot["portrait_source_batch_reports"],
        portrait_source_process_reports=[
            Path(item) for item in args.portrait_source_process_report
        ] + snapshot["portrait_source_process_reports"],
        portrait_video_handoff_reports=[
            Path(item) for item in args.portrait_video_handoff_report
        ] + snapshot["portrait_video_handoff_reports"],
        portrait_video_import_reports=[
            Path(item) for item in args.portrait_video_import_report
        ] + snapshot["portrait_video_import_reports"],
        portrait_frame_qa_reports=[
            Path(item) for item in args.portrait_frame_qa_report
        ] + snapshot["portrait_frame_qa_reports"],
        portrait_regeneration_brief_reports=[
            Path(item) for item in args.portrait_regeneration_brief_report
        ] + snapshot["portrait_regeneration_brief_reports"],
        portrait_retry_handoff_reports=[
            Path(item) for item in args.portrait_retry_handoff_report
        ] + snapshot["portrait_retry_handoff_reports"],
        hatch_pet_imagegen_readiness_reports=[
            Path(item) for item in args.hatch_pet_imagegen_readiness_report
        ] + snapshot["hatch_pet_imagegen_readiness_reports"],
        hatch_pet_imagegen_route_preflight_reports=[
            Path(item) for item in args.hatch_pet_imagegen_route_preflight_report
        ] + snapshot["hatch_pet_imagegen_route_preflight_reports"],
        hatch_pet_base_intake_reports=[
            Path(item) for item in args.hatch_pet_base_intake_report
        ] + snapshot["hatch_pet_base_intake_reports"],
        pixel_pet_emote_mapping_reports=[
            Path(item) for item in args.pixel_pet_emote_mapping_report
        ] + snapshot["pixel_pet_emote_mapping_reports"],
        pixel_pet_visual_qa_reports=[
            Path(item) for item in args.pixel_pet_visual_qa_report
        ] + snapshot["pixel_pet_visual_qa_reports"],
        pixel_pet_edge_style_brief_reports=[
            Path(item) for item in args.pixel_pet_edge_style_brief_report
        ] + snapshot["pixel_pet_edge_style_brief_reports"],
    )
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    _write_text(args.json, text + "\n")
    _write_text(args.markdown, render_release_readiness_markdown(payload))
    print(text)
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
