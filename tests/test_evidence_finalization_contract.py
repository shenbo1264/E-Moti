import json
from dataclasses import replace

import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import validate_judgment, resolve_judged_subjects, _alias_source_binding
from guanghe_companion.retrieval_contract import RetrievalIntent, RetrievalPlan


@pytest.mark.parametrize('basis,allowed', [(None, True), ('unix', True), ('logical', False)])
def test_future_finalization_inherits_archive_without_overriding_card(tmp_path, basis, allowed):
    service = EmotionalMemoryService(root=tmp_path, character_id='xingxi_pixel_pet', time_basis='unix')
    entry = service.remember(kind='用户事实', title='编号', summary='新版编号未来生效。',
        source='explicit_user_request', source_ids=('source:one',), now=10, valid_from=100)
    with service.store._document() as document:
        for raw in document['entries']:
            if raw['memory_id'] == entry.memory_id:
                raw['metadata'].pop('time_basis')
                if basis:
                    raw['metadata']['time_basis'] = basis
    entry = replace(entry, metadata={k: v for k, v in entry.metadata.items() if k != 'time_basis'})
    if basis:
        entry = replace(entry, metadata={**entry.metadata, 'time_basis': basis})
    epoch = service.store.current_context_epoch(now=10)
    result = service.store.finalize_indexed_recall((entry,), expected_epoch=epoch, now=10,
        valid_at_by_id={entry.memory_id: 110}, record_access=False)
    assert (result is not None) is allowed
    service.forget(entry.memory_id, now=11)
    assert service.store.finalize_indexed_recall((entry,), expected_epoch=epoch, now=11,
        valid_at_by_id={entry.memory_id: 110}, record_access=False) is None


@pytest.mark.parametrize('text,allowed', [
    ('装订工作定在下周五晚上七点，现在尚未进行。', True),
    ('装订工作定于下周五晚上七点，现在尚未进行。', True),
    ('如果装订工作定在下周五，就再说。', False),
    ('装订工作定在下周五，但已经取消。', False),
    ('画框固定在墙上。', False),
])
def test_explicit_scheduling_predicate_is_source_evidence(tmp_path, text, allowed):
    service = EmotionalMemoryService(root=tmp_path, character_id='xingxi_pixel_pet')
    entry = service.remember(kind='用户事实', title='安排', summary=text,
        source='explicit_user_request', source_ids=('source:one',), now=10)
    query = '装订工作有什么安排？'
    result = validate_judgment(json.dumps({'intents': [{'route': 'fact', 'question_ref': 0,
        'claim_use': 'planned_event', 'status': 'sufficient',
        'evidence': [{'id': entry.memory_id, 'quote': entry.summary}]}]}, ensure_ascii=False),
        query=query, plan=RetrievalPlan((RetrievalIntent('fact', query),)), entries=(entry,),
        now=10, owner_id=service.owner_id, character_id=service.character_id)
    assert bool(result.source_ids) is allowed


def test_identity_evidence_can_bind_a_separate_planned_event(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id='xingxi_pixel_pet')
    identity = service.remember(kind='用户事实', title='人物', summary='杜昭是我的堂兄，家里叫他阿昭。',
        source='explicit_user_request', source_ids=('source:identity',), now=10,
        metadata={'fact_subject': 'person:du_zhao', 'fact_predicate': 'relationship',
                  'fact_value': '堂兄', 'subject_aliases': ['杜昭', '阿昭']})
    event = service.remember(kind='用户事实', title='活动', summary='我和杜昭约好下周一起装订画册，现在还没做。',
        source='explicit_user_request', source_ids=('source:event',), now=10,
        metadata={'fact_subject': 'event:binding', 'fact_predicate': 'craft_plan', 'fact_value': '装订画册'})
    query = '我和阿昭约好做什么？'
    plan = RetrievalPlan((RetrievalIntent('fact', query, subjects=('阿昭',)),))
    row = {'route': 'fact', 'question_ref': 0, 'claim_use': 'planned_event', 'status': 'sufficient',
        'subject_binding': {'mention': '阿昭', 'subject': 'person:du_zhao', 'kind': 'alias', 'quote': identity.summary},
        'evidence': [{'id': event.memory_id, 'quote': event.summary}]}
    result = validate_judgment(json.dumps({'intents': [row]}, ensure_ascii=False), query=query, plan=plan,
        entries=(identity, event), now=10, owner_id=service.owner_id, character_id=service.character_id)
    assert event.memory_id in result.source_ids
    assert identity.memory_id in result.binding_sources[0]
    _, unresolved, _ = resolve_judged_subjects(service.store, result, 0, now=10)
    assert not unresolved
    service.forget(identity.memory_id, now=11)
    assert resolve_judged_subjects(service.store, result, 0, now=11)[1]


def test_shared_participants_must_belong_to_each_literal_source(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id='xingxi_pixel_pet')
    entry = service.remember(kind='用户事实', title='共同经历', summary='我和你把纸灯做好了，给它取名暖云。',
        source='explicit_user_request', source_ids=('source:light',), now=10)
    query = '我们把做好的纸灯叫什么？'
    plan = RetrievalPlan((RetrievalIntent('episode', query, requires_shared_event=True),))
    proof = {'id': entry.memory_id, 'quote': entry.summary}
    row = {'route': 'episode', 'question_ref': 0, 'claim_use': 'completed_event',
           'status': 'sufficient', 'participants': ['user:self', 'character:self'], 'evidence': [proof]}
    def validate(current):
        return validate_judgment(json.dumps({'intents': [current]}, ensure_ascii=False), query=query,
            plan=plan, entries=(entry,), now=10, owner_id=service.owner_id, character_id=service.character_id)
    assert not validate(row).source_ids
    row['evidence'] = [{**proof, 'participants': row.pop('participants')}]
    assert validate(row).source_ids == (entry.memory_id,)
    row['evidence'][0]['quote'] = '给它取名暖云。'
    assert not validate(row).source_ids


def test_identity_plan_fix_preserves_explicit_historical_validity(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id='xingxi_pixel_pet', time_basis='unix')
    identity = service.remember(kind='用户事实', title='旧称呼', summary='杜昭当时叫阿昭。',
        source='explicit_user_request', source_ids=('source:identity',), now=10,
        valid_until=20, metadata={'fact_subject': 'person:du_zhao', 'fact_predicate': 'nickname',
            'fact_value': '阿昭', 'subject_aliases': ['阿昭']})
    binding = {'mention': '阿昭', 'subject': 'person:du_zhao', 'quote': identity.summary}
    intent = RetrievalIntent('fact', '当时阿昭是谁？', temporal_mode='as_of', as_of=15, as_of_end=16)
    result = _alias_source_binding(binding, (identity,), intent, now=30,
        owner_id=service.owner_id, character_id=service.character_id)
    assert result[0] == ('阿昭', 'person:du_zhao')
    service.close()
