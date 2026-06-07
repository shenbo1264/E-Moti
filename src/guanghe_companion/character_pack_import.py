from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .character_registry import validate_character_pack_dir


@dataclass(frozen=True, slots=True)
class CharacterPackImportReport:
    ok: bool
    character_id: str
    source_path: Path
    target_path: Path
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "character_id": self.character_id,
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
            source_path=source,
            target_path=target,
            errors=tuple(validation.errors),
        )

    safety_error = _target_safety_error(source, target_base, target)
    if safety_error:
        return CharacterPackImportReport(
            ok=False,
            character_id=validation.character_id,
            source_path=source,
            target_path=target,
            errors=(safety_error,),
        )
    if target.exists() and not force:
        return CharacterPackImportReport(
            ok=False,
            character_id=validation.character_id,
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
            source_path=source,
            target_path=target,
            errors=(f"copy failed: {exc}",),
        )

    return CharacterPackImportReport(
        ok=True,
        character_id=validation.character_id,
        source_path=source,
        target_path=target,
        errors=(),
    )


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
