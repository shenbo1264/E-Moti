import json
from threading import Event
from time import monotonic

import pytest

from guanghe_companion.expression_clients import LLMProviderError, OpenAICompatibleChatClient
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_request import ExpressionRequest


# 第六份独立集真实响应原文；这里只回放调用边界，模型效果由另存的真实复测验收。
RECORDED_DRAFTS = (
    '{"type":"speech","[joy]":"[joy] 字号18号，段落左对齐，每页不排双栏。","effect":"ATTENTION","motion_hint":"Raised","intent_hint":"stay_quiet"}',
    '{"type":"speech":"[calm] 小聆就是柏聆，练习时她读方向提示，画点的是你。","effect":"ATTENTION","motion_hint":"Raised","intent_hint":"gentle_reminder"}',
)
RECORDED_REVIEW = '{"edits":[],"speech":"[joy] 18号字，段落左对齐，每页不排双栏。"}'


@pytest.mark.parametrize("draft", RECORDED_DRAFTS)
@pytest.mark.parametrize("cancel_after_draft", [False, True])
def test_recorded_format_failure_reaches_only_existing_review(draft, cancel_after_draft):
    captured = []
    cancel = Event()

    def transport(request, timeout):
        captured.append((json.loads(request.data), timeout))
        if len(captured) > 1:
            raise LLMProviderError("contract stop before real review; no generated result")
        if cancel_after_draft:
            cancel.set()
        return json.dumps({"choices": [{"message": {"content": draft}}]}).encode()

    client = OpenAICompatibleChatClient(api_key="protocol", json_response=True, transport=transport)
    expressor = ShinsekaiAIExpressor(llm_client=client, timeout_seconds=10)
    request = ExpressionRequest.from_snapshot({"character_name": "星汐", "focus": 50, "charge": 50,
        "stability": 50, "mood": 50, "trust": 50}, context={"player_message": "刚才那项信息是什么？"})
    try:
        expressor.express(request, cancel_event=cancel)
        assert len(captured) == (1 if cancel_after_draft else 2)
        if cancel_after_draft:
            assert expressor.last_fallback_reason == "cancelled"
        else:
            assert expressor.last_fallback_reason == "provider_error"
            review = json.loads(captured[1][0]["messages"][-1]["content"])
            assert review["draft"] == draft
            assert review["evidence"]["player_message"] == request.player_message
            assert 0 < captured[1][1] <= captured[0][1] <= 10
    finally:
        expressor.close()


@pytest.mark.parametrize("cancel_after_review", [False, True])
def test_recovery_never_copies_unvalidated_fields_or_delivers_after_cancel(cancel_after_review):
    captured = []
    cancel = Event()
    untrusted = json.loads(RECORDED_DRAFTS[0])
    untrusted.update(coins=999, motion_hint="unsafe-motion", intent_hint="unsafe-intent")

    def transport(request, timeout):
        captured.append(json.loads(request.data))
        if len(captured) == 2 and cancel_after_review:
            cancel.set()
        content = json.dumps(untrusted) if len(captured) == 1 else RECORDED_REVIEW
        return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    client = OpenAICompatibleChatClient(api_key="protocol", json_response=True, transport=transport)
    expressor = ShinsekaiAIExpressor(llm_client=client, timeout_seconds=10)
    request = ExpressionRequest.from_snapshot({"character_name": "星汐", "focus": 50, "charge": 50,
        "stability": 50, "mood": 50, "trust": 50}, context={"player_message": "文字材料怎么排？"})
    try:
        events = expressor.express(request, cancel_event=cancel)
        assert len(captured) == 2
        assert expressor.last_interaction_intents == ()
        assert "coins" not in json.dumps(events)
        if cancel_after_review:
            assert expressor.last_fallback_reason == "cancelled"
            assert expressor.last_visual_actions == ()
        else:
            assert expressor.last_fallback_reason is None
            assert events[0]["speech"] == "18号字，段落左对齐，每页不排双栏。"
        captured.clear()
        with pytest.raises(TimeoutError):
            expressor._complete_chat(client, "JSON", request, None, monotonic() - 1)
        assert not captured
    finally:
        expressor.close()


@pytest.mark.parametrize("review", [RECORDED_DRAFTS[0], RECORDED_DRAFTS[1]])
def test_invalid_review_is_reported_without_third_call(review):
    captured = []

    def transport(request, timeout):
        captured.append(json.loads(request.data))
        content = RECORDED_DRAFTS[0] if len(captured) == 1 else review
        return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    client = OpenAICompatibleChatClient(api_key="protocol", json_response=True, transport=transport)
    with ShinsekaiAIExpressor(llm_client=client, timeout_seconds=10) as expressor:
        request = ExpressionRequest.from_snapshot({"character_name": "星汐", "focus": 50, "charge": 50,
            "stability": 50, "mood": 50, "trust": 50}, context={"player_message": "文字材料怎么排？"})
        expressor.express(request)
        assert len(captured) == 2
        assert expressor.last_fallback_reason == "invalid_refinement"
        assert expressor.last_visual_actions == ()
        assert expressor.last_interaction_intents == ()
