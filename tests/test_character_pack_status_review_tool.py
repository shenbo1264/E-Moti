import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from guanghe_companion.character_generation_workflow import CharacterGenerationWorkflow


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "review_character_pack_status.py"


def _brief(policy: str = "original_inspiration") -> dict[str, object]:
    brief: dict[str, object] = {
        "character_id": "teal_echo_companion",
        "name": "Teal Echo",
        "title": "Draft companion",
        "description": "Original draft companion for validation.",
        "visual_keywords": ["teal accent", "visual novel portrait"],
        "personality_keywords": ["bright", "gentle"],
        "boundaries": ["No third-party IP"],
        "policy": policy,
    }
    if policy == "local_fanwork":
        brief["character_id"] = "teal_echo_fanwork"
        brief["source_character"] = "Example Source Character"
        brief["boundaries"] = ["Private local fanwork only", "Do not bundle or distribute"]
    return brief


def _run_tool(path: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(TOOL),
            str(path),
            "--json",
            str(tmp_path / "status.json"),
            "--markdown",
            str(tmp_path / "status.md"),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_runtime_pack(
    root: Path,
    *,
    metadata: bool = True,
    distribution_boundary: str = "shareable_after_review",
) -> Path:
    pack_dir = root / "runtime_character"
    (pack_dir / "item_icons").mkdir(parents=True)
    (pack_dir / "preview").mkdir()
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(pack_dir / "item_icons" / "snack.png")
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(pack_dir / "preview" / "contact-sheet.png")
    _write_json(
        pack_dir / "character.json",
        {
            "character_id": "runtime_character",
            "name": "Runtime Character",
            "title": "Complete companion",
            "description": "A complete local runtime pack.",
            "distribution_boundary": distribution_boundary,
            "spritesheet": "spritesheet.png",
            "motion_manifest": "motion_manifest.json",
            "default_mode": "Calm",
            "modes": ["Calm"],
            "mode_descriptions": {"Calm": "Quiet response."},
            "motion_labels": {"Default": "Idle"},
        },
    )
    _write_json(
        pack_dir / "dialogue_style.json",
        {"tone": "calm", "keywords": ["desktop"], "fallback_style": "short"},
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
    if metadata:
        (pack_dir / "provenance.md").write_text("Original local test pack.", encoding="utf-8")
        (pack_dir / "LICENSE.md").write_text("Pack assets are user-owned.", encoding="utf-8")
    return pack_dir


def test_review_character_pack_status_reports_generated_draft_next_actions(tmp_path):
    draft = CharacterGenerationWorkflow(output_root=tmp_path / "generated").create_draft(_brief())

    result = _run_tool(draft.pack_dir, tmp_path)

    payload = json.loads(result.stdout)
    saved_payload = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert result.returncode == 1
    assert payload == saved_payload
    assert payload["ok"] is False
    assert payload["pack_type"] == "draft"
    assert payload["status"] == "needs_manual_qa"
    assert payload["validation_ok"] is True
    assert payload["import_ready"] is False
    assert payload["manual_qa_required"] is True
    assert "generate spritesheet and item icons" in payload["next_actions"]
    assert "complete portrait candidate QA and approval" in payload["next_actions"]
    assert (tmp_path / "status.md").read_text(encoding="utf-8").startswith("# Character Pack Status Review")


def test_review_character_pack_status_marks_local_fanwork_private_only(tmp_path):
    draft = CharacterGenerationWorkflow(output_root=tmp_path / "generated").create_draft(_brief("local_fanwork"))

    result = _run_tool(draft.pack_dir, tmp_path)

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["pack_type"] == "draft"
    assert payload["distribution_boundary"] == "private_local_fanwork"
    assert payload["status"] == "private_only"
    assert "keep local fanwork private and out of open-source commits" in payload["next_actions"]


def test_review_character_pack_status_accepts_distribution_ready_runtime_pack(tmp_path):
    pack_dir = _write_runtime_pack(tmp_path / "packs", metadata=True)

    result = _run_tool(pack_dir, tmp_path)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["pack_type"] == "runtime_pack"
    assert payload["status"] == "ready"
    assert payload["validation_ok"] is True
    assert payload["import_ready"] is True
    assert payload["warnings"] == []
    assert payload["provenance_files"] == ["provenance.md"]
    assert payload["license_files"] == ["LICENSE.md"]


def test_review_character_pack_status_reads_runtime_distribution_boundary(tmp_path):
    pack_dir = _write_runtime_pack(
        tmp_path / "packs",
        metadata=True,
        distribution_boundary="local_ugc_only",
    )

    result = _run_tool(pack_dir, tmp_path)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["distribution_boundary"] == "local_ugc_only"


def test_review_character_pack_status_requires_distribution_metadata_for_runtime_pack(tmp_path):
    pack_dir = _write_runtime_pack(tmp_path / "packs", metadata=False)

    result = _run_tool(pack_dir, tmp_path)

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["pack_type"] == "runtime_pack"
    assert payload["status"] == "needs_distribution_review"
    assert payload["validation_ok"] is True
    assert payload["import_ready"] is True
    assert "add provenance note before sharing or bundling" in payload["next_actions"]
    assert "add license or usage-rights note before sharing or bundling" in payload["next_actions"]


def test_review_character_pack_status_accepts_bundled_original_pack(tmp_path):
    pack_dir = REPO_ROOT / "assets" / "companion" / "original_oc"

    result = _run_tool(pack_dir, tmp_path)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["pack_type"] == "runtime_pack"
    assert payload["status"] == "ready"
    assert payload["validation_ok"] is True
    assert payload["warnings"] == []
    assert "portrait_assets_provenance.md" in payload["provenance_files"]
    assert "LICENSE.md" in payload["license_files"]
