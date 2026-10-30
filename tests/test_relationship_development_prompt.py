import json

from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.expression_prompt_budget import fit_prompt
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def add_shared_moment(controller):
    return controller.story_runtime.record_settled_events([{
        "event_type": "inventory", "event_id": "actual-gift:1",
        "payload": {"action": "gift", "item_id": "star", "item_name": "星形纪念品", "first_time": True},
    }], now=int(controller.now))[0]


def request(controller, development=None):
    context = controller.get_expression_context()
    context["relationship_development"] = (controller.story_runtime.relationship_development(now=int(controller.now))
                                            if development is None else development)
    return ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=context)


def test_grounded_relationship_guidance_reaches_actual_prompt_without_changing_persona(tmp_path):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        original_persona = controller.get_expression_context()["persona"]
        memory_id = add_shared_moment(controller)
        typed = request(controller)
        prompt = controller.ai_expressor.build_prompt(typed)
        evidence = json.loads(next(line.removeprefix("emotional_memory: ") for line in prompt.splitlines()
                                   if line.startswith("emotional_memory: ")))
        development = evidence["relationship_development"]
        assert development["source_memory_ids"] == [memory_id]
        assert development["expression_stage"] == "first_shared_moments"
        assert development["expression_hint"] in prompt
        assert "不改写 persona" in prompt
        assert typed.persona == original_persona
    finally:
        controller.close()


def test_stale_development_does_not_reenter_prompt_after_forgetting(tmp_path):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        memory_id = add_shared_moment(controller)
        previous = controller.story_runtime.relationship_development(now=int(controller.now))
        controller.memory_album_controller.forget(memory_id, now=int(controller.now))
        typed = request(controller, previous)
        assert "relationship_development" not in typed.emotional_memory
        current = request(controller)
        assert current.emotional_memory["relationship_development"]["expression_stage"] == "getting_acquainted"
        assert memory_id not in controller.ai_expressor.build_prompt(current)
    finally:
        controller.close()


def test_excessive_or_unbound_development_is_excluded(tmp_path):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        add_shared_moment(controller)
        development = controller.story_runtime.relationship_development(now=int(controller.now))
        excessive = {**development, "source_memory_ids": development["source_memory_ids"] * 7}
        assert "relationship_development" not in request(controller, excessive).emotional_memory
        unbound = {**development, "source_fingerprints": {}}
        assert "relationship_development" not in request(controller, unbound).emotional_memory
    finally:
        controller.close()


def test_prompt_budget_drops_derived_guidance_before_facts_and_identity():
    persona = {"identity_version": "pack-v1", "speech_style": "自然好奇", "traits": ["有主见"]}
    fact = {"memory_id": "fact", "summary": "用户明确说过的事实" * 10}
    memory = {"shared_memories": [fact]}
    lines = ["player_message: 当前问题必须保留", "persona: " + json.dumps(persona, ensure_ascii=False),
             "emotional_memory: " + json.dumps(memory, ensure_ascii=False)]
    baseline = fit_prompt(list(lines), limit=8192)
    memory["relationship_development"] = {"expression_hint": "派生表达指引" * 80}
    lines[-1] = "emotional_memory: " + json.dumps(memory, ensure_ascii=False)
    rendered = fit_prompt(lines, limit=len(baseline) + 10)
    assert "当前问题必须保留" in rendered
    actual = json.loads(next(line.removeprefix("emotional_memory: ") for line in rendered.splitlines()
                             if line.startswith("emotional_memory: ")))
    assert actual["shared_memories"] == [fact]
    assert "relationship_development" not in actual
    assert json.loads(next(line.removeprefix("persona: ") for line in rendered.splitlines()
                          if line.startswith("persona: "))) == persona
