import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/eval_memory_process_restart.py"


def module():
    spec = importlib.util.spec_from_file_location("process_restart_eval", SCRIPT)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def scenario(path):
    path.write_text(json.dumps({"id": "isolated_relation", "seed": ["我的修鞋师叫陆景舟。", "我喜欢喝乌龙茶。"],
        "recall": "我的修鞋师叫什么名字？", "forget": "请忘记我的修鞋师叫什么名字。",
        "after_forget": "我的修鞋师叫什么名字？另外，我喜欢喝什么茶？"}, ensure_ascii=False), encoding="utf-8")


def test_offline_chain_uses_distinct_processes_real_storage_and_no_provider(tmp_path):
    data = tmp_path / "scenario.json"
    scenario(data)
    output = tmp_path / "run"
    run = subprocess.run([sys.executable, str(SCRIPT), "--scenario", str(data), "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=90)
    assert run.returncode == 0, run.stderr
    report = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert report["status"] == "offline_checked"
    assert report["model_status"] == "not_run"
    assert len({stage["pid"] for stage in report["stages"]}) == 3
    assert all(stage["exit_code"] == 0 and stage["parent_pid"] == report["pid"] for stage in report["stages"])
    assert all(not stage["history_before"] for stage in report["stages"])
    after = report["stages"][-1]["storage_after"]
    assert len(after["active"]) == 1 and "乌龙茶" in after["active"][0]["summary"]
    assert any("陆景舟" in item["summary"] for item in after["retired"])
    assert report["budget"]["calls"] == 0
    assert not (output / "provider-calls.json").exists()


def test_durable_reservation_blocks_restart_after_interrupted_request(tmp_path):
    tool = module()
    state = tmp_path / "budget.json"
    tool.initialize_budget(state)
    payload = {"model": "deepseek-flash", "messages": [{"role": "user", "content": "预算检查"}], "max_tokens": 4096}
    saved = tool.reserve_on_disk(state, payload)
    assert saved["calls"] == 1 and saved["in_flight"]
    assert float(saved["reserved_peak_cny"]) > 0
    with pytest.raises(ValueError, match="in.flight"):
        tool.read_budget(state)


def test_cumulative_call_cap_is_not_reset_by_new_process(tmp_path):
    tool = module()
    state = tmp_path / "budget.json"
    tool.initialize_budget(state)
    data = json.loads(state.read_text())
    data.update(calls=10, reserved_peak_cny="0.40")
    state.write_text(json.dumps(data), encoding="utf-8")
    payload = {"model": "deepseek-flash", "messages": [{"role": "user", "content": "预算检查"}], "max_tokens": 4096}
    with pytest.raises(ValueError, match="limit"):
        tool.reserve_on_disk(state, payload)
    assert json.loads(state.read_text())["calls"] == 10


def test_peak_cost_guard_uses_the_previous_process_reservation(tmp_path):
    tool = module()
    state = tmp_path / "budget.json"
    tool.initialize_budget(state)
    data = json.loads(state.read_text())
    data.update(calls=2, reserved_peak_cny="0.49")
    state.write_text(json.dumps(data), encoding="utf-8")
    payload = {"model": "deepseek-flash", "messages": [{"role": "user", "content": "预算检查"}], "max_tokens": 4096}
    with pytest.raises(ValueError, match="0.50"):
        tool.reserve_on_disk(state, payload)
    assert json.loads(state.read_text())["reserved_peak_cny"] == "0.49"


def test_offline_extraction_failure_stops_without_later_processes(tmp_path):
    data = tmp_path / "scenario.json"
    scenario(data)
    value = json.loads(data.read_text(encoding="utf-8"))
    value["seed"] = ["我养护植物时用的记录册封皮是米白色。"]
    data.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "failed-run"
    run = subprocess.run([sys.executable, str(SCRIPT), "--scenario", str(data), "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=90)
    assert run.returncode == 1
    report = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert report["status"] == "stopped" and len(report["stages"]) == 1
    assert report["stages"][0]["exit_code"] == 1
    assert report["budget"]["calls"] == 0
    assert not (output / "verify.json").exists()
