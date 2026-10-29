import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.fixture
def controller(tmp_path):
    instance = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    yield instance
    instance.close()


def test_host_dialogue_uses_current_persona_and_commits_once_on_owner_thread(controller):
    ticket = controller.prepare_host_dialogue(DialogueRequest("你好", source="mobile"))
    assert ticket.expression_request.persona["character_id"] == controller.state.character_id
    assert not controller.dialogue_history
    with ThreadPoolExecutor(max_workers=1) as worker:
        events = worker.submit(ticket.expressor.express, ticket.expression_request, "ATTENTION").result()
    result = controller.complete_host_dialogue(ticket, events)
    assert result["character_id"] == ticket.character_id
    assert len(controller.dialogue_history) == 2
    with pytest.raises(RuntimeError, match="stale"):
        controller.complete_host_dialogue(ticket, events)
    assert len(controller.dialogue_history) == 2


def test_host_pending_memory_requires_confirmation(controller):
    ticket = controller.prepare_host_dialogue(DialogueRequest("请记住：我的宠物叫青提", source="mobile"))
    assert ticket.expression_request is None
    controller.complete_host_dialogue(ticket)
    album = controller.memory_album_controller.snapshot()
    assert album["pending_confirmation_count"] == 1
    assert not controller.story_runtime.memory.recall("青提", now=int(controller.now))
    controller.memory_album_controller.confirm_pending(album["pending_candidates"][0]["pending_id"],
        now=int(controller.now), expected_epoch=album["context_epoch"])
    ticket = controller.prepare_host_dialogue(DialogueRequest("宠物叫什么"))
    assert "青提" in ticket.expressor.build_prompt(ticket.expression_request)
    controller.complete_host_dialogue(ticket, ticket.expressor.express(ticket.expression_request))


def test_cancel_discards_late_result_and_does_not_allow_parallel_expressor(controller):
    ticket = controller.prepare_host_dialogue(DialogueRequest("你好"))
    events = ticket.expressor.express(ticket.expression_request)
    controller.cancel_host_dialogue()
    assert ticket.cancelled.is_set()
    with pytest.raises(RuntimeError, match="busy"):
        controller.prepare_host_dialogue(DialogueRequest("另一个请求"))
    with pytest.raises(RuntimeError, match="stale"):
        controller.complete_host_dialogue(ticket, events)
    assert not controller.dialogue_history
    fresh = controller.prepare_host_dialogue(DialogueRequest("新的请求"), include_ai_expression=False)
    controller.complete_host_dialogue(fresh)
    assert len(controller.dialogue_history) == 2


def test_desktop_submit_cannot_interleave_host_or_add_pending_candidate(controller):
    ticket = controller.prepare_host_dialogue(DialogueRequest("你好"))
    with pytest.raises(RuntimeError, match="busy"):
        controller.submit_dialogue_request(DialogueRequest("请记住：不应进入待确认"))
    assert not controller.story_runtime.memory.pending_candidates
    controller.complete_host_dialogue(ticket, ticket.expressor.express(ticket.expression_request))


def test_host_thread_boundary_rejects_network_controller_access(controller):
    with ThreadPoolExecutor(max_workers=1) as worker:
        with pytest.raises(RuntimeError, match="thread"):
            worker.submit(controller.prepare_host_dialogue, DialogueRequest("你好")).result()
    ticket = controller.prepare_host_dialogue(DialogueRequest("你好"))
    with ThreadPoolExecutor(max_workers=1) as worker:
        with pytest.raises(RuntimeError, match="thread"):
            worker.submit(controller.complete_host_dialogue, ticket).result()
        with pytest.raises(RuntimeError, match="thread"):
            worker.submit(controller.cancel_host_dialogue).result()
    controller.complete_host_dialogue(ticket, ticket.expressor.express(ticket.expression_request))


def test_forget_rejects_old_result_and_new_prompt_uses_existing_memory_lifecycle(controller):
    album = controller.memory_album_controller
    album.remember_explicit("我的饮品是紫苏冰饮", now=int(controller.now))
    memory = controller.story_runtime.memory.store.load_memories()[0]
    ticket = controller.prepare_host_dialogue(DialogueRequest("饮品偏好"))
    persona = ticket.expression_request.persona
    assert "紫苏冰饮" in ticket.expressor.build_prompt(ticket.expression_request)
    events = ticket.expressor.express(ticket.expression_request)
    album.forget(memory.memory_id, now=int(controller.now))
    assert ticket.cancelled.is_set()
    with pytest.raises(RuntimeError, match="stale"):
        controller.complete_host_dialogue(ticket, events)
    next_ticket = controller.prepare_host_dialogue(DialogueRequest("饮品偏好"))
    assert "紫苏冰饮" not in next_ticket.expressor.build_prompt(next_ticket.expression_request)
    assert next_ticket.expression_request.persona == persona
    controller.complete_host_dialogue(next_ticket, next_ticket.expressor.express(next_ticket.expression_request))
    assert "紫苏冰饮" not in json.dumps(controller.get_snapshot()["events"], ensure_ascii=False)


def test_switch_away_and_back_cannot_resurrect_old_ticket(controller):
    original = controller.state.character_id
    ticket = controller.prepare_host_dialogue(DialogueRequest("你好"))
    events = ticket.expressor.express(ticket.expression_request)
    controller.switch_character("original_oc")
    assert ticket.cancelled.is_set()
    controller.switch_character(original)
    with pytest.raises(RuntimeError, match="stale"):
        controller.complete_host_dialogue(ticket, events)
    assert not controller.dialogue_history


@pytest.mark.parametrize("operation", ["reset_demo_state", "clear_dialogue_history", "revert_dialogue_history"])
def test_history_edit_invalidates_prepared_dialogue(controller, operation):
    ticket = controller.prepare_host_dialogue(DialogueRequest("你好"))
    events = ticket.expressor.express(ticket.expression_request)
    getattr(controller, operation)()
    assert ticket.cancelled.is_set()
    with pytest.raises(RuntimeError, match="stale"):
        controller.complete_host_dialogue(ticket, events)


def test_diagnostic_cannot_reuse_inflight_expressor(controller):
    ticket = controller.prepare_host_dialogue(DialogueRequest("你好"))
    with pytest.raises(RuntimeError, match="busy"):
        controller.test_expression_provider()
    controller.complete_host_dialogue(ticket, ticket.expressor.express(ticket.expression_request))


def test_memory_expiry_during_worker_wait_rejects_response(controller):
    controller.story_runtime.memory.remember(kind="玩家希望被记住", title="今日饮品",
        summary="今天喝紫苏冰饮", source="explicit_user_request", now=0, valid_until=5)
    ticket = controller.prepare_host_dialogue(DialogueRequest("今日饮品"))
    events = ticket.expressor.express(ticket.expression_request)
    controller.now = 6
    with pytest.raises(RuntimeError, match="stale"):
        controller.complete_host_dialogue(ticket, events)
    assert ticket.cancelled.is_set()


def test_normal_completion_preserves_host_generation(controller):
    generation = controller.host_context_generation
    ticket = controller.prepare_host_dialogue(DialogueRequest("你好"), include_ai_expression=False)
    controller.complete_host_dialogue(ticket)
    assert controller.host_context_generation == generation
