import json
import importlib.util
from pathlib import Path

from guanghe_companion.controller import CompanionController
from guanghe_companion.expression_settings import normalize_expression_settings
from guanghe_companion.interaction_intents import InteractionIntent
from guanghe_companion.llm_smoke import run_configured_llm_dialogue_smoke
from guanghe_companion.llm_smoke import DEFAULT_LLM_SMOKE_PROMPTS
from guanghe_companion.visual_actions import VisualAction


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_tool(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_llm_smoke_prompts_use_player_like_scenarios():
    assert len(DEFAULT_LLM_SMOKE_PROMPTS) == 10
    assert all(any("\u4e00" <= char <= "\u9fff" for char in prompt) for prompt in DEFAULT_LLM_SMOKE_PROMPTS)
    assert not any(prompt.startswith("Player scenario") for prompt in DEFAULT_LLM_SMOKE_PROMPTS)
    assert not any("Please reply" in prompt for prompt in DEFAULT_LLM_SMOKE_PROMPTS)
    assert not any("motion_hint" in prompt for prompt in DEFAULT_LLM_SMOKE_PROMPTS)
    assert not any("[" in prompt or "]" in prompt for prompt in DEFAULT_LLM_SMOKE_PROMPTS)
    assert not any(prompt.startswith("Smoke turn") for prompt in DEFAULT_LLM_SMOKE_PROMPTS)


def test_default_llm_smoke_prompts_cover_quality_gate_emotional_cues():
    joined = "\n".join(DEFAULT_LLM_SMOKE_PROMPTS)

    assert "\u5b89\u9759" in joined
    assert "\u5f00\u5fc3" in joined
    assert "\u60ca\u8bb6" in joined
    assert "\u96be\u8fc7" in joined
    assert "\u56f0\u5026" in joined


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
    assert public["diagnostic"]["state_mutation_check"] == {"ok": True, "changed_fields": []}
    assert public["state_mutation_check"] == {"ok": True, "changed_fields": []}
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


def test_configured_llm_dialogue_smoke_reports_speech_quality_gap(tmp_path):
    class UnevenSpeechExpressor:
        enabled = True
        last_fallback_reason = ""
        last_visual_actions = (
            VisualAction(action_type="expression", action_id="calm", ttl_ms=3000, priority=70),
            VisualAction(action_type="motion", action_id="Default", ttl_ms=1800, priority=60),
        )
        last_interaction_intents = ()

        def __init__(self):
            self.calls = 0

        def express(self, request, effect=None):
            self.calls += 1
            if self.calls == 1:
                speech = "诊断调用保持正常。"
            elif self.calls == 2:
                speech = "嗯"
            else:
                speech = "这句话故意写得很长很长，超过本次 smoke 允许的上限。"
            return [
                {
                    "character_name": request.character_name,
                    "speech": speech,
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        dialogue_history_path=tmp_path / "dialogue-history.json",
        ai_expressor=UnevenSpeechExpressor(),
    )
    controller.expression_settings = normalize_expression_settings({"enabled": True, "api_key": "sk-secret"})

    report = run_configured_llm_dialogue_smoke(
        controller,
        prompts=("short", "long"),
        min_speech_chars=4,
        max_speech_chars=12,
    )
    public = report.to_public_dict()

    assert report.ok is False
    assert report.reason == "speech_quality:empty=0,short=1,long=1"
    assert public["speech_quality"] == {
        "min_speech_chars": 4,
        "max_speech_chars": 12,
        "empty_count": 0,
        "short_count": 1,
        "long_count": 1,
        "violations": [
            {"turn": 1, "kind": "short", "speech_len": 1},
            {"turn": 2, "kind": "long", "speech_len": 29},
        ],
    }
    assert public["state_mutation_check"] == {"ok": True, "changed_fields": []}


def test_configured_llm_dialogue_smoke_reports_non_growth_state_mutation(tmp_path):
    class MutatingExpressor:
        enabled = True
        last_fallback_reason = ""
        last_interaction_intents = ()
        last_visual_actions = ()

        def __init__(self):
            self.calls = 0

        def express(self, request, effect=None):
            self.calls += 1
            if self.calls > 1:
                controller.state.inventory["warm_milk"] = 1
                controller.state.memory_log.append(
                    {
                        "at": 0,
                        "kind": "llm_overreach",
                        "summary": "LLM tried to write memory",
                        "motion": "Default",
                    }
                )
            return [
                {
                    "character_name": request.character_name,
                    "speech": "I should only speak.",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    expressor = MutatingExpressor()
    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        dialogue_history_path=tmp_path / "dialogue-history.json",
        ai_expressor=expressor,
    )
    controller.expression_settings = normalize_expression_settings({"enabled": True, "api_key": "sk-secret"})

    report = run_configured_llm_dialogue_smoke(controller, prompts=("hello",))
    public = report.to_public_dict()

    assert report.ok is False
    assert report.reason == "growth_mutated"
    assert public["state_mutation_check"] == {
        "ok": False,
        "changed_fields": ["inventory", "memory_log"],
    }
    assert public["growth_before"]["inventory"] != public["growth_after"]["inventory"]
    assert public["growth_before"]["memory_log"] != public["growth_after"]["memory_log"]


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
    assert captured["kwargs"]["min_speech_chars"] == 8
    assert captured["kwargs"]["max_speech_chars"] == 80
    assert "sk-secret" not in capsys.readouterr().out


def test_llm_dialogue_smoke_entrypoint_writes_utf8_report_without_printing_key(monkeypatch, capsys, tmp_path):
    module = _load_tool(REPO_ROOT / "tools" / "llm_dialogue_smoke.py")
    report_path = tmp_path / "nested" / "smoke-report.json"

    class FakeReport:
        ok = True

        def to_public_dict(self):
            return {"ok": True, "reason": "", "speech_preview": "\u661f\u6c50\u5728\u8fd9\u91cc"}

    monkeypatch.setattr(module, "run_llm_dialogue_smoke", lambda *args, **kwargs: FakeReport())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-secret")

    assert module.main(["--provider", "deepseek", "--prompt", "hello", "--report", str(report_path)]) == 0

    stdout_payload = json.loads(capsys.readouterr().out)
    report_text = report_path.read_text(encoding="utf-8")
    report_payload = json.loads(report_text)
    assert stdout_payload == report_payload
    assert report_payload["speech_preview"] == "\u661f\u6c50\u5728\u8fd9\u91cc"
    assert "sk-secret" not in report_text


def test_llm_dialogue_smoke_dry_run_reports_sanitized_deepseek_settings_without_calling_provider(
    monkeypatch,
    capsys,
):
    module = _load_tool(REPO_ROOT / "tools" / "llm_dialogue_smoke.py")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("dry run must not call the provider smoke")

    monkeypatch.setattr(module, "run_llm_dialogue_smoke", fail_if_called)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-secret")

    assert module.main(["--provider", "deepseek", "--dry-run"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "ok": True,
        "reason": "",
        "dry_run": True,
        "would_call_api": False,
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "api_style": "chat_completions",
        "api_key_set": True,
        "timeout_seconds": 30.0,
    }
    assert "sk-secret" not in str(payload)


def test_llm_dialogue_smoke_dry_run_reports_missing_required_key_without_calling_provider(
    monkeypatch,
    capsys,
):
    module = _load_tool(REPO_ROOT / "tools" / "llm_dialogue_smoke.py")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("dry run must not call the provider smoke")

    monkeypatch.setattr(module, "run_llm_dialogue_smoke", fail_if_called)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("E_MOTI_LLM_API_KEY", raising=False)

    assert module.main(["--provider", "deepseek", "--dry-run"]) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["reason"] == "missing_api_key"
    assert payload["dry_run"] is True
    assert payload["would_call_api"] is False
    assert payload["api_key_set"] is False
