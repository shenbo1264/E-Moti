from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Sequence

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.controller import CompanionController

CHARACTER_IDS = ("xingxi_pixel_pet", "ikaros_pixel_pet", "nairong_pixel_pet")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a reproducible E-Moti simulated playthrough.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--skip-live-voice", action="store_true")
    parser.add_argument("--user-data-root", default="")
    args = parser.parse_args(argv)

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.user_data_root:
        user_data_root = Path(args.user_data_root)
        user_data_root.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="emoti-playthrough-")
        user_data_root = Path(temp_dir.name)

    try:
        payload = _run_playthrough(user_data_root=user_data_root, skip_live_voice=args.skip_live_voice)
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0 if payload["ok"] else 1
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def _run_playthrough(*, user_data_root: Path, skip_live_voice: bool) -> dict[str, object]:
    characters: list[dict[str, object]] = []
    interaction_reports: list[dict[str, object]] = []
    errors: list[str] = []

    for character_id in CHARACTER_IDS:
        controller = CompanionController(
            character_id=character_id,
            user_data_root=user_data_root,
            auto_load=False,
        )
        try:
            pack = controller.character_pack
            before = controller.get_typed_snapshot()
            snapshot = controller.perform_action("touch", include_ai_expression=False)
            after = controller.get_typed_snapshot()
            characters.append(
                {
                    "character_id": pack.character_id,
                    "name": pack.name,
                    "renderer_backend": pack.renderer.backend,
                    "voice_provider": pack.tts_profile.provider,
                    "voice_backend_provider": pack.tts_profile.backend_provider,
                    "synthesis_language": pack.tts_profile.synthesis_language,
                }
            )
            interaction_reports.append(
                {
                    "character_id": pack.character_id,
                    "action": "touch",
                    "feedback_present": bool(snapshot.get("feedback")),
                    "events_after": len(after.events),
                    "stats_changed": after.stats != before.stats,
                }
            )
        except Exception as exc:
            errors.append(f"{character_id}: {exc}")
        finally:
            controller.close()

    interaction_ok = (
        len(interaction_reports) == len(CHARACTER_IDS)
        and all(item["feedback_present"] for item in interaction_reports)
        and all(item["events_after"] >= 1 for item in interaction_reports)
    )
    return {
        "ok": not errors and interaction_ok,
        "characters": characters,
        "interaction_loop": {
            "ok": interaction_ok,
            "reports": interaction_reports,
        },
        "voice": {
            "skipped": skip_live_voice,
            "live_voice_scope": "not run" if skip_live_voice else "not implemented in dry-run tool",
        },
        "errors": errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())

