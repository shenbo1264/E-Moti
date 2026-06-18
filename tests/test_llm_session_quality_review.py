from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_session_quality_review_flags_flat_repeated_speech() -> None:
    from tools.review_llm_session_quality import review_session_quality

    report = {
        "ok": True,
        "turns": [
            {"speech_preview": "嗯嗯。", "visual_actions": [{"type": "expression", "id": "neutral"}]},
            {"speech_preview": "嗯嗯。", "visual_actions": [{"type": "expression", "id": "neutral"}]},
            {"speech_preview": "嗯嗯。", "visual_actions": [{"type": "expression", "id": "neutral"}]},
        ],
        "state_mutation_check": {"changed_fields": []},
    }

    result = review_session_quality(report)

    assert result["ok"] is False
    assert "repeated_speech" in result["reasons"]
    assert "low_expression_diversity" in result["reasons"]


def test_session_quality_review_passes_diverse_state_safe_session() -> None:
    from tools.review_llm_session_quality import review_session_quality

    report = {
        "ok": True,
        "turns": [
            {"speech_preview": "我在这里。", "visual_actions": [{"type": "expression", "id": "joy"}]},
            {"speech_preview": "先慢慢来。", "visual_actions": [{"type": "expression", "id": "sleepy"}]},
            {"speech_preview": "我会安静陪你。", "visual_actions": [{"type": "expression", "id": "focused"}]},
            {"speech_preview": "这个按钮是切换角色。", "visual_actions": [{"type": "expression", "id": "confused"}]},
        ],
        "state_mutation_check": {"ok": True, "changed_fields": []},
    }

    result = review_session_quality(report)

    assert result["ok"] is True
    assert result["turn_count"] == 4
    assert result["expression_diversity_count"] == 4
    assert result["reasons"] == []


def test_session_quality_review_flags_state_mutation() -> None:
    from tools.review_llm_session_quality import review_session_quality

    result = review_session_quality(
        {
            "ok": True,
            "turns": [
                {"speech_preview": "我只是说话。", "visual_actions": [{"type": "expression", "id": "joy"}]},
                {"speech_preview": "不会改存档。", "visual_actions": [{"type": "expression", "id": "focused"}]},
                {"speech_preview": "但报告显示变了。", "visual_actions": [{"type": "expression", "id": "confused"}]},
            ],
            "state_mutation_check": {"ok": False, "changed_fields": ["inventory"]},
        }
    )

    assert result["ok"] is False
    assert "state_mutated" in result["reasons"]
    assert result["changed_fields"] == ["inventory"]


def test_session_quality_review_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    report_path = tmp_path / "session.json"
    json_path = tmp_path / "quality.json"
    markdown_path = tmp_path / "quality.md"
    report_path.write_text(
        json.dumps(
            {
                "ok": True,
                "turns": [
                    {"speech_preview": "嗯嗯。", "visual_actions": [{"type": "expression", "id": "neutral"}]},
                    {"speech_preview": "嗯嗯。", "visual_actions": [{"type": "expression", "id": "neutral"}]},
                    {"speech_preview": "嗯嗯。", "visual_actions": [{"type": "expression", "id": "neutral"}]},
                ],
                "state_mutation_check": {"ok": True, "changed_fields": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "tools/review_llm_session_quality.py",
            str(report_path),
            "--json",
            str(json_path),
            "--markdown",
            str(markdown_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 1
    stdout_payload = json.loads(result.stdout)
    saved_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert stdout_payload == saved_payload
    assert saved_payload["ok"] is False
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# LLM Session Quality Review" in markdown
    assert "- Turn count: `3`" in markdown
    assert "- Repeated speech: `failed`" in markdown
    assert "- State mutation: `passed`" in markdown
