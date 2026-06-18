import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "create_character_draft.py"


def _brief() -> dict[str, object]:
    return {
        "character_id": "teal_echo_companion",
        "name": "Teal Echo",
        "title": "Draft companion",
        "description": "Original draft companion for validation.",
        "visual_keywords": ["teal accent", "visual novel portrait"],
        "personality_keywords": ["bright", "gentle"],
        "boundaries": ["No third-party IP"],
    }


def _run_tool(brief_path: Path, output_root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--brief", str(brief_path), "--output-root", str(output_root), *extra],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_create_character_draft_tool_writes_reproducible_draft(tmp_path):
    brief_path = tmp_path / "brief.json"
    output_root = tmp_path / "generated"
    brief_path.write_text(json.dumps(_brief(), ensure_ascii=False), encoding="utf-8")

    result = _run_tool(brief_path, output_root)

    payload = json.loads(result.stdout)
    draft_dir = output_root / "teal_echo_companion"
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["character_id"] == "teal_echo_companion"
    assert Path(payload["pack_dir"]) == draft_dir
    assert payload["import_ready"] is False
    assert payload["manual_qa_required"] is True
    assert payload["errors"] == []
    assert (draft_dir / "character.json").is_file()
    assert (draft_dir / "portrait_candidate.json").is_file()
    assert (draft_dir / "art_prompts.json").is_file()
    assert not (draft_dir / "spritesheet.png").exists()


def test_create_character_draft_tool_rejects_existing_output_without_force(tmp_path):
    brief_path = tmp_path / "brief.json"
    output_root = tmp_path / "generated"
    brief_path.write_text(json.dumps(_brief(), ensure_ascii=False), encoding="utf-8")
    first = _run_tool(brief_path, output_root)
    assert first.returncode == 0

    result = _run_tool(brief_path, output_root)

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["character_id"] == "teal_echo_companion"
    assert payload["errors"] == ["draft already exists: teal_echo_companion"]


def test_create_character_draft_tool_force_replaces_existing_output(tmp_path):
    brief_path = tmp_path / "brief.json"
    output_root = tmp_path / "generated"
    brief_path.write_text(json.dumps(_brief(), ensure_ascii=False), encoding="utf-8")
    first = _run_tool(brief_path, output_root)
    assert first.returncode == 0
    stale_file = output_root / "teal_echo_companion" / "stale.txt"
    stale_file.write_text("old", encoding="utf-8")

    result = _run_tool(brief_path, output_root, "--force")

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert not stale_file.exists()
    assert (output_root / "teal_echo_companion" / "qa_checklist.md").is_file()


def test_create_character_draft_tool_rejects_invalid_brief(tmp_path):
    brief_path = tmp_path / "brief.json"
    output_root = tmp_path / "generated"
    brief_path.write_text(json.dumps({"character_id": "../bad"}, ensure_ascii=False), encoding="utf-8")

    result = _run_tool(brief_path, output_root)

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["errors"] == ["invalid character brief"]
    assert not output_root.exists()
