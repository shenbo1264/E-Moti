from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SOURCE_ROOT = Path("artifacts") / "portrait-video-source"
DEFAULT_OUTPUT_DIR = Path("artifacts") / "portrait-video-handoff"


@dataclass(frozen=True, slots=True)
class PortraitVideoSourcePackBundle:
    set_id: str
    source_pack_dir: str
    zip_path: str
    status: str
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "set_id": self.set_id,
            "source_pack_dir": self.source_pack_dir,
            "zip_path": self.zip_path,
            "status": self.status,
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class PortraitVideoSourcePackBundleReport:
    ok: bool
    source_root: str
    output_dir: str
    pack_count: int
    bundle_count: int
    failed_count: int
    bundles: tuple[PortraitVideoSourcePackBundle, ...]
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source_root": self.source_root,
            "output_dir": self.output_dir,
            "pack_count": self.pack_count,
            "bundle_count": self.bundle_count,
            "failed_count": self.failed_count,
            "bundles": [bundle.to_dict() for bundle in self.bundles],
            "errors": list(self.errors),
        }


def bundle_portrait_video_source_packs(
    *,
    source_root: Path | str = DEFAULT_SOURCE_ROOT,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
) -> PortraitVideoSourcePackBundleReport:
    root = Path(source_root)
    output = Path(output_dir)
    errors: list[str] = []
    if not root.is_dir():
        errors.append("source_root not found")
        return _report(source_root=root, output_dir=output, bundles=(), errors=tuple(errors))

    bundles: list[PortraitVideoSourcePackBundle] = []
    for source_pack in _source_pack_dirs(root):
        bundle = _bundle_one_source_pack(source_pack=source_pack, output_dir=output)
        errors.extend(bundle.errors)
        bundles.append(bundle)

    return _report(source_root=root, output_dir=output, bundles=tuple(bundles), errors=tuple(errors))


def _source_pack_dirs(root: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_dir() and (path / "source_pack.json").is_file()
    )


def _bundle_one_source_pack(*, source_pack: Path, output_dir: Path) -> PortraitVideoSourcePackBundle:
    metadata, metadata_errors = _read_metadata(source_pack / "source_pack.json")
    set_id = _metadata_string(metadata, "set_id") or source_pack.name
    zip_path = output_dir / f"{set_id}.zip"
    if metadata_errors:
        return PortraitVideoSourcePackBundle(
            set_id=set_id,
            source_pack_dir=str(source_pack),
            zip_path="",
            status="invalid",
            errors=metadata_errors,
        )

    reference_rel = _metadata_string(metadata, "reference_image")
    prompt_rel = _metadata_string(metadata, "prompt_path") or "gemini_prompt.md"
    provider_prompts_rel = _metadata_string(metadata, "provider_prompts_path") or "provider_prompts.md"
    path_errors = _metadata_path_errors(
        {
            "reference_image": reference_rel,
            "prompt_path": prompt_rel,
            "provider_prompts_path": provider_prompts_rel,
        }
    )
    if path_errors:
        return PortraitVideoSourcePackBundle(
            set_id=set_id,
            source_pack_dir=str(source_pack),
            zip_path="",
            status="invalid",
            errors=path_errors,
        )

    reference_path = source_pack / reference_rel
    prompt_path = source_pack / prompt_rel
    provider_prompts_path = source_pack / provider_prompts_rel
    required_files = {
        reference_rel: reference_path,
        prompt_rel: prompt_path,
        provider_prompts_rel: provider_prompts_path,
        "source_pack.json": source_pack / "source_pack.json",
    }
    missing = tuple(f"{name} not found" for name, path in required_files.items() if not path.is_file())
    if missing:
        return PortraitVideoSourcePackBundle(
            set_id=set_id,
            source_pack_dir=str(source_pack),
            zip_path="",
            status="invalid",
            errors=missing,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AI_VIDEO_HANDOFF_README.md", _handoff_readme(set_id=set_id, source_pack=source_pack))
        archive.write(prompt_path, arcname=prompt_rel)
        archive.write(provider_prompts_path, arcname=provider_prompts_rel)
        archive.write(source_pack / "source_pack.json", arcname="source_pack.json")
        archive.write(reference_path, arcname=reference_rel)

    return PortraitVideoSourcePackBundle(
        set_id=set_id,
        source_pack_dir=str(source_pack),
        zip_path=str(zip_path),
        status="bundled",
    )


def _read_metadata(path: Path) -> tuple[dict[str, object], tuple[str, ...]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, (f"source_pack.json invalid: {exc}",)
    if not isinstance(payload, dict):
        return {}, ("source_pack.json must be an object",)
    errors: list[str] = []
    for field in ("set_id", "reference_image"):
        if not isinstance(payload.get(field), str) or not str(payload.get(field)).strip():
            errors.append(f"source_pack.json.{field} must be a non-empty string")
    return payload, tuple(errors)


def _metadata_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _metadata_path_errors(paths: dict[str, str]) -> tuple[str, ...]:
    errors: list[str] = []
    for key, value in paths.items():
        path = Path(value)
        if (
            not value
            or path.is_absolute()
            or ".." in path.parts
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
        ):
            errors.append(f"source_pack.json.{key} must be a safe relative path")
    return tuple(errors)


def _handoff_readme(*, set_id: str, source_pack: Path) -> str:
    frames_dir = source_pack / "frames"
    video_dir = source_pack / "video"
    return "\n".join(
        [
            "# AI Video Portrait Handoff",
            "",
            f"Set id: `{set_id}`",
            "",
            "Use the image under `reference/` as the identity anchor.",
            "",
            "Provider options: Pika, Hailuo, Kling, PixVerse, Runway, Vidu, LivePortrait.",
            "",
            "Use `provider_prompts.md` when Gemini is unavailable. `gemini_prompt.md` is kept as the baseline prompt.",
            "",
            "After the video provider finishes:",
            "",
            f"- Save the raw video into `{video_dir}`.",
            f"- Put exported PNG frames back into `{frames_dir}`.",
            "- Keep frame names sequential, for example `frame_0001.png`.",
            "",
            "Do not commit generated videos or rejected frames unless they are explicitly approved release assets.",
            "",
        ]
    )


def _report(
    *,
    source_root: Path,
    output_dir: Path,
    bundles: tuple[PortraitVideoSourcePackBundle, ...],
    errors: tuple[str, ...],
) -> PortraitVideoSourcePackBundleReport:
    bundle_count = sum(1 for bundle in bundles if bundle.status == "bundled")
    failed_count = sum(1 for bundle in bundles if bundle.status == "invalid")
    return PortraitVideoSourcePackBundleReport(
        ok=not errors and failed_count == 0,
        source_root=str(source_root),
        output_dir=str(output_dir),
        pack_count=len(bundles),
        bundle_count=bundle_count,
        failed_count=failed_count,
        bundles=bundles,
        errors=errors,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bundle AI video portrait source packs into handoff zip files.")
    parser.add_argument("source_root", nargs="?", default=str(DEFAULT_SOURCE_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = bundle_portrait_video_source_packs(source_root=args.source_root, output_dir=args.output_dir)
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
