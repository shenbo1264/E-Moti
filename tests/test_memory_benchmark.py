from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "memory_benchmark.py"
DATASET = ROOT / "tests" / "fixtures" / "memory_benchmark.json"


def _run(tmp_path: Path, *args: str):
    output = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, str(TOOL), "--repo", str(ROOT), "--output", str(output), *args],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    report = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else None
    return result, report


def test_benchmark_fixture_covers_failure_domains_without_query_leakage() -> None:
    cases = json.loads(DATASET.read_text(encoding="utf-8"))["cases"]
    assert 24 <= len(cases) <= 40
    assert len({case["id"] for case in cases}) == len(cases)
    assert {case["category"] for case in cases} >= {
        "recall", "irrelevant", "correction", "forgetting", "derived", "isolation",
        "temporal", "fabrication", "persona", "migration",
    }
    for case in cases:
        assert case["expect"], case["id"]
        # A user's present question quoting the old value is not a memory leak.
        for forbidden in case["expect"].get("prompt_absent", []):
            assert forbidden not in case.get("query", ""), case["id"]


def test_benchmark_observes_actual_final_prompt_and_repository(tmp_path: Path) -> None:
    result, report = _run(tmp_path, "--case", "recall_drink")
    assert result.returncode == 0, result.stderr or result.stdout
    case = report["results"][0]
    assert case["observed"]["retrieved"]
    assert "白桃乌龙" in case["observed"]["prompt"]
    assert Path(case["observed"]["loaded_service_file"]) == ROOT / "src" / "guanghe_companion" / "emotional_memory_service.py"
    assert report["summary"]["final_prompt_delivery"] == {"numerator": 1, "denominator": 1, "rate": 1.0}
    assert report["summary"]["model_response_latency"] == "not_run"


def test_benchmark_returns_failure_for_unmet_positive_prompt_assertion(tmp_path: Path) -> None:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    case = payload["cases"][0]
    case["expect"] = {"prompt_contains": ["a fact that was never ingested -- 5be11d7e"]}
    dataset = tmp_path / "negative_control.json"
    dataset.write_text(json.dumps({"version": 1, "cases": [case]}, ensure_ascii=False), encoding="utf-8")
    result, report = _run(tmp_path, "--dataset", str(dataset))
    assert result.returncode == 1
    assert report["summary"]["failed"] == 1
    assert report["summary"]["final_prompt_delivery"]["rate"] == 0.0
    assert not report["results"][0]["checks"][0]["passed"]


def test_benchmark_cannot_report_success_for_empty_case_selection(tmp_path: Path) -> None:
    result, report = _run(tmp_path, "--case", "case_does_not_exist")
    assert result.returncode == 2
    assert "unknown case ids" in result.stderr
    assert report is None
