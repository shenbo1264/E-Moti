"""Language families; no fixture names, IDs, app names or field keys in rules."""
from datetime import datetime, timezone

import pytest

from guanghe_companion.retrieval_router import MemoryRetrievalRouter


@pytest.mark.parametrize("query,subject", [
    ("我的泳池储物牌编号是什么？", "user:self"),
    ("我姨妈的泳池储物牌编号是什么？", "relation:姨妈"),
    ("我的搭档的仪器放在哪里？", "relation:搭档"),
    ("阿禾的仪器放在哪里？", "阿禾"),
    ("我同学租的仓库叫什么名字？", "relation:同学"),
    ("我那只杯子是什么材质？", "user:self"),
])
def test_personal_attribute_keeps_literal_owner(query, subject):
    plan = MemoryRetrievalRouter().plan(query)
    assert plan.intents[0].route == "fact"
    assert subject in plan.intents[0].subjects
    assert plan.intents[0].predicates


@pytest.mark.parametrize("query,subject", [
    ("我学陶艺的教练叫什么？", "relation:陶艺教练"),
    ("我学书法的老师住在哪里？", "relation:书法老师"),
    ("我的同事的助理叫什么？", "relation:同事的助理"),
    ("我的朋友的室友叫什么？", "relation:朋友的室友"),
    ("我同学租的仓库叫什么名字？", "relation:同学"),
    ("我的朋友买的设备叫什么名字？", "relation:朋友"),
])
def test_specific_relationship_survives_coarse_possessive_hint(query, subject):
    # An existing correction/restart contract exposed the precedence defect.
    # Preserve full person relations without turning an owned object into a
    # person; none of these labels are added to the production rule vocabulary.
    intent = MemoryRetrievalRouter().plan(query).intents[0]
    assert intent.route == "fact"
    assert intent.subjects == (subject,)


@pytest.mark.parametrize("query", [
    "上次用绘谱4.7时，按什么顺序把文件拼好的？",
    "在绘谱5.0还能沿用之前的步骤吗？",
    "当前设备还连着另一台电脑，上次那套连接方法能直接用吗？",
    "以前操作成功时的条件和步骤是什么？",
])
def test_past_procedure_uses_task_evidence_without_app_word_list(query):
    plan = MemoryRetrievalRouter().plan(query)
    assert "task" in plan.routes
    assert all(i.scopes == ("task_experience",) for i in plan.intents if i.route == "task")


@pytest.mark.parametrize("query", [
    "绘谱今天更新后能连接设备了吗？",
    "邻里工坊今天几点关门？",
    "云端服务目前恢复了吗？",
])
def test_current_external_state_needs_authority(query):
    assert "live" in MemoryRetrievalRouter().plan(query).routes


def test_current_personal_appointment_is_not_external_live_state():
    assert MemoryRetrievalRouter().plan("我今天和理发师的预约是几点？").routes == ("fact",)


def test_omitted_subject_continuation_cannot_overwrite_external_state():
    plan = MemoryRetrievalRouter().plan("我的包是什么颜色？工作室今天关门了吗？")
    assert plan.routes == ("fact", "live")
    assert plan.intents[1].authority == "executor"


@pytest.mark.parametrize("query", [
    "不要翻旧记忆，写三句打气的话。",
    "给我写两段风景描写，不需要回顾我们的经历。",
    "给我一句参加活动的鼓励，不用提过去。",
])
def test_explicit_no_recall_is_respected(query):
    plan = MemoryRetrievalRouter().plan(query)
    assert plan.routes == ("chat",)
    assert not plan.needs_semantic


@pytest.mark.parametrize("query", ["树叶为什么秋天变黄？", "解释一下电子为什么带负电。", "π是什么？"])
def test_general_knowledge_still_skips_archive(query):
    assert MemoryRetrievalRouter().plan(query).routes == ("chat",)


def test_named_subject_reference_does_not_turn_into_self():
    history = [{"role": "user", "content": "阿禾的仪器放在哪里？"}]
    plan = MemoryRetrievalRouter().plan("她用的仪器是什么型号？", history=history)
    assert plan.routes == ("fact",)
    assert plan.intents[0].subjects == ("阿禾",)


def test_reference_switch_to_my_own_keeps_field_but_changes_owner():
    history = [{"role": "user", "text": "我姨妈的泳池储物牌编号是多少？"}]
    plan = MemoryRetrievalRouter().plan("那我的呢？", history=history)
    assert plan.intents[0].subjects == ("user:self",)
    assert plan.routes == ("fact",)


def test_explicit_caller_scope_remains_narrow():
    plan = MemoryRetrievalRouter().plan("我的收藏主题是什么？", scope="private_archive")
    assert all(i.scopes == ("private_archive",) for i in plan.intents)


def utc(year, month, day=1):
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())


@pytest.mark.parametrize("query,start,end", [
    ("6月5日那会儿，我用哪款设备？", utc(2026, 6, 5), utc(2026, 6, 6)),
    ("今年4月，我用的版本是多少？", utc(2026, 4), utc(2026, 5)),
    ("去年12月的配置是什么？", utc(2025, 12), utc(2026, 1)),
    ("2023年10月的配置是什么？", utc(2023, 10), utc(2023, 11)),
])
def test_calendar_window_uses_caller_clock(query, start, end):
    plan = MemoryRetrievalRouter().plan(query, now=utc(2026, 8, 15))
    intent = next(i for i in plan.intents if i.route != "chat")
    assert intent.temporal_mode == "as_of"
    assert (intent.as_of, intent.as_of_end) == (start, end)


def test_missing_year_without_clock_is_unresolved_not_current():
    plan = MemoryRetrievalRouter().plan("6月5日那会儿，我用哪款设备？")
    assert not plan.unresolved_reference
    assert all(i.temporal_mode == "unresolved" for i in plan.intents if i.route != "chat")


@pytest.mark.parametrize("query,route", [
    ("回顾一下我们做纸灯的那段经历。", "episode"),
    ("我们一起修好的收音机测试了多久？", "episode"),
    ("上次辰光服务的连接故障最后怎么解决的？", "task"),
    ("上月文件备份的验证结果怎么样？", "task"),
])
def test_narrative_and_task_objects_are_not_people(query, route):
    plan = MemoryRetrievalRouter().plan(query, now=utc(2026, 8, 15))
    assert plan.routes == (route,)
    assert not plan.intents[0].subjects


def test_date_prefix_does_not_turn_selected_object_into_relation():
    plan = MemoryRetrievalRouter().plan("7月3日那会儿，我的纸灯选的是什么材料？", now=utc(2026, 8, 15))
    assert plan.routes == ("fact",)
    assert plan.intents[0].subjects == ("user:self",)
    assert plan.intents[0].as_of == utc(2026, 7, 3)


def test_user_named_antecedent_is_only_an_unverified_literal():
    history = [{"role": "user", "content": "我同事阿槐做了一个纸模。"},
               {"role": "assistant", "content": "你的朋友阿岚喜欢红色。"}]
    plan = MemoryRetrievalRouter().plan("他选的纸是什么颜色？", history=history)
    assert plan.routes == ("fact",)
    assert plan.intents[0].subjects == ("阿槐",)
    assert plan.inherited_context


def test_assistant_only_named_antecedent_cannot_resolve_reference():
    history = [{"role": "assistant", "content": "我同事阿槐做了一个纸模。"}]
    plan = MemoryRetrievalRouter().plan("他选的纸是什么颜色？", history=history)
    assert plan.unresolved_reference
    assert not plan.intents[0].subjects


@pytest.mark.parametrize("query", ["7月3日我的配置是什么？", "2026年7月3日我的配置是什么？", "上月的设备配置是什么？"])
def test_logical_clock_never_becomes_a_calendar_timestamp(query):
    plan = MemoryRetrievalRouter(time_basis="logical").plan(query, now=300)
    assert not plan.unresolved_reference
    assert all(i.temporal_mode == "unresolved" and i.as_of is None and i.as_of_end is None
               for i in plan.intents if i.route != "chat")


def test_clock_basis_is_an_explicit_contract():
    with pytest.raises(ValueError, match="time_basis"):
        MemoryRetrievalRouter(time_basis="infer")
    plan = MemoryRetrievalRouter(time_basis="unix").plan("7月3日我的配置是什么？", now=utc(2026, 8, 15))
    assert plan.intents[0].as_of == utc(2026, 7, 3)
