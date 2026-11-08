"""Unseen predicates need source verification, not a growing field whitelist."""
from dataclasses import replace

import pytest

from guanghe_companion.emotional_memory import EmotionalMemoryEntry
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.retrieval_contract import RetrievalIntent
from guanghe_companion.retrieval_evidence import check_evidence


def row(title, summary, predicate, value, *, subject="user:self", **kwargs):
    return EmotionalMemoryEntry(memory_id=predicate + subject, character_id="pet", owner_id="local_user",
        kind="用户事实", title=title, summary=summary, source="user_chat", source_ids=("turn:1",),
        occurred_at=10, created_at=10, updated_at=10, valid_from=10,
        metadata={"fact_subject": subject, "fact_predicate": predicate,
                  "fact_slot": subject + ":" + predicate, "fact_value": value}, **kwargs)


def decision(entry, query, *, subjects=("user:self",), route="fact", **kwargs):
    intent = RetrievalIntent(route, query, subjects=subjects, predicates=("unresolved_field",), **kwargs)
    return check_evidence(entry, intent, now=200, owner_id="local_user", character_id="pet")


@pytest.mark.parametrize("title,summary,predicate,value,query", [
    ("我的会员卡号", "用户的青杉俱乐部会员卡号是 QS-802。", "membership_card_number", "QS-802", "我的青杉俱乐部会员卡号是多少？"),
    ("会员卡有效期", "用户的会员卡有效至2026-12-30。", "membership_expiration", "2026-12-30", "我的会员卡哪天到期？"),
    ("常用笔记本的纸张克重", "用户常用笔记本的纸张克重是90克。", "paper_basis_weight", "90克", "我常用笔记本的纸张克重是多少？"),
    ("入会日期", "用户加入青杉俱乐部的日期是2025-04-20。", "joining_date", "2025-04-20", "我加入青杉俱乐部的日期是什么？"),
    ("小包颜色", "用户的小包颜色是浅青。", "bag_color", "浅青", "我的小包是什么颜色？"),
    ("排班日", "用户每周三在画室值班。", "studio_shift_weekday", "周三", "我每周哪天在画室值班？"),
    ("画室值班地点", "用户在白桦楼三层302室值班。", "studio_shift_room", "白桦楼三层302室", "我在什么房间值班？"),
    ("备份文件夹", "用户的照片备份文件夹是 /photos/2026。", "photo_backup_directory", "/photos/2026", "我的照片备份放在哪个目录？"),
    ("我的未读消息数", "用户的未读消息数是0。", "unread_count", 0, "我的未读消息数是多少？"),
    ("同步是否开启", "用户的自动同步设置为false。", "automatic_sync_enabled", False, "我的自动同步设置是什么？"),
])
def test_literal_source_can_support_open_predicate(title, summary, predicate, value, query):
    outcome = decision(row(title, summary, predicate, value), query)
    assert outcome.accepted, outcome


@pytest.mark.parametrize("title,summary,predicate,value,query", [
    ("会员卡号", "用户的青杉俱乐部会员卡号是 QS-802。", "membership_card_number", "QS-802", "我登录青杉俱乐部网站的密码是什么？"),
    ("会员卡有效期", "用户的青杉俱乐部会员卡有效至2026-12-30。", "membership_expiration", "2026-12-30", "我的青杉俱乐部会员卡号是多少？"),
    ("衣服颜色", "用户的衣服颜色是浅青。", "shirt_color", "浅青", "我的小包是什么颜色？"),
    ("小包颜色", "用户的小包颜色是浅青。", "bag_color", "浅青", "我的小包是什么牌子？"),
    ("画室地点", "用户在白桦楼三层302室值班。", "studio_shift_room", "白桦楼三层302室", "我每周哪天在画室值班？"),
    ("纸张克重", "用户常用笔记本的纸张克重是90克。", "paper_basis_weight", "200克", "我常用笔记本的纸张克重是多少？"),
])
def test_lexical_overlap_does_not_prove_wrong_attribute(title, summary, predicate, value, query):
    assert not decision(row(title, summary, predicate, value), query).accepted


@pytest.mark.parametrize("route", ["fact", "bounded", "episode"])
def test_subject_constraint_applies_before_every_retrieval_route(route):
    other = row("姐姐的画室地点", "姐姐在白桦楼三层302室值班。", "studio_shift_room", "白桦楼三层302室", subject="relation:姐姐")
    assert not decision(other, "我在什么房间值班？", route=route).accepted


def test_day_interval_includes_evidence_recorded_during_that_day():
    entry = row("色号", "用户的小包色号是A3。", "bag_color_code", "A3")
    entry = replace(entry, valid_from=100, valid_until=150)
    outcome = decision(entry, "我的小包色号是什么？", temporal_mode="as_of", as_of=90, as_of_end=120)
    assert outcome.accepted
    assert not decision(entry, "我的小包色号是什么？", temporal_mode="as_of", as_of=150, as_of_end=170).accepted


@pytest.mark.parametrize("value,body", [(7, "17"), (0, "10"), (False, "falsehood")])
def test_typed_literal_requires_whole_scalar_token(value, body):
    entry = row("同步设置", "用户的同步设置是" + body + "。", "sync_setting", value)
    assert not decision(entry, "我的同步设置是什么？").accepted


def test_open_field_uses_bounded_lexical_candidates_not_latest_user_rows(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="pet")
    target = memory.remember(kind="用户事实", title="常用笔记本的纸张克重",
        summary="用户常用笔记本的纸张克重是90克。", source="user_chat", now=1, source_ids=("turn:target",),
        metadata={"fact_subject": "user:self", "fact_predicate": "paper_basis_weight", "fact_value": "90克"})
    with memory.store._document() as document:
        for n in range(150):
            noise = row("其他记录", f"用户的另一件物品编号是N{n}。", f"other_{n}", f"N{n}")
            document["entries"].append(replace(noise, occurred_at=10+n, valid_from=10+n).to_dict())
    result = memory.retrieve("我常用笔记本的纸张克重是多少？", now=300)
    assert result.trace.selected_memory_ids == (target.memory_id,)
    assert result.trace.rows_loaded <= 130
