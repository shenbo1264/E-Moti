from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.art.create_portrait_video_source_pack import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    create_portrait_video_source_pack,
)


SAFE_SET_SEGMENT = re.compile(r"[^a-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class PortraitVideoSourcePackCreateItem:
    expression_id: str
    variant: str
    set_id: str
    source_image: str
    output_dir: str
    status: str
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "expression_id": self.expression_id,
            "variant": self.variant,
            "set_id": self.set_id,
            "source_image": self.source_image,
            "output_dir": self.output_dir,
            "status": self.status,
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class PortraitVideoSourcePacksFromCandidateReport:
    ok: bool
    candidate_manifest_path: str
    output_root: str
    requested_count: int
    created_count: int
    failed_count: int
    packs: tuple[PortraitVideoSourcePackCreateItem, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "candidate_manifest_path": self.candidate_manifest_path,
            "output_root": self.output_root,
            "requested_count": self.requested_count,
            "created_count": self.created_count,
            "failed_count": self.failed_count,
            "packs": [pack.to_dict() for pack in self.packs],
            "errors": list(self.errors),
        }


def create_portrait_video_source_packs_from_candidate(
    *,
    candidate_manifest_path: Path | str,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    set_id_prefix: str,
    set_id_suffix: str = "",
    character_name: str = "Xingxi",
    source_label_prefix: str = "VN portrait candidate",
) -> PortraitVideoSourcePacksFromCandidateReport:
    manifest = Path(candidate_manifest_path)
    output = Path(output_root)
    payload, read_errors = _read_candidate_manifest(manifest)
    if read_errors:
        return _report(
            candidate_manifest_path=manifest,
            output_root=output,
            packs=(),
            errors=read_errors,
        )

    expression_refs, ref_errors = _expression_references(payload)
    packs: list[PortraitVideoSourcePackCreateItem] = []
    errors: list[str] = list(ref_errors)

    for expression_id, variant, relative_path in expression_refs:
        set_id = _build_set_id(set_id_prefix=set_id_prefix, expression_id=expression_id, set_id_suffix=set_id_suffix)
        source_image = manifest.parent / relative_path
        if not _is_safe_relative_path(relative_path):
            error = f"expressions.{expression_id}.{variant} must be a safe relative path"
            errors.append(error)
            packs.append(
                PortraitVideoSourcePackCreateItem(
                    expression_id=expression_id,
                    variant=variant,
                    set_id=set_id,
                    source_image=str(source_image),
                    output_dir="",
                    status="invalid",
                    errors=(error,),
                )
            )
            continue

        source_label = f"{source_label_prefix.strip() or 'VN portrait candidate'} {expression_id}.{variant}"
        created = create_portrait_video_source_pack(
            source_image_path=source_image,
            output_root=output,
            set_id=set_id,
            character_name=character_name,
            source_label=source_label,
        )
        status = "created" if created.ok else "failed"
        errors.extend(created.errors)
        packs.append(
            PortraitVideoSourcePackCreateItem(
                expression_id=expression_id,
                variant=variant,
                set_id=created.set_id if created.ok else set_id,
                source_image=str(source_image),
                output_dir=created.output_dir,
                status=status,
                errors=created.errors,
            )
        )

    return _report(
        candidate_manifest_path=manifest,
        output_root=output,
        packs=tuple(packs),
        errors=tuple(errors),
    )


def _read_candidate_manifest(path: Path) -> tuple[dict[str, object], tuple[str, ...]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, (f"portrait_candidate.json invalid: {exc}",)
    if not isinstance(payload, dict):
        return {}, ("portrait_candidate.json must be an object",)
    return payload, ()


def _expression_references(payload: dict[str, object]) -> tuple[
    tuple[tuple[str, str, str], ...],
    tuple[str, ...],
]:
    expressions = payload.get("expressions")
    if not isinstance(expressions, dict) or not expressions:
        return (), ("portrait_candidate.json.expressions must be a non-empty object",)

    refs: list[tuple[str, str, str]] = []
    errors: list[str] = []
    for raw_expression_id, value in sorted(expressions.items()):
        expression_id = str(raw_expression_id).strip()
        if not expression_id:
            errors.append("portrait_candidate.json.expressions keys must be non-empty")
            continue
        if isinstance(value, str):
            refs.append((expression_id, "open", value))
            continue
        if isinstance(value, dict) and isinstance(value.get("open"), str):
            refs.append((expression_id, "open", str(value["open"])))
            continue
        errors.append(f"expressions.{expression_id}.open must be a string")
    return tuple(refs), tuple(errors)


def _build_set_id(*, set_id_prefix: str, expression_id: str, set_id_suffix: str) -> str:
    parts = [_safe_set_segment(set_id_prefix), _safe_set_segment(expression_id), _safe_set_segment(set_id_suffix)]
    return "-".join(part for part in parts if part)


def _safe_set_segment(value: str) -> str:
    cleaned = SAFE_SET_SEGMENT.sub("-", value.lower().strip()).strip("-._")
    return cleaned


def _is_safe_relative_path(value: str) -> bool:
    path = Path(value)
    return (
        bool(value)
        and not path.is_absolute()
        and ".." not in path.parts
        and any(part == "portraits" for part in path.parts[:1])
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
    )


def _report(
    *,
    candidate_manifest_path: Path,
    output_root: Path,
    packs: tuple[PortraitVideoSourcePackCreateItem, ...],
    errors: tuple[str, ...],
) -> PortraitVideoSourcePacksFromCandidateReport:
    created_count = sum(1 for pack in packs if pack.status == "created")
    failed_count = sum(1 for pack in packs if pack.status in {"failed", "invalid"})
    return PortraitVideoSourcePacksFromCandidateReport(
        ok=not errors and failed_count == 0,
        candidate_manifest_path=str(candidate_manifest_path),
        output_root=str(output_root),
        requested_count=len(packs),
        created_count=created_count,
        failed_count=failed_count,
        packs=packs,
        errors=errors,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create local Gemini video source packs from every expression in a portrait candidate."
    )
    parser.add_argument("candidate_manifest")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--set-id-prefix", required=True)
    parser.add_argument("--set-id-suffix", default="")
    parser.add_argument("--character-name", default="Xingxi")
    parser.add_argument("--source-label-prefix", default="VN portrait candidate")
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = create_portrait_video_source_packs_from_candidate(
        candidate_manifest_path=args.candidate_manifest,
        output_root=args.output_root,
        set_id_prefix=args.set_id_prefix,
        set_id_suffix=args.set_id_suffix,
        character_name=args.character_name,
        source_label_prefix=args.source_label_prefix,
    )
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
