from pathlib import Path
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/memory_holdout.py"


def test_holdout_preflight_keeps_model_metrics_unmeasured(tmp_path):
    output = tmp_path / "holdout.json"
    result = subprocess.run([sys.executable, str(TOOL), "--output", str(output)],
                            cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["dataset_kind"] == "synthetic_frozen_holdout"
    assert report["model_execution"] == "not_run"
    assert report["summary"]["answer_correctness"] == "not_run"
    assert report["summary"]["persona_behavior"] == "not_run"
    assert report["summary"]["provider_usage"] == "not_run"
    assert report["results"]
    for case in report["results"]:
        assert case["arms"]["current_memory"]["prompt"]
        assert case["arms"]["no_memory"]["prompt"]
        assert case["persona_equal_between_arms"]
        assert case["retrieved"] is not None


def test_holdout_rejects_unknown_case_and_missing_live_configuration(tmp_path):
    for args in (["--case", "does-not-exist"], ["--live"]):
        result = subprocess.run([sys.executable, str(TOOL), "--output", str(tmp_path / "out.json"), *args],
                                cwd=ROOT, capture_output=True, text=True, timeout=20)
        assert result.returncode == 2
        assert not (tmp_path / "out.json").exists()


def test_holdout_dataset_is_separate_and_has_no_probe_answer_leak():
    payload = json.loads((ROOT / "tests/fixtures/memory_holdout.json").read_text(encoding="utf-8"))
    dev = json.loads((ROOT / "tests/fixtures/memory_benchmark.json").read_text(encoding="utf-8"))
    assert len(dev["cases"]) == 38
    assert not ({row["id"] for row in payload["cases"]} & {row["id"] for row in dev["cases"]})
    assert {row["category"] for row in payload["cases"]} >= {"recall", "correction", "forgetting", "isolation", "persona", "fabrication", "irrelevant"}
    for case in payload["cases"]:
        assert any(step["op"] == "reopen" for step in case["steps"])
        for value in case.get("required", []) + case.get("forbidden", []):
            assert value not in case["query"]
