import json

from guanghe_companion.expression_clients import MAX_OPENAI_PROMPT_LENGTH
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def test_large_valid_memory_and_persona_stay_inside_provider_budget(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        for i in range(12):
            c.story_runtime.memory.update_bond_profile(now=i+1,
                new_preference=str(i)+"咖啡"*39, new_boundary=str(i)+"安静"*45)
        for i in range(4):
            c.story_runtime.memory.remember(kind="玩家希望被记住", title=f"咖啡{i}", summary="咖啡"*120,
                                           source="explicit_user_request", now=20+i)
        c._current_player_message = "咖啡"
        context = c.get_expression_context()
        context["persona"]["traits"] = ["风格"*80+str(i) for i in range(12)]
        context["persona"]["preferences"] = ["偏好"*80+str(i) for i in range(12)]
        context["recent_dialogue"] = [{"role":"user", "speaker":"你", "text":"话"*240} for _ in range(5)]
        request = ExpressionRequest.from_snapshot(c.get_typed_snapshot(), context=context)
        rendered = c.ai_expressor.build_prompt(request)
        assert len(rendered) <= MAX_OPENAI_PROMPT_LENGTH
        # Complete JSON, stable identity and at least one grounded recall survive.
        persona = json.loads(next(line[len("persona: "):] for line in rendered.splitlines() if line.startswith("persona: ")))
        memory = json.loads(next(line[len("emotional_memory: "):] for line in rendered.splitlines() if line.startswith("emotional_memory: ")))
        assert persona["config_hash"] == context["persona"]["config_hash"]
        assert memory["shared_memories"]
    finally:
        c.close()
