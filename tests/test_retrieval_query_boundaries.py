from datetime import datetime, timezone

import pytest

from guanghe_companion.retrieval_router import MemoryRetrievalRouter


NOW = int(datetime(2026, 11, 6, tzinfo=timezone.utc).timestamp())


@pytest.mark.parametrize("query", [
    "十二月三日换签安排生效以后，档案要挂什么系列名？",
    "二〇二六年十二月七日生效的规则里，借阅上限是多少？",
    "十二月八日以后展板要用什么标题？",
    "12月8日以后展板要用什么标题？",
])
def test_parsed_calendar_demand_is_not_lost_to_chat_classification(query):
    plan = MemoryRetrievalRouter().plan(query, now=NOW)
    assert plan.intents[0].route not in {"chat", "live"}
    assert plan.intents[0].temporal_mode == "as_of"
    assert plan.intents[0].as_of > NOW


def test_logical_archive_keeps_calendar_demand_unresolved_instead_of_chat():
    plan = MemoryRetrievalRouter(time_basis="logical").plan(
        "十二月八日以后展板要用什么标题？", now=20)
    assert plan.intents[0].route != "chat"
    assert plan.intents[0].temporal_mode == "unresolved"
    assert plan.intents[0].as_of is None


def test_dated_plan_keeps_its_evidence_demand_and_date():
    intent = MemoryRetrievalRouter().plan("十二月八日预约的项目是什么？", now=NOW).intents[0]
    assert intent.route != "chat"
    assert intent.temporal_mode == "planned"
    assert intent.as_of > NOW


@pytest.mark.parametrize("query", [
    "透视布景试摆已经在我的完成清单里了吗？",
    "我的木雕练习已经完成了吗？",
    "我读书计划目前进展怎么样？",
])
def test_personal_progress_does_not_invent_an_executor_authority(query):
    plan = MemoryRetrievalRouter().plan(query, now=NOW)
    assert plan.intents[0].route in {"fact", "episode", "bounded"}
    assert not plan.intents[0].authority


@pytest.mark.parametrize("query", [
    "Relay 的任务完成了吗？",
    "备份任务现在进度怎么样？",
    "同步服务恢复了吗？",
    "陶艺店现在营业吗？",
    "手机当前状态怎么样？",
])
def test_explicit_external_state_still_requires_live_authority(query):
    intent = MemoryRetrievalRouter().plan(query, now=NOW).intents[0]
    assert intent.route == "live"
    assert intent.authority


@pytest.mark.parametrize("query", [
    "十二月八日帮我编一个故事好吗？",
    "什么是日历？",
    "不用翻旧记忆，陪我聊聊。",
])
def test_creative_and_no_recall_requests_stay_chat(query):
    assert MemoryRetrievalRouter().plan(query, now=NOW).routes == ("chat",)
