from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .character_registry import (
    DEFAULT_DISTRIBUTION_BOUNDARY,
    summarize_character_pack_dir,
    validate_character_pack_dir,
)


@dataclass(frozen=True, slots=True)
class CharacterPackImportReport:
    ok: bool
    character_id: str
    distribution_boundary: str
    source_path: Path
    target_path: Path
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "character_id": self.character_id,
            "distribution_boundary": self.distribution_boundary,
            "source_path": str(self.source_path),
            "target_path": str(self.target_path),
            "errors": list(self.errors),
        }


def import_character_pack_dir(
    source_dir: Path | str,
    *,
    target_root: Path | str,
    force: bool = False,
) -> CharacterPackImportReport:
    source = Path(source_dir)
    validation = validate_character_pack_dir(source, source="import_source")
    target_base = Path(target_root)
    target = target_base / validation.character_id
    if not validation.ok:
        return CharacterPackImportReport(
            ok=False,
            character_id=validation.character_id,
            distribution_boundary=DEFAULT_DISTRIBUTION_BOUNDARY,
            source_path=source,
            target_path=target,
            errors=tuple(validation.errors),
        )
    distribution_boundary = _source_distribution_boundary(source)

    draft_gate_errors = _draft_import_gate_errors(source)
    if draft_gate_errors:
        return CharacterPackImportReport(
            ok=False,
            character_id=validation.character_id,
            distribution_boundary=distribution_boundary,
            source_path=source,
            target_path=target,
            errors=draft_gate_errors,
        )

    safety_error = _target_safety_error(source, target_base, target)
    if safety_error:
        return CharacterPackImportReport(
            ok=False,
            character_id=validation.character_id,
            distribution_boundary=distribution_boundary,
            source_path=source,
            target_path=target,
            errors=(safety_error,),
        )
    if target.exists() and not force:
        return CharacterPackImportReport(
            ok=False,
            character_id=validation.character_id,
            distribution_boundary=distribution_boundary,
            source_path=source,
            target_path=target,
            errors=(f"target character pack already exists: {validation.character_id}",),
        )

    target_base.mkdir(parents=True, exist_ok=True)
    if target.exists():
        _remove_existing_target(target)
    try:
        shutil.copytree(source, target)
        copied_validation = validate_character_pack_dir(target, source="user")
        if not copied_validation.ok:
            _remove_existing_target(target)
            return CharacterPackImportReport(
                ok=False,
                character_id=validation.character_id,
                distribution_boundary=distribution_boundary,
                source_path=source,
                target_path=target,
                errors=tuple(copied_validation.errors),
            )
    except OSError as exc:
        if target.exists():
            _remove_existing_target(target)
        return CharacterPackImportReport(
            ok=False,
            character_id=validation.character_id,
            distribution_boundary=distribution_boundary,
            source_path=source,
            target_path=target,
            errors=(f"copy failed: {exc}",),
        )

    return CharacterPackImportReport(
        ok=True,
        character_id=validation.character_id,
        distribution_boundary=distribution_boundary,
        source_path=source,
        target_path=target,
        errors=(),
    )


def _source_distribution_boundary(source: Path) -> str:
    summary = summarize_character_pack_dir(source, source="import_source")
    if summary is None:
        return DEFAULT_DISTRIBUTION_BOUNDARY
    return summary.distribution_boundary


def _target_safety_error(source: Path, target_base: Path, target: Path) -> str:
    try:
        resolved_base = target_base.resolve()
        resolved_target = target.resolve()
        resolved_target.relative_to(resolved_base)
    except (OSError, ValueError):
        return "target path must stay inside target root"
    try:
        if source.resolve() == resolved_target:
            return "source and target character pack paths must be different"
    except OSError:
        return "source path cannot be resolved"
    return ""


def _remove_existing_target(target: Path) -> None:
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


def _draft_import_gate_errors(source: Path) -> tuple[str, ...]:
    candidate_path = source / "portrait_candidate.json"
    if not candidate_path.exists():
        return ()
    try:
        payload = json.loads(candidate_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return (f"portrait_candidate.json json invalid: {exc}",)
    if not isinstance(payload, dict):
        return ("portrait_candidate.json must be an object",)

    errors: list[str] = []
    status = payload.get("status")
    if not isinstance(status, str) or status.strip().lower() != "approved":
        errors.append("draft portrait candidate must be approved before import")
    if payload.get("approval_required") is not False:
        errors.append("draft portrait candidate approval_required must be false before import")
    if payload.get("runtime_manifest_safe") is not True:
        errors.append("draft portrait candidate runtime_manifest_safe must be true before import")
    return tuple(errors)
