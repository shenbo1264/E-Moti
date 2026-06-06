import importlib.util
from pathlib import Path

from guanghe_companion.controller import CompanionController
from guanghe_companion.expression_settings import normalize_expression_settings
from guanghe_companion.interaction_intents import InteractionIntent
from guanghe_companion.llm_smoke import run_configured_llm_dialogue_smoke
from guanghe_companion.visual_actions import VisualAction


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_tool(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_configured_llm_dialogue_smoke_uses_llm_path_without_growth_mutation(tmp_path):
    class FakeExpressor:
        enabled = True
        last_fallback_reason = ""

        def express(self, request, effect=None):
            self.last_interaction_intents = (
                InteractionIntent(intent_id="offer_rest", ttl_ms=5000, priority=50, source="llm"),
            )
            return [
                {
                    "character_name": request.character_name,
                    "speech": "LLM says: " + request.feedback,
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        dialogue_history_path=tmp_path / "dialogue-history.json",
        ai_expressor=FakeExpressor(),
    )
    controller.expression_settings = normalize_expression_settings(
        {
            "enabled": True,
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-secret",
            "timeout_seconds": 30,
        }
    )

    report = run_configured_llm_dialogue_smoke(controller, prompts=("hello", "rest"))
    public = report.to_public_dict()

    assert report.ok is True
    assert public["ok"] is True
    assert public["reason"] == ""
    assert public["diagnostic"]["ok"] is True
    assert public["growth_before"] == public["growth_after"]
    assert public["history_len"] == 4
    assert [turn["fallback_reason"] for turn in public["turns"]] == ["", ""]
    assert all(str(turn["speech_preview"]).startswith("LLM says:") for turn in public["turns"])
    assert public["turns"][0]["interaction_intents"] == [
        {
            "id": "offer_rest",
            "ttl_ms": 5000,
            "priority": 50,
            "source": "llm",
        }
    ]
    assert "api_key" not in str(public)
    assert "sk-secret" not in str(public)


def test_configured_llm_dialogue_smoke_reports_turn_fallback(tmp_path):
    class FallbackExpressor:
        enabled = False
        last_fallback_reason = "disabled"

        def express(self, request, effect=None):
            raise AssertionError("disabled expressor should stop before call")

    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        dialogue_history_path=tmp_path / "dialogue-history.json",
        ai_expressor=FallbackExpressor(),
    )
    controller.expression_settings = normalize_expression_settings({"enabled": True, "api_key": "sk-secret"})

    report = run_configured_llm_dialogue_smoke(controller, prompts=("hello",))

    assert report.ok is False
    assert report.reason == "diagnostic:disabled"
    assert report.to_public_dict()["diagnostic"]["reason"] == "disabled"


def test_configured_llm_dialogue_smoke_reports_visual_action_coverage_gap(tmp_path):
    class SparseVisualExpressor:
        enabled = True
        last_fallback_reason = ""
        last_interaction_intents = ()

        def express(self, request, effect=None):
            self.last_visual_actions = (
                VisualAction(
                    action_type="expression",
                    action_id="calm",
                    ttl_ms=3000,
                    priority=70,
                ),
                VisualAction(
                    action_type="motion",
                    action_id="Default",
                    ttl_ms=1800,
                    priority=60,
                ),
            )
            return [
                {
                    "character_name": request.character_name,
                    "speech": "I am here.",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        dialogue_history_path=tmp_path / "dialogue-history.json",
        ai_expressor=SparseVisualExpressor(),
    )
    controller.expression_settings = normalize_expression_settings({"enabled": True, "api_key": "sk-secret"})

    report = run_configured_llm_dialogue_smoke(
        controller,
        prompts=("hello", "still here"),
        min_expression_actions=2,
        min_motion_actions=2,
    )
    public = report.to_public_dict()

    assert report.ok is False
    assert report.reason == "visual_action_coverage:expressions=1/2,motions=1/2"
    assert public["visual_action_coverage"] == {
        "expression_count": 1,
        "expression_ids": ["calm"],
        "motion_count": 1,
        "motion_ids": ["Default"],
    }


def test_llm_dialogue_smoke_entrypoint_reads_deepseek_env_without_printing_key(monkeypatch, capsys):
    module = _load_tool(REPO_ROOT / "tools" / "llm_dialogue_smoke.py")
    captured = {}

    class FakeReport:
        ok = True

        def to_public_dict(self):
            return {"ok": True, "reason": "", "provider": "deepseek"}

    def fake_run(settings, prompts, **kwargs):
        captured["settings"] = dict(settings)
        captured["prompts"] = prompts
        captured["kwargs"] = kwargs
        return FakeReport()

    monkeypatch.setattr(module, "run_llm_dialogue_smoke", fake_run)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-secret")

    assert module.main(["--provider", "deepseek", "--prompt", "hello"]) == 0

    assert captured["settings"]["api_key"] == "sk-secret"
    assert captured["prompts"] == ("hello",)
    assert captured["kwargs"]["min_expression_actions"] == 4
    assert captured["kwargs"]["min_motion_actions"] == 3
    assert "sk-secret" not in capsys.readouterr().out
