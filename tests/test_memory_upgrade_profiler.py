import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_embedding_profiler_help_is_available_on_windows():
    result = subprocess.run([sys.executable, str(ROOT / "tools/profile_persistent_embeddings.py"), "--help"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "--corpus-profile" in result.stdout


def test_memory_metrics_measure_current_process_without_fake_rss():
    metrics = tool("memory_profile_metrics")
    assert metrics.peak_rss_bytes() > 0


def test_long_source_corpus_keeps_authoritative_lengths():
    benchmark = tool("benchmark_memory_index")
    rows = benchmark.records(50, corpus_profile="long-source")
    assert len(rows) == 50
    assert all(100 <= len(row.summary) <= 240 for row in rows)
    assert min(len(row.metadata["original_quote"]) for row in rows) >= 500
    assert max(len(row.metadata["original_quote"]) for row in rows) >= 2000
    assert all(row.normalized().metadata["original_quote"] == row.metadata["original_quote"] for row in rows)


def test_sqlite_profiler_closes_its_database_before_cleanup(tmp_path):
    output = tmp_path / "measurements.json"
    result = subprocess.run([sys.executable, str(ROOT / "tools/benchmark_memory_index.py"),
        "--sizes", "50", "--repeats", "1", "--writes", "1", "--output", str(output)],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"},
        capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["results"][0]["rows_decoded_for_four"] == 4
