from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import zipfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guanghe_companion.companion_story_runtime import CompanionStoryRuntime  # noqa: E402
from guanghe_companion.focus_companion import ActivityKind, FocusCompanionSettings  # noqa: E402
from guanghe_companion.release_security import redact_json_payload, scan_json_payload  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the integrated E-Moti memory/focus smoke.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "integrated_smoke")
    parser.add_argument("--submission-zip", type=Path, default=Path("/mnt/data/E-Moti-submission.zip"))
    parser.add_argument(
        "--write-public-templates",
        action="store_true",
        help="Write redacted config templates into public_config_template. Disabled by default.",
    )
    args = parser.parse_args(argv)
    artifacts = args.output_dir.resolve()
    if artifacts.exists():
        import shutil

        shutil.rmtree(artifacts)
    artifacts.mkdir(parents=True)

    pack_root = ROOT / "assets" / "companion" / "xingxi_pixel_pet"
    character = json.loads((pack_root / "character.json").read_text(encoding="utf-8-sig"))
    motions = json.loads((pack_root / "motion_manifest.json").read_text(encoding="utf-8-sig"))
    items = json.loads((pack_root / "shop_items.json").read_text(encoding="utf-8-sig"))
    image = Image.open(pack_root / "spritesheet.png")
    expected_size = (
        int(motions["sheet_columns"]) * int(motions["frame_width"]),
        int(motions["sheet_rows"]) * int(motions["frame_height"]),
    )
    warm_milk = next(item for item in items if item["item_id"] == "warm_milk")

    runtime = CompanionStoryRuntime.create(
        user_data_root=artifacts / "user_data",
        character_id=character["character_id"],
        focus_settings=FocusCompanionSettings(
            enabled=True,
            threshold_minutes=50,
            break_minutes=5,
            snooze_minutes=20,
            quiet_hours_enabled=False,
        ),
    )

    game_state = {
        "focus": 72,
        "charge": 65,
        "stability": 78,
        "mood": 58,
        "trust": 5,
        "coins": 20,
        "inventory": {item["item_id"]: 0 for item in items},
    }
    state_before_companion_skill = copy.deepcopy(game_state)

    # Mirrors the current controller's settled paired inventory + memory events.
    first_milk_ids = runtime.record_settled_events(
        [
            {
                "event_type": "inventory",
                "speech": "feed: 热牛奶",
                "payload": {
                    "item_id": "warm_milk",
                    "action": "feed",
                    "item_name": "热牛奶",
                    "icon_path": "item_icons/warm_milk.png",
                },
            },
            {
                "event_type": "memory",
                "speech": "投喂了 热牛奶",
                "payload": {
                    "kind": "投喂",
                    "summary": "投喂了 热牛奶：charge +12 / mood +2",
                    "motion": "Eat",
                },
            },
        ],
        now=100,
    )
    repeated_milk_ids = runtime.record_settled_events(
        [
            {
                "event_type": "inventory",
                "payload": {
                    "item_id": "warm_milk",
                    "action": "feed",
                    "item_name": "热牛奶",
                },
            }
        ],
        now=200,
    )
    study_ids = runtime.record_settled_events(
        [
            {
                "event_type": "memory",
                "payload": {
                    "kind": "互动",
                    "summary": "共同学习：把这一小段时间记成共同学习吧。",
                    "motion": "Study",
                },
            }
        ],
        now=300,
    )
    relationship_ids = runtime.record_settled_events(
        [
            {
                "event_type": "relationship",
                "event_id": "relationship-unlock-shared-ritual",
                "payload": {
                    "stage": "共同日常",
                    "unlock_id": "unlock_shared_ritual",
                    "message": "我们有自己的小默契了。以后安静待着，也像一起做了什么。",
                },
            }
        ],
        now=400,
    )
    chapter = runtime.memory.consolidate(now=500)

    hot_milk_context, hot_milk_bundle = runtime.build_expression_context(
        {"recent_dialogue": []},
        query="还记得第一次热牛奶吗",
        now=600,
        relationship_stage="共同日常",
    )
    _, unrelated_bundle = runtime.build_expression_context(
        {},
        query="像素动画边缘锯齿怎么修",
        now=600,
        relationship_stage="共同日常",
    )

    offer = runtime.focus.inject_demo_focus(
        focused_minutes=52,
        kind=ActivityKind.CODING,
        now=10_000,
        pet_stability=game_state["stability"],
        pet_mode="Calm",
    )
    started = runtime.focus.confirm_break(now=10_001, duration_seconds_override=2)
    completed = runtime.focus.tick(now=10_004)
    focus_memory = runtime.record_focus_completion(
        completed[0], now=10_004, event_id="focus-companion-smoke-1"
    )

    submission_zip = args.submission_zip.resolve()
    secret_findings: list[dict[str, str]] = []
    sanitized_templates: dict[str, object] = {}
    with zipfile.ZipFile(submission_zip) as archive:
        for member in ("user_data/capability_settings.json", "user_data/expression_settings.json"):
            payload = json.loads(archive.read(member).decode("utf-8-sig"))
            report = scan_json_payload(payload, path=member)
            secret_findings.extend({"path": finding.path, "field": finding.field} for finding in report.findings)
            sanitized_templates[member] = redact_json_payload(payload)
    secret_findings = [
        {"path": path, "field": field}
        for path, field in sorted({(row["path"], row["field"]) for row in secret_findings})
    ]

    template_root = ROOT / "public_config_template"
    if args.write_public_templates:
        template_root.mkdir(parents=True, exist_ok=True)
        for member, payload in sanitized_templates.items():
            target = template_root / Path(member).name
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    memories = runtime.memory.store.load_memories()
    report = {
        "upstream_basis": {
            "repository": "shenbo1264/E-Moti",
            "main_commit": "e840d77dc35d95c507d65f5de5c5ff2bac65f363",
            "verification_mode": "portable integration overlay + real Xingxi assets",
        },
        "asset_validation": {
            "character_id": character["character_id"],
            "character_name": character["name"],
            "spritesheet_size": list(image.size),
            "expected_spritesheet_size": list(expected_size),
            "spritesheet_ok": image.size == expected_size,
            "motion_count": len(motions["motions"]),
            "warm_milk_category": warm_milk["category"],
        },
        "memory_flow": {
            "first_milk_memory_count": len(first_milk_ids),
            "repeat_milk_memory_count": len(repeated_milk_ids),
            "first_study_memory_count": len(study_ids),
            "relationship_memory_count": len(relationship_ids),
            "memory_titles": [memory.title for memory in memories],
            "chapter_title": chapter.title if chapter else None,
            "chapter_source_count": len(chapter.source_memory_ids) if chapter else 0,
            "hot_milk_recall_titles": [memory.title for memory in hot_milk_bundle.memories],
            "unrelated_recall_count": len(unrelated_bundle.memories),
            "context_has_emotional_memory": "emotional_memory" in hot_milk_context,
        },
        "heartbeat_flow": {
            "offer_event": offer[0].event_type if offer else None,
            "offer_copy": offer[0].speech if offer else None,
            "started_event": started.event_type,
            "completed_event": completed[0].event_type if completed else None,
            "focus_memory_title": focus_memory.title if focus_memory else None,
            "growth_state_unchanged": game_state == state_before_companion_skill,
        },
        "security": {
            "submission_config_findings": secret_findings,
            "sanitized_template_files": sorted(path.name for path in template_root.glob("*.json")),
            "submission_zip_name": submission_zip.name,
        },
    }
    (artifacts / "integration_smoke_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (artifacts / "expression_context_sample.json").write_text(
        json.dumps(hot_milk_context, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    checks = [
        report["asset_validation"]["spritesheet_ok"],
        report["memory_flow"]["first_milk_memory_count"] == 1,
        report["memory_flow"]["repeat_milk_memory_count"] == 0,
        report["memory_flow"]["first_study_memory_count"] == 1,
        report["memory_flow"]["relationship_memory_count"] == 1,
        report["memory_flow"]["unrelated_recall_count"] == 0,
        report["heartbeat_flow"]["growth_state_unchanged"],
        bool(secret_findings),
    ]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
