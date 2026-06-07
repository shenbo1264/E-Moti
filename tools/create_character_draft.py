from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.character_generation_workflow import CharacterGenerationWorkflow


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an E-Moti character draft from a local brief JSON file.")
    parser.add_argument("--brief", required=True, help="Path to a character brief JSON object.")
    parser.add_argument("--output-root", required=True, help="Directory where the draft folder will be created.")
    parser.add_argument("--force", action="store_true", help="Replace an existing draft with the same character_id.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    brief_path = Path(args.brief)
    output_root = Path(args.output_root)
    try:
        brief = _read_brief(brief_path)
        draft = CharacterGenerationWorkflow(output_root=output_root).create_draft(
            brief,
            force=args.force,
        )
    except FileExistsError as exc:
        character_id = Path(exc.filename or exc.args[0]).name
        _print_result(
            ok=False,
            character_id=character_id,
            pack_dir=output_root / character_id,
            errors=[f"draft already exists: {character_id}"],
        )
        return 1
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        _print_result(
            ok=False,
            character_id="",
            pack_dir=output_root,
            errors=[str(exc)],
        )
        return 1

    _print_result(
        ok=True,
        character_id=draft.character_id,
        pack_dir=draft.pack_dir,
        import_ready=draft.import_ready,
        manual_qa_required=draft.manual_qa_required,
        errors=[],
    )
    return 0


def _read_brief(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("brief JSON must be an object")
    return payload


def _print_result(
    *,
    ok: bool,
    character_id: str,
    pack_dir: Path,
    errors: list[str],
    import_ready: bool = False,
    manual_qa_required: bool = True,
) -> None:
    print(
        json.dumps(
            {
                "ok": ok,
                "character_id": character_id,
                "pack_dir": str(pack_dir),
                "import_ready": import_ready,
                "manual_qa_required": manual_qa_required,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
