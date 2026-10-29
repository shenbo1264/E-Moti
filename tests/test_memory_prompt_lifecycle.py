"""The final provider prompt is the integration boundary of memory/privacy."""
import json
from dataclasses import replace

from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def make_controller(tmp_path):
    return PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)


def prompt(controller, query="饮品偏好"):
    controller._current_player_message = query
    try:
        context = controller.get_expression_context()
        request = ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=context)
        return controller.ai_expressor.build_prompt(request), request
    finally:
        controller._current_player_message = ""


def test_real_prompt_delivers_v2_memory_and_stable_persona(tmp_path):
    c = make_controller(tmp_path)
    try:
        c.story_runtime.memory.remember(kind="玩家希望被记住", title="饮品偏好",
            summary="我的饮品是紫苏冰饮", source="explicit_user_request", now=1)
        text, request = prompt(c)
        assert "紫苏冰饮" in text
        assert request.to_prompt_dict()["emotional_memory"]["shared_memories"]
        assert request.to_prompt_dict()["persona"]["character_id"] == c.state.character_id
        assert "config_hash" in text
    finally:
        c.close()


def test_forget_fences_old_dialogue_legacy_and_snapshot_routes_after_restart(tmp_path):
    c = make_controller(tmp_path)
    try:
        memory = c.story_runtime.memory.remember(kind="玩家希望被记住", title="饮品偏好",
            summary="我的饮品是紫苏冰饮", source="explicit_user_request", now=1)
        c.submit_dialogue_request(DialogueRequest("我的饮品是紫苏冰饮"))
        # Inject an old archive directly. The public compatibility API now
        # creates independent V2 evidence and is no longer a legacy side route.
        c.long_term_memory_service.upsert(key="preference:drink", category="preference",
                                         summary="紫苏冰饮", source="local_api", now=c.now)
        c.long_term_memory_store.save(c.long_term_memory_service.entries)
        c.state.memory_log.append({"at":1,"kind":"偏好","summary":"紫苏冰饮","motion":"Default"})
        c.set_perception_summary("桌面显示紫苏冰饮")
        c.set_tool_results([{"source":"old","title":"紫苏冰饮","summary":"紫苏冰饮"}])
        _, before_request = prompt(c)
        persona = before_request.to_prompt_dict()["persona"]
        c.memory_album_controller.forget(memory.memory_id, now=2)
        text, request = prompt(c)
        assert "紫苏冰饮" not in text
        assert request.to_prompt_dict()["persona"] == persona
        assert c.copy_dialogue_history_text()  # Archive is still user-readable.
    finally:
        c.close()
    restarted = make_controller(tmp_path)
    try:
        assert "紫苏冰饮" not in prompt(restarted)[0]
        restarted.submit_dialogue_request(DialogueRequest("现在我喜欢散步"))
        assert "散步" in prompt(restarted)[0]  # A fence is not permanent amnesia.
    finally:
        restarted.close()


def test_please_remember_is_a_visible_pending_candidate_not_an_unapproved_fact(tmp_path):
    c = make_controller(tmp_path)
    try:
        c.submit_dialogue_request(DialogueRequest("请记住：我的宠物叫青提"))
        pending = c.story_runtime.memory.pending_candidates
        assert len(pending) == 1
        assert not c.story_runtime.memory.recall("青提", now=10)
        c.memory_album_controller.confirm_pending(next(iter(pending)), now=10)
        assert "青提" in prompt(c, "宠物叫什么")[0]
    finally:
        c.close()


def test_switch_prompt_never_uses_previous_character_memory(tmp_path, monkeypatch):
    c = make_controller(tmp_path)
    captures = []
    from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
    from guanghe_companion import controller as controller_module
    def expressor_factory(**_kwargs):
        return ShinsekaiAIExpressor(enabled=True, llm_client=lambda text:
            captures.append(text) or '[{"type":"speech","speech":"[calm]你好。"}]')
    monkeypatch.setattr(controller_module, "build_default_ai_expressor", expressor_factory)
    try:
        old_id = c.state.character_id
        c.story_runtime.memory.update_bond_profile(now=1, new_preference="紫苏冰饮")
        c.switch_character("original_oc", include_ai_expression=True)
        assert captures and all("紫苏冰饮" not in text for text in captures)
        assert c.story_runtime.memory.character_id == "original_oc"
        _, request = prompt(c)
        assert request.persona["character_id"] == "original_oc" and old_id != "original_oc"
    finally:
        c.close()


def test_inflight_response_built_before_forget_is_not_presented(tmp_path):
    c = make_controller(tmp_path)
    try:
        memory = c.story_runtime.memory.remember(kind="玩家希望被记住", title="饮品",
            summary="紫苏冰饮", source="explicit_user_request", now=1)
        calls = []
        def provider(_text):
            calls.append(_text)
            c.story_runtime.memory.forget(memory.memory_id, now=2)
            return '[{"type":"speech","speech":"[joy]你最爱紫苏冰饮。"}]'
        c.ai_expressor.llm_client = provider
        c.ai_expressor.enabled = True
        snapshot = c.submit_dialogue_request(DialogueRequest("饮品"), include_ai_expression=True)
        assert len(calls) == 1 and "紫苏冰饮" in calls[0]
        assert "紫苏冰饮" not in json.dumps(snapshot["events"], ensure_ascii=False)
        assert "紫苏冰饮" not in c.copy_dialogue_history_text()
    finally:
        c.close()
