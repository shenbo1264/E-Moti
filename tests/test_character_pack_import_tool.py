import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from guanghe_companion.character_generation_workflow import CharacterGenerationWorkflow
from guanghe_companion.character_registry import CharacterRegistry


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "import_character_pack.py"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_complete_pack(root: Path, character_id: str = "teal_echo") -> Path:
    pack_dir = root / character_id
    (pack_dir / "item_icons").mkdir(parents=True)
    (pack_dir / "preview").mkdir()
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    Image.new("RGBA", (32, 32), (40, 90, 120, 255)).save(pack_dir / "item_icons" / "snack.png")
    Image.new("RGBA", (64, 64), (40, 90, 120, 255)).save(pack_dir / "preview" / "contact-sheet.png")
    _write_json(
        pack_dir / "character.json",
        {
            "character_id": character_id,
            "name": "Teal Echo",
            "title": "Desktop companion",
            "description": "Original complete import pack.",
            "spritesheet": "spritesheet.png",
            "motion_manifest": "motion_manifest.json",
            "default_mode": "Calm",
            "modes": ["Calm"],
            "mode_descriptions": {"Calm": "Calm response"},
            "motion_labels": {"Default": "Idle"},
        },
    )
    _write_json(
        pack_dir / "dialogue_style.json",
        {
            "tone": "calm",
            "keywords": ["desktop", "companion"],
            "fallback_style": "short companion lines",
        },
    )
    _write_json(
        pack_dir / "motion_manifest.json",
        {
            "sheet_columns": 8,
            "sheet_rows": 9,
            "frame_width": 192,
            "frame_height": 208,
            "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
        },
    )
    _write_json(
        pack_dir / "shop_items.json",
        [
            {
                "item_id": "snack",
                "name": "Snack",
                "category": "food",
                "icon": "item_icons/snack.png",
                "price": 1,
                "effects": {"mood": 1},
            }
        ],
    )
    return pack_dir


def _complete_generated_draft_runtime_assets(draft_dir: Path) -> None:
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(draft_dir / "spritesheet.png")
    shop_items = json.loads((draft_dir / "shop_items.json").read_text(encoding="utf-8"))
    for item in shop_items:
        icon = draft_dir / str(item["icon"])
        icon.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (32, 32), (40, 90, 120, 255)).save(icon)


def _set_draft_candidate_import_ready(draft_dir: Path) -> None:
    candidate_path = draft_dir / "portrait_candidate.json"
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["status"] = "approved"
    candidate["approval_required"] = False
    candidate["runtime_manifest_safe"] = True
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")


def _draft_brief() -> dict[str, object]:
    return {
        "character_id": "draft_echo",
        "name": "Draft Echo",
        "title": "Draft companion",
        "description": "Original draft companion for import validation.",
        "visual_keywords": ["teal", "visual novel portrait"],
        "personality_keywords": ["gentle"],
        "boundaries": ["No third-party IP"],
    }


def _run_tool(source: Path, target_root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), str(source), "--target-root", str(target_root), *extra],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_import_character_pack_tool_copies_valid_pack_to_user_root(tmp_path):
    source = _write_complete_pack(tmp_path / "source")
    target_root = tmp_path / "user-data" / "character_packs"

    result = _run_tool(source, target_root)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["character_id"] == "teal_echo"
    assert Path(payload["target_path"]) == target_root / "teal_echo"
    assert (target_root / "teal_echo" / "character.json").is_file()
    packs = CharacterRegistry(builtin_root=tmp_path / "empty-builtin", user_root=target_root).list_available_packs()
    assert [pack.character_id for pack in packs] == ["teal_echo"]


def test_import_character_pack_tool_rejects_generated_draft(tmp_path):
    draft = CharacterGenerationWorkflow(output_root=tmp_path / "generated").create_draft(_draft_brief())
    target_root = tmp_path / "user-data" / "character_packs"

    result = _run_tool(draft.pack_dir, target_root)

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert "spritesheet not found: spritesheet.png" in payload["errors"]
    assert not target_root.exists()


def test_import_character_pack_tool_rejects_complete_draft_until_portrait_candidate_is_import_ready(tmp_path):
    draft = CharacterGenerationWorkflow(output_root=tmp_path / "generated").create_draft(_draft_brief())
    _complete_generated_draft_runtime_assets(draft.pack_dir)
    target_root = tmp_path / "user-data" / "character_packs"

    result = _run_tool(draft.pack_dir, target_root)

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["errors"] == [
        "draft portrait candidate must be approved before import",
        "draft portrait candidate approval_required must be false before import",
        "draft portrait candidate runtime_manifest_safe must be true before import",
    ]
    assert not target_root.exists()

    _set_draft_candidate_import_ready(draft.pack_dir)
    approved_result = _run_tool(draft.pack_dir, target_root)
    approved_payload = json.loads(approved_result.stdout)

    assert approved_result.returncode == 0
    assert approved_payload["ok"] is True
    assert approved_payload["character_id"] == "draft_echo"
    assert (target_root / "draft_echo" / "character.json").is_file()


def test_import_character_pack_tool_rejects_existing_target_without_force(tmp_path):
    source = _write_complete_pack(tmp_path / "source")
    target_root = tmp_path / "user-data" / "character_packs"
    first = _run_tool(source, target_root)
    assert first.returncode == 0

    result = _run_tool(source, target_root)

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["errors"] == ["target character pack already exists: teal_echo"]


def test_import_character_pack_tool_force_replaces_existing_target(tmp_path):
    source = _write_complete_pack(tmp_path / "source")
    target_root = tmp_path / "user-data" / "character_packs"
    first = _run_tool(source, target_root)
    assert first.returncode == 0
    stale_file = target_root / "teal_echo" / "stale.txt"
    stale_file.write_text("old", encoding="utf-8")

    result = _run_tool(source, target_root, "--force")

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert not stale_file.exists()
    assert (target_root / "teal_echo" / "character.json").is_file()
