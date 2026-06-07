import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from guanghe_companion.character_generation_workflow import CharacterGenerationWorkflow


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "validate_character_draft.py"


def _brief():
    return {
        "character_id": "teal_echo_companion",
        "name": "Teal Echo",
        "title": "Draft companion",
        "description": "Original draft companion for validation.",
        "visual_keywords": ["teal accent", "visual novel portrait"],
        "personality_keywords": ["bright", "gentle"],
        "boundaries": ["No third-party IP"],
    }


def _run_tool(path: Path):
    return subprocess.run(
        [sys.executable, str(TOOL), str(path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _write_png(path: Path, size: tuple[int, int] = (64, 64)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (40, 90, 120, 255)).save(path)


def _complete_draft_artifacts(draft_dir: Path) -> None:
    _write_png(draft_dir / "spritesheet.png", (1536, 1872))
    shop_items = json.loads((draft_dir / "shop_items.json").read_text(encoding="utf-8"))
    for item in shop_items:
        _write_png(draft_dir / str(item["icon"]), (32, 32))

    candidate_path = draft_dir / "portrait_candidate.json"
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    for value in candidate["expressions"].values():
        paths = value.values() if isinstance(value, dict) else (value,)
        for path in paths:
            _write_png(draft_dir / str(path), (256, 512))
    candidate["status"] = "approved"
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")


def test_validate_character_draft_tool_accepts_generated_draft_metadata(tmp_path):
    draft = CharacterGenerationWorkflow(output_root=tmp_path / "generated").create_draft(_brief())

    result = _run_tool(draft.pack_dir)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["character_id"] == "teal_echo_companion"
    assert payload["import_ready"] is False
    assert payload["manual_qa_required"] is True
    assert payload["portrait_candidate_status"] == "candidate"
    assert "spritesheet.png missing; draft is not import-ready" in payload["warnings"]
    assert "portrait candidate still requires human approval" in payload["warnings"]
    assert payload["errors"] == []


def test_validate_character_draft_tool_requires_runtime_safe_candidate_before_import_ready(tmp_path):
    draft = CharacterGenerationWorkflow(output_root=tmp_path / "generated").create_draft(_brief())
    _complete_draft_artifacts(draft.pack_dir)

    result = _run_tool(draft.pack_dir)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["import_ready"] is False
    assert payload["manual_qa_required"] is True
    assert "portrait candidate approval_required must be false before import" in payload["warnings"]
    assert "portrait candidate runtime_manifest_safe must be true before import" in payload["warnings"]

    candidate_path = draft.pack_dir / "portrait_candidate.json"
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["approval_required"] = False
    candidate["runtime_manifest_safe"] = True
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")

    approved_result = _run_tool(draft.pack_dir)
    approved_payload = json.loads(approved_result.stdout)

    assert approved_result.returncode == 0
    assert approved_payload["ok"] is True
    assert approved_payload["import_ready"] is True
    assert approved_payload["manual_qa_required"] is False
    assert approved_payload["warnings"] == []


def test_validate_character_draft_tool_rejects_missing_portrait_candidate(tmp_path):
    draft = CharacterGenerationWorkflow(output_root=tmp_path / "generated").create_draft(_brief())
    (draft.pack_dir / "portrait_candidate.json").unlink()

    result = _run_tool(draft.pack_dir)

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert "missing required draft file: portrait_candidate.json" in payload["errors"]


def test_validate_character_draft_tool_rejects_unsafe_candidate_paths(tmp_path):
    draft = CharacterGenerationWorkflow(output_root=tmp_path / "generated").create_draft(_brief())
    candidate_path = draft.pack_dir / "portrait_candidate.json"
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    payload["expressions"]["neutral"] = "../neutral.png"
    candidate_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = _run_tool(draft.pack_dir)

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert "portrait_candidate.expressions.neutral path must stay inside portraits" in payload["errors"]
