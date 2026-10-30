import pytest

from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.fixture
def controller(tmp_path):
    instance = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    yield instance
    instance.close()


def say(controller, text):
    return controller.submit_dialogue_request(DialogueRequest(text))


def active(controller):
    return [m for m in controller.story_runtime.memory.store.load_memories() if not m.deleted]


def final_prompt(controller, query):
    controller._current_player_message = query
    try:
        context = controller.get_expression_context()
        request = ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=context)
        return controller.ai_expressor.build_prompt(request)
    finally:
        controller._current_player_message = ""


@pytest.mark.parametrize("text", [
    "我喜欢咖啡才怪", "我喜欢咖啡这句话是朋友的原话", "我喜欢咖啡仅仅是举例",
    "我喜欢咖啡是假话", "我不喜欢的不是咖啡", "我喜欢咖啡的话就会买",
])
def test_unasserted_or_retracted_statement_is_not_committed(controller, text):
    say(controller, text)
    assert not active(controller)
    assert not controller.story_runtime.memory.valid_profile(now=int(controller.now)).stable_preferences


@pytest.mark.parametrize("question", [
    "忘记饮料偏好是什么意思？", "忘记饮料偏好这句话是假设", "忘记饮料偏好是朋友说的，不是我的要求",
])
def test_discussing_a_forget_command_does_not_execute_it(controller, question):
    say(controller, "我喜欢紫苏冰饮茶")
    original = active(controller)[0]
    say(controller, question)
    assert [row.memory_id for row in active(controller)] == [original.memory_id]


def test_pending_only_forget_also_removes_old_chat_from_provider_prompt(controller):
    controller.set_chat_memory_mode("review")
    say(controller, "我喜欢紫苏冰饮茶")
    assert controller.story_runtime.memory.pending_candidates
    assert not active(controller)
    say(controller, "别再记我的饮料偏好了")
    assert not controller.story_runtime.memory.pending_candidates
    assert "紫苏冰饮茶" not in final_prompt(controller, "我的饮品偏好是什么")


def test_same_value_in_another_fact_domain_is_not_a_preference_reversal(controller):
    say(controller, "我住在上海")
    say(controller, "我喜欢上海")
    assert {m.summary for m in active(controller)} == {"用户住在上海", "用户喜欢上海"}


def test_named_fact_can_be_forgotten_without_domain_jargon(controller):
    say(controller, "我喜欢紫苏冰饮茶")
    say(controller, "忘记我喜欢紫苏冰饮茶这件事")
    assert not active(controller)
    assert not controller.story_runtime.memory.valid_profile(now=int(controller.now)).stable_preferences


def test_conflict_confirmation_fences_old_profile_and_history(controller):
    say(controller, "我喜欢紫苏冰饮茶")
    say(controller, "我喜欢桂花乌龙茶")
    pending = controller.story_runtime.memory.pending_candidates
    assert len(pending) == 1
    controller.memory_album_controller.confirm_pending(next(iter(pending)), now=int(controller.now))
    assert {m.summary for m in active(controller)} == {"用户喜欢桂花乌龙茶"}
    prompt = final_prompt(controller, "饮品偏好")
    assert "紫苏冰饮茶" not in prompt
    assert "桂花乌龙茶" in prompt


def test_repeated_negation_does_not_duplicate_or_preserve_positive_fact(controller):
    say(controller, "我喜欢紫苏冰饮茶")
    say(controller, "我不喜欢紫苏冰饮茶，我不喜欢紫苏冰饮茶")
    assert [m.summary for m in active(controller)] == ["用户不喜欢紫苏冰饮茶"]
    assert controller.story_runtime.memory.valid_profile(now=int(controller.now)).stable_preferences == (
        "用户不喜欢紫苏冰饮茶",)


def test_off_mode_disables_new_inference_but_keeps_forget_available(controller):
    say(controller, "我喜欢紫苏冰饮茶")
    controller.set_chat_memory_mode("off")
    say(controller, "我住在上海")
    assert not any("上海" in row.summary for row in active(controller))
    say(controller, "别再记我的饮料偏好了")
    assert not active(controller)
