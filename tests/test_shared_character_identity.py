import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import validate_judgment, hard_eligibility
from guanghe_companion.retrieval_contract import RetrievalIntent, RetrievalPlan


NOW = int(datetime(2026, 3, 3, tzinfo=timezone.utc).timestamp())


@pytest.mark.parametrize('name,text,allowed', [
    ('林澈', '我和林澈把纸灯做好了，取名暖云。', True),
    ('望舒', '我和望舒把纸灯做好了，取名暖云。', True),
    ('望舒', '我和林澈把纸灯做好了，取名暖云。', False),
    ('林澈', '我和叫林澈的同事把纸灯做好了，取名暖云。', False),
    ('林澈', '我和林澈老师把纸灯做好了，取名暖云。', False),
    ('林澈', '我和林澈风把纸灯做好了，取名暖云。', False),
    ('林澈', '如果我和林澈把纸灯做好了，就取名暖云。', False),
    ('林澈', '我和林澈约好明天做纸灯，取名暖云。', False),
    ('林澈', '我和林澈没有把纸灯做好。', False),
    ('林澈', '听同事说我和林澈把纸灯做好了。', False),
    ('林澈', '2026年3月1日我和林澈一起复盘纸灯：最初灯罩太窄。', True),
    ('林澈', '2026年3月9日我和林澈一起复盘纸灯：最初灯罩太窄。', False),
    ('林澈', '2026年3月9日我和林澈把纸灯做好了。', False),
])
def test_named_character_requires_current_host_identity_and_actual_source(tmp_path, name, text, allowed):
    service = EmotionalMemoryService(root=tmp_path, character_id='character_a', character_name=name,
        time_basis='unix')
    entry = service.remember(kind='用户事实', title='共同经历', summary=text,
        source='user_chat', source_ids=('dialogue:one',), now=NOW - 86400,
        metadata={'speaker': 'user', 'participants': ['user:self', 'character:self']})
    query = '我们一起做的纸灯叫什么？'
    intent = RetrievalIntent('episode', query, requires_shared_event=True)
    proof = {'id': entry.memory_id, 'quote': text, 'participants': ['user:self', 'character:self']}
    raw = json.dumps({'intents': [{'route': 'episode', 'question_ref': 0, 'status': 'sufficient',
        'claim_use': 'completed_event', 'evidence': [proof]}]}, ensure_ascii=False)
    result = validate_judgment(raw, query=query, plan=RetrievalPlan((intent,)), entries=(entry,), now=NOW,
        owner_id=service.owner_id, character_id=service.character_id, character_name=service.character_name,
        archive_time_basis=service.time_basis, archive_timezone=service.timezone_name)
    assert bool(result.source_ids) is allowed
    if allowed:
        claim = result.source_claims[0][entry.memory_id]
        args = dict(now=NOW, owner_id=service.owner_id, character_id=service.character_id,
            character_name=name, source_claim=claim, archive_time_basis='unix', archive_timezone='UTC')
        assert hard_eligibility(entry, intent, **args)
        assert not hard_eligibility(entry, intent, **{**args, 'character_name': '另一角色'})
        assert not hard_eligibility(replace(entry, deleted=True), intent, **args)
        assert not hard_eligibility(replace(entry, owner_id='another'), intent, **args)
        assert not hard_eligibility(replace(entry, character_id='other'), intent, **args)
        assert not hard_eligibility(replace(entry, scope='private'), intent, **args)


def test_display_name_alone_does_not_authorize_same_named_person(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id='character_a', character_name='林澈')
    entry = service.remember(kind='用户事实', title='人物活动', summary='我和林澈把纸灯做好了。',
        source='user_chat', source_ids=('source:one',), now=10)
    intent = RetrievalIntent('episode', '我们做了什么？', requires_shared_event=True)
    claim = {'quote': entry.summary, 'use': 'completed_event', 'participants': ['user:self', 'character:self']}
    assert not hard_eligibility(entry, intent, now=10, owner_id=service.owner_id,
        character_id=service.character_id, character_name=service.character_name, source_claim=claim)


def test_controller_rebinds_memory_display_name_when_switching_real_packs(tmp_path):
    from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        previous = controller.story_runtime.memory
        assert previous.character_name == controller.character_pack.name
        controller.switch_character('nairong_pixel_pet', include_ai_expression=False)
        current = controller.story_runtime.memory
        assert current is not previous
        assert current.character_name == controller.character_pack.name
        assert current.character_name != previous.character_name
        assert current.character_id == controller.character_pack.character_id
    finally:
        controller.close()
