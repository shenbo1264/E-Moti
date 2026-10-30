import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("companion_acceptance", ROOT / "tools" / "companion_acceptance.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def test_dataset_covers_every_required_scene():
    cases = tool.load_dataset()["cases"]
    assert {c["category"] for c in cases} == {
        "extract", "no_extract", "natural_correct", "natural_forget", "semantic_recall", "persona"}
    assert {c["scene"] for c in cases if c["category"] == "persona"} >= {"休息", "游戏", "工作", "拒绝"}
    assert all("rubric" in c for c in cases if c["category"] == "persona")


def test_persona_cases_never_report_a_result_without_a_model(tmp_path):
    case = next(c for c in tool.load_dataset()["cases"] if c["category"] == "persona")
    assert tool.run_case(case, tmp_path)["status"] == "not_run"


def test_runner_fails_on_missing_fact_and_passes_on_seeded_recall(tmp_path):
    missing = {"id": "m", "category": "extract", "chat": ["你好"], "stored": ["不存在的事实"]}
    assert tool.run_case(missing, tmp_path / "a")["status"] == "fail"
    seeded = {"id": "s", "category": "semantic_recall", "seed": ["我常去槐荫图书馆。"], "reopen": True,
              "query": "我常去哪个图书馆？", "recalled": ["槐荫"]}
    assert tool.run_case(seeded, tmp_path / "b")["status"] == "pass"
