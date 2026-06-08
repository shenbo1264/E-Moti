from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _passing_report() -> dict[str, object]:
    return {
        "ok": True,
        "reason": "",
        "diagnostic": {
            "ok": True,
            "stage": "event_validation",
            "reason": "",
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
        },
        "turns": [
            {
                "turn": 1,
                "speech_len": 18,
                "speech_preview": "星汐在这里，先陪你安静一下。",
                "fallback_reason": "",
                "visual_actions": [{"type": "expression", "id": "calm"}],
            },
            {
                "turn": 2,
                "speech_len": 24,
                "speech_preview": "那我靠近一点，别急，慢慢说就好。",
                "fallback_reason": "",
                "visual_actions": [{"type": "motion", "id": "lean_in"}],
            },
        ],
        "visual_action_coverage": {
            "expression_count": 1,
            "expression_ids": ["calm"],
            "motion_count": 1,
            "motion_ids": ["lean_in"],
        },
        "speech_quality": {
            "min_speech_chars": 8,
            "max_speech_chars": 80,
            "empty_count": 0,
            "short_count": 0,
            "long_count": 0,
            "violations": [],
        },
        "state_mutation_check": {"ok": True, "changed_fields": []},
        "history_len": 4,
    }


def test_review_llm_smoke_report_marks_clean_report_passed():
    from tools.review_llm_smoke_report import review_llm_smoke_report, render_llm_smoke_review_markdown

    review = review_llm_smoke_report(_passing_report())

    assert review.ok is True
    assert review.status == "passed"
    assert review.provider == "deepseek"
    assert review.turn_count == 2
    assert review.issue_count == 0
    assert review.fallback_count == 0
    assert review.to_dict()["speech_quality"]["violation_count"] == 0
    markdown = render_llm_smoke_review_markdown(review)
    assert "# LLM Smoke Review" in markdown
    assert "- Status: `passed`" in markdown
    assert "- Speech quality violations: `0`" in markdown
    assert "- State guard: `passed`" in markdown


def test_review_llm_smoke_report_surfaces_speech_quality_failures():
    from tools.review_llm_smoke_report import review_llm_smoke_report, render_llm_smoke_review_markdown

    payload = _passing_report()
    payload["ok"] = False
    payload["reason"] = "speech_quality:empty=0,short=1,long=1"
    payload["speech_quality"] = {
        "min_speech_chars": 8,
        "max_speech_chars": 80,
        "empty_count": 0,
        "short_count": 1,
        "long_count": 1,
        "violations": [
            {"turn": 1, "kind": "short", "speech_len": 1},
            {"turn": 2, "kind": "long", "speech_len": 101},
        ],
    }

    review = review_llm_smoke_report(payload)

    assert review.ok is False
    assert review.status == "needs_attention"
    assert review.issue_count == 2
    issues = [issue.to_dict() for issue in review.issues]
    assert issues[0]["kind"] == "report_failed"
    assert issues[1]["kind"] == "speech_quality"
    assert review.to_dict()["speech_quality"]["violation_count"] == 2
    markdown = render_llm_smoke_review_markdown(review)
    assert "speech_quality:empty=0,short=1,long=1" in markdown
    assert "turn 1: short speech_len=1" in markdown
    assert "turn 2: long speech_len=101" in markdown


def test_review_llm_smoke_report_flags_legacy_report_without_speech_quality():
    from tools.review_llm_smoke_report import review_llm_smoke_report

    payload = _passing_report()
    payload.pop("speech_quality")

    review = review_llm_smoke_report(payload)

    assert review.ok is False
    assert review.status == "needs_attention"
    assert [issue.kind for issue in review.issues] == ["speech_quality_missing"]
    assert "rerun" in review.issues[0].message


def test_review_llm_smoke_report_cli_writes_json_and_markdown(tmp_path: Path):
    report_path = tmp_path / "llm-smoke.json"
    json_path = tmp_path / "review.json"
    markdown_path = tmp_path / "review.md"
    report_path.write_text(json.dumps(_passing_report(), ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "tools/review_llm_smoke_report.py",
            str(report_path),
            "--json",
            str(json_path),
            "--markdown",
            str(markdown_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout_payload = json.loads(result.stdout)
    saved_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert stdout_payload == saved_payload
    assert saved_payload["ok"] is True
    assert markdown_path.read_text(encoding="utf-8").startswith("# LLM Smoke Review")


def test_review_llm_smoke_reports_in_directory_skips_existing_review_outputs(tmp_path: Path):
    from tools.review_llm_smoke_report import (
        render_llm_smoke_batch_review_markdown,
        review_llm_smoke_reports_in_directory,
    )

    reports_dir = tmp_path / "llm_smoke"
    reports_dir.mkdir()
    (reports_dir / "passing.json").write_text(json.dumps(_passing_report(), ensure_ascii=False), encoding="utf-8")
    failing = _passing_report()
    failing["ok"] = False
    failing["reason"] = "speech_quality:empty=0,short=1,long=0"
    failing["speech_quality"] = {
        "min_speech_chars": 8,
        "max_speech_chars": 80,
        "empty_count": 0,
        "short_count": 1,
        "long_count": 0,
        "violations": [{"turn": 1, "kind": "short", "speech_len": 2}],
    }
    (reports_dir / "failing.json").write_text(json.dumps(failing, ensure_ascii=False), encoding="utf-8")
    (reports_dir / "passing-review.json").write_text('{"ok": true, "status": "passed"}', encoding="utf-8")

    batch = review_llm_smoke_reports_in_directory(reports_dir)

    assert batch["ok"] is False
    assert batch["report_count"] == 2
    assert batch["passed_count"] == 1
    assert batch["needs_attention_count"] == 1
    assert batch["invalid_count"] == 0
    assert [Path(item["path"]).name for item in batch["reports"]] == ["failing.json", "passing.json"]
    markdown = render_llm_smoke_batch_review_markdown(batch)
    assert "# LLM Smoke Batch Review" in markdown
    assert "failing.json" in markdown
    assert "passing-review.json" not in markdown


def test_review_llm_smoke_report_cli_accepts_directory(tmp_path: Path):
    reports_dir = tmp_path / "llm_smoke"
    reports_dir.mkdir()
    (reports_dir / "passing.json").write_text(json.dumps(_passing_report(), ensure_ascii=False), encoding="utf-8")
    json_path = tmp_path / "batch-review.json"
    markdown_path = tmp_path / "batch-review.md"

    result = subprocess.run(
        [
            sys.executable,
            "tools/review_llm_smoke_report.py",
            str(reports_dir),
            "--json",
            str(json_path),
            "--markdown",
            str(markdown_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout_payload = json.loads(result.stdout)
    assert stdout_payload["ok"] is True
    assert stdout_payload["report_count"] == 1
    assert json.loads(json_path.read_text(encoding="utf-8")) == stdout_payload
    assert markdown_path.read_text(encoding="utf-8").startswith("# LLM Smoke Batch Review")
