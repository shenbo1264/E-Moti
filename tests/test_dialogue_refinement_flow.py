import json
from pathlib import Path
from threading import Event

import pytest

from guanghe_companion.expression_clients import OpenAICompatibleChatClient
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.fixture
def recorded_answer():
    report = json.loads((Path(__file__).parents[1] / 'docs/modernization/evidence/voice-ui-followup-20261030/voice-final.json').read_text(encoding='utf-8'))
    return report['results'][0]['calls'][-1]['answer']


@pytest.mark.parametrize('cancel_after_draft', [False, True])
def test_chat_refines_once_with_remaining_budget_and_cancellation(tmp_path, recorded_answer, cancel_after_draft):
    captured = []
    cancel = Event()

    def transport(request, timeout):
        captured.append((json.loads(request.data), timeout))
        if cancel_after_draft:
            cancel.set()
        # 回放已保存的真实模型文本，只检查调用契约，不代表模型效果验收。
        content = recorded_answer if len(captured) == 1 else json.dumps({
            'edits': [], 'speech': json.loads(recorded_answer)['speech'],
        }, ensure_ascii=False)
        return json.dumps({'choices': [{'message': {'content': content}}]}).encode()

    client = OpenAICompatibleChatClient(api_key='protocol', json_response=True, transport=transport)
    expressor = ShinsekaiAIExpressor(llm_client=client, timeout_seconds=10)
    controller = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        controller._current_player_message = '今天什么都不想做。'
        request = ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=controller.get_expression_context())
        expressor.express(request, cancel_event=cancel)
        assert len(captured) == (1 if cancel_after_draft else 2)
        if cancel_after_draft:
            assert expressor.last_fallback_reason == 'cancelled'
        else:
            assert expressor.last_fallback_reason is None
            review = json.loads(captured[1][0]['messages'][-1]['content'])
            assert review['evidence']['player_message'] == '今天什么都不想做。'
            assert review['draft'] == json.loads(recorded_answer)
            assert 0 < captured[1][1] <= captured[0][1] <= 10
        captured.clear()
        cancel.clear()
        controller._current_player_message = ''
        action = ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=controller.get_expression_context())
        expressor.express(action)
        assert len(captured) == 1
    finally:
        expressor.close()
        controller.close()
