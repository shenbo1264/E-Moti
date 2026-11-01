import pytest

from guanghe_companion.chat_memory_extraction import ChatMemoryExtraction, MemoryProposal
from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def say(controller, text):
    controller.submit_dialogue_request(DialogueRequest(text))
    return controller.last_chat_memory_result


def active(controller):
    return [m for m in controller.story_runtime.memory.store.load_memories() if not m.deleted]


@pytest.mark.parametrize("relation,field,old,new", [
    ("室友", "叫", "宋禾", "陆岑"),
    ("搭档", "住在", "青岛", "厦门"),
    ("表姐", "的职业是", "设计师", "建筑师"),
])
@pytest.mark.parametrize("mode", ["auto", "review"])
def test_relation_field_correction_keeps_subject_and_other_fields(tmp_path, relation, field, old, new, mode):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        assert say(c, f"我的{relation}{field}{old}。").status == "saved"
        assert say(c, "我的名字是小满。").status == "saved"
        assert say(c, "我的邻居住在宁波。").status == "saved"
        c.set_chat_memory_mode(mode)
        result = say(c, f"我写错了，我的{relation}{field}{new}。")
        assert result.status == ("pending" if mode == "review" else "saved")
        if mode == "review":
            c.memory_album_controller.confirm_pending(next(iter(c.story_runtime.memory.pending_candidates)), now=0)
        c.clear_dialogue_history()
    finally:
        c.close()
    c = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        rows = active(c)
        changed = next(m for m in rows if new in m.summary)
        assert changed.metadata["fact_subject"] == f"relation:{relation}"
        assert relation in changed.summary and not any(old in m.summary for m in rows)
        assert any("小满" in m.summary for m in rows) and any("邻居" in m.summary for m in rows)
        assert say(c, f"请忘记我的{relation}。").status == "forgotten"
        assert all(new not in m.summary for m in active(c))
        assert any("小满" in m.summary for m in active(c))
    finally:
        c.close()


@pytest.mark.parametrize("activity", ["练琴", "参加合唱团", "整理书架"])
def test_weekly_activity_does_not_require_go_verb(tmp_path, activity):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        assert say(c, f"我每星期二{activity}。").status == "saved"
        assert say(c, f"我以后改成星期四{activity}了。").status == "saved"
        rows = active(c)
        assert len(rows) == 1 and "周四" in rows[0].summary and activity in rows[0].summary
        assert say(c, f"请忘记我的{activity}安排。").status == "forgotten"
    finally:
        c.close()


@pytest.mark.parametrize("text", [
    "朋友说我的室友叫宋禾。", "如果我的室友叫宋禾。", "我的室友说我叫宋禾。",
    "我的室友不是叫宋禾。", "我的室友今天住在青岛。", "小说里我的室友叫宋禾。",
])
def test_relation_report_hypothesis_negation_and_temporary_are_not_fact(tmp_path, text):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        say(c, text)
        assert not active(c)
    finally:
        c.close()


def test_semantic_correction_cannot_cross_subject_or_predicate(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        say(c, "我的室友叫宋禾。")
        say(c, "我的室友住在青岛。")
        rows = active(c)
        assert len(rows) == 2
        target = next(m for m in rows if "宋禾" in m.summary)
        for text, value, predicate, domain in [
            ("我说错了，我的邻居叫陆岑", "陆岑", "relation_name", "人物姓名"),
            ("我说错了，我的室友住在厦门", "厦门", "relation_residence", "人物居住地"),
        ]:
            extraction = ChatMemoryExtraction(c.story_runtime.memory)
            envelope = extraction.prepare(text, now=0, mode="auto", generation=0)
            proposal = MemoryProposal("correct", text, value, predicate, domain, (target.memory_id,), "explicit", "personal")
            assert extraction.apply(envelope, (proposal,), now=0, mode="auto", generation=0).status == "clarify"
        assert any("宋禾" in m.summary for m in active(c))
        assert any("青岛" in m.summary for m in active(c))
    finally:
        c.close()


@pytest.mark.parametrize("mode", ["auto", "review", "off"])
def test_relation_field_forgetting_preserves_other_fields_and_people(tmp_path, mode):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        for text in ("我的室友叫宋禾", "我的室友住在青岛", "我的邻居住在青岛", "我住在青岛"):
            assert say(c, text).status == "saved"
        c.set_chat_memory_mode(mode)
        assert say(c, "请忘记我的室友的住址").status == "forgotten"
        summaries = {m.summary for m in active(c)}
        assert summaries == {"用户的室友叫宋禾", "用户的邻居住在青岛", "用户住在青岛"}
    finally:
        c.close()


def test_legacy_relation_slot_is_corrected_without_history_migration(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        memory = c.story_runtime.memory
        old = memory.remember(kind="用户自述", title="教师姓名", summary="用户的摄影老师叫宋禾",
            source="user_correction", now=0, user_confirmed=True, source_ids=("old-turn",),
            metadata={"fact_slot": "teacher_name:摄影老师", "fact_domain": "教师姓名", "fact_value": "宋禾"})
        assert say(c, "我写错了，我的摄影老师叫陆岑").status == "saved"
        rows = active(c)
        assert len(rows) == 1 and rows[0].metadata["fact_slot"] == "relation:摄影老师:name"
        assert rows[0].memory_id != old.memory_id
        assert say(c, "忘记我的摄影老师的名字").status == "forgotten"
        assert not active(c)
    finally:
        c.close()


@pytest.mark.parametrize("predicate,domain,text,value", [
    ("name", "称呼", "我的搭档叫宋禾", "宋禾"),
    ("residence", "居住地", "我的搭档住在青岛", "青岛"),
    ("occupation", "职业", "我的搭档的职业是设计师", "设计师"),
])
def test_semantic_relation_is_bound_even_when_model_labels_it_as_self(tmp_path, predicate, domain, text, value):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        extraction = ChatMemoryExtraction(c.story_runtime.memory)
        envelope = extraction.prepare(text, now=0, mode="auto", generation=0)
        proposal = MemoryProposal("remember", text, value, predicate, domain, (), "explicit", "other")
        assert extraction.apply(envelope, (proposal,), now=0, mode="auto", generation=0).status == "saved"
        row = active(c)[0]
        assert row.metadata["fact_subject"] == "relation:搭档" and row.summary.startswith("用户的搭档")
    finally:
        c.close()


@pytest.mark.parametrize("prefix", ["我刚才说错了，", "我之前把名字写错了，", "刚才我写错名字了，"])
def test_natural_correction_prefix_binds_same_relation(tmp_path, prefix):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        say(c, "我的室友叫宋禾")
        assert say(c, prefix + "我的室友叫陆岑").status == "saved"
        assert [m.summary for m in active(c)] == ["用户的室友叫陆岑"]
    finally:
        c.close()


def test_unknown_relation_forget_cannot_remove_user_field(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        say(c, "我的名字是小满")
        assert say(c, "忘记我的室友的姓名").status == "clarify"
        assert [m.summary for m in active(c)] == ["用户的名字是小满"]
    finally:
        c.close()


def test_relation_attribute_is_not_rejected_as_fiction_by_a_word_inside_value(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        assert say(c, "我的邻居的职业是小说家").status == "saved"
        assert [m.summary for m in active(c)] == ["用户的邻居的职业是小说家"]
    finally:
        c.close()


@pytest.mark.parametrize("text", ["我的室友叫宋禾才怪", "我的室友叫宋禾只是举例", "我的室友叫宋禾这句话是假话"])
def test_grounded_relation_cannot_bypass_retraction_guard(tmp_path, text):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        say(c, text)
        assert not active(c)
    finally:
        c.close()


def test_semantic_forget_unknown_relation_cannot_target_self_field(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        say(c, "我住在青岛")
        target = active(c)[0]
        extraction = ChatMemoryExtraction(c.story_runtime.memory)
        text = "请忘记我的邻居的居住地"
        envelope = extraction.prepare(text, now=0, mode="off", generation=0)
        p = MemoryProposal("forget", text, "", "residence", "居住地", (target.memory_id,), "explicit", "personal")
        assert extraction.apply(envelope, (p,), now=0, mode="off", generation=0).status == "clarify"
        assert len(active(c)) == 1
    finally:
        c.close()


def test_semantic_correction_requires_unique_existing_relation_slot(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        memory = c.story_runtime.memory
        rows = [memory.remember(kind="用户自述", title="人物姓名", summary="用户的搭档叫" + name,
            source="explicit_user_request", now=0, user_confirmed=True, source_ids=(name,))
            for name in ("宋禾", "陆岑")]
        extraction = ChatMemoryExtraction(memory)
        text = "我写错了，我的搭档叫叶舟"
        envelope = extraction.prepare(text, now=0, mode="auto", generation=0)
        p = MemoryProposal("correct", text, "叶舟", "relation_name", "人物姓名", (rows[0].memory_id,), "explicit", "personal")
        assert extraction.apply(envelope, (p,), now=0, mode="auto", generation=0).status == "clarify"
        assert len(active(c)) == 2
    finally:
        c.close()


@pytest.mark.parametrize("text,quote", [
    ("我的室友说我叫宋禾", "我叫宋禾"),
    ("我邻居告诉我，我叫宋禾", "我叫宋禾"),
    ("我的搭档认为我叫宋禾", "我叫宋禾"),
])
def test_semantic_excerpt_cannot_remove_reported_speech_context(tmp_path, text, quote):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        extraction = ChatMemoryExtraction(c.story_runtime.memory)
        envelope = extraction.prepare(text, now=0, mode="auto", generation=0)
        p = MemoryProposal("remember", quote, "宋禾", "legal_name", "姓名", (), "explicit", "personal")
        assert extraction.apply(envelope, (p,), now=0, mode="auto", generation=0).status in {"ignored", "clarify"}
        assert not active(c)
    finally:
        c.close()


@pytest.mark.parametrize("mode", ["auto", "review"])
def test_semantic_copula_occupation_correction_survives_restart(tmp_path, mode):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        memory = c.story_runtime.memory
        old = memory.confirm_candidate(memory.propose_explicit_user_memory("请记住：我的堂姐是木工。", now=0), now=0)
        text = "我之前说错了，我的堂姐是摄影师"
        extraction = ChatMemoryExtraction(memory)
        envelope = extraction.prepare(text, now=0, mode=mode, generation=0)
        p = MemoryProposal("correct", "我的堂姐是摄影师", "摄影师", "relation_occupation", "人物职业",
                           (old.memory_id,), "explicit", "personal")
        assert extraction.apply(envelope, (p,), now=0, mode=mode, generation=0).status == ("pending" if mode == "review" else "saved")
        if mode == "review":
            memory.confirm_candidate(next(iter(memory.pending_candidates)), now=0)
        c.clear_dialogue_history()
    finally:
        c.close()
    c = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        rows = active(c)
        assert len(rows) == 1 and rows[0].summary == "用户的堂姐的职业是摄影师"
        assert rows[0].metadata["fact_slot"] == "relation:堂姐:occupation"
        assert say(c, "请忘记我的堂姐的职业").status == "forgotten"
        assert not active(c)
    finally:
        c.close()


def test_semantic_field_hint_can_forget_legacy_copula_without_rewriting_it(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        memory = c.story_runtime.memory
        old = memory.confirm_candidate(memory.propose_explicit_user_memory("请记住：我的堂姐是木工。", now=0), now=0)
        say(c, "我的名字是小满")
        extraction = ChatMemoryExtraction(memory)
        text = "请忘记我的堂姐的职业"
        envelope = extraction.prepare(text, now=0, mode="off", generation=0)
        p = MemoryProposal("forget", text, "", "relation_occupation", "人物职业", (old.memory_id,), "explicit", "personal")
        assert extraction.apply(envelope, (p,), now=0, mode="off", generation=0).status == "forgotten"
        assert [m.summary for m in active(c)] == ["用户的名字是小满"]
    finally:
        c.close()


@pytest.mark.parametrize("text", ["我的邻居是新朋友", "我的搭档是认真的", "我的表哥是队长"])
def test_copula_without_semantic_field_hint_does_not_default_to_occupation(tmp_path, text):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        assert say(c, text).status == "ignored"
        assert not active(c)
    finally:
        c.close()


@pytest.mark.parametrize("certainty,scene", [("uncertain", "personal"), ("explicit", "other")])
def test_copula_field_hint_requires_explicit_personal_classification(tmp_path, certainty, scene):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        extraction = ChatMemoryExtraction(c.story_runtime.memory)
        text = "我的堂姐是木工"
        envelope = extraction.prepare(text, now=0, mode="auto", generation=0)
        p = MemoryProposal("remember", text, "木工", "relation_occupation", "人物职业", (), certainty, scene)
        assert extraction.apply(envelope, (p,), now=0, mode="auto", generation=0).status in {"ignored", "clarify"}
        assert not active(c)
    finally:
        c.close()


@pytest.mark.parametrize("predicate,domain", [("name", "称呼"), ("legal_name", "姓名"), ("residence", "居住地")])
def test_misclassified_relation_copula_cannot_become_user_attribute(tmp_path, predicate, domain):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        extraction = ChatMemoryExtraction(c.story_runtime.memory)
        text = "我的搭档是翻译"
        envelope = extraction.prepare(text, now=0, mode="auto", generation=0)
        p = MemoryProposal("remember", text, "翻译", predicate, domain, (), "explicit", "personal")
        assert extraction.apply(envelope, (p,), now=0, mode="auto", generation=0).status == "clarify"
        assert not active(c)
    finally:
        c.close()


@pytest.mark.parametrize("text,value,predicate,domain", [
    ("我的名字是小满", "小满", "legal_name", "姓名"),
    ("我的职业是木工", "木工", "occupation", "职业"),
])
def test_self_field_is_not_mistaken_for_relation_copula(tmp_path, text, value, predicate, domain):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        extraction = ChatMemoryExtraction(c.story_runtime.memory)
        envelope = extraction.prepare(text, now=0, mode="auto", generation=0)
        p = MemoryProposal("remember", text, value, predicate, domain, (), "explicit", "personal")
        assert extraction.apply(envelope, (p,), now=0, mode="auto", generation=0).status == "saved"
        assert active(c)[0].metadata["fact_slot"] == domain
    finally:
        c.close()
