import json

import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.expression_clients import LLMProviderError
from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge


class RecordedProtocolClient:
    base_url = 'https://api.deepseek.com'

    def __init__(self, responses, on_first=None):
        self.responses = iter(responses)
        self.calls = []
        self.on_first = on_first

    def complete(self, prompt, **options):
        self.calls.append((prompt, options))
        if len(self.calls) == 1 and self.on_first:
            self.on_first()
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


def setup(tmp_path, responses, on_first=None):
    service = EmotionalMemoryService(root=tmp_path, character_id='xingxi_pixel_pet')
    entry = service.remember(kind='用户事实', title='物品', summary='我的画笔放在藤盒里。',
        source='user_chat', source_ids=('source:brush',), now=10)
    client = RecordedProtocolClient(responses, on_first)
    service.evidence_judge = MemoryEvidenceJudge(client)
    return service, entry, client


UNKNOWN = json.dumps({'intents': [{'route': 'fact', 'question_ref': 0,
    'claim_use': 'current_attribute', 'status': 'unknown', 'evidence': []}]})


@pytest.mark.parametrize('first', [
    LLMProviderError('empty completion', public_reason='invalid_response_text'),
    '{"intents":[{"route":"fact","subject_binding":{"quote":"小',
])
def test_recorded_empty_or_truncated_protocol_gets_one_nonreasoning_repair(tmp_path, first):
    service, _, client = setup(tmp_path, [first, UNKNOWN])
    try:
        service.prepare_retrieval('我的画笔放在哪里？', now=10).result(timeout=5)
        assert len(client.calls) == 2
        assert client.calls[0][0] == client.calls[1][0]
        assert client.calls[0][1]['reasoning_effort'] == 'low'
        assert client.calls[1][1]['reasoning_effort'] == 'none'
        assert service.evidence_judge.status == 'completed'
        assert len(service.evidence_judge.format_failures) == 1
        assert service.evidence_judge.format_repair_attempted
    finally:
        service.close()


@pytest.mark.parametrize('response', [UNKNOWN, '{"intents":[]}'])
def test_valid_json_never_retries_for_semantics_or_schema(tmp_path, response):
    service, _, client = setup(tmp_path, [response])
    try:
        service.prepare_retrieval('我的画笔放在哪里？', now=10).result(timeout=5)
        assert len(client.calls) == 1
        assert not service.evidence_judge.format_repair_attempted
    finally:
        service.close()


def test_format_repair_is_bounded_and_records_both_failures(tmp_path):
    service, _, client = setup(tmp_path, ['{', '{'])
    try:
        service.prepare_retrieval('我的画笔放在哪里？', now=10).result(timeout=5)
        assert len(client.calls) == 2
        assert len(service.evidence_judge.format_failures) == 2
        assert service.evidence_judge.status.startswith('unavailable:')
    finally:
        service.close()


def test_revocation_before_repair_stops_second_request(tmp_path):
    service, entry, client = setup(tmp_path, ['{', UNKNOWN])
    client.on_first = lambda: service.forget(entry.memory_id, now=10)
    try:
        service.prepare_retrieval('我的画笔放在哪里？', now=10).result(timeout=5)
        assert len(client.calls) == 1
        assert service.evidence_judge.status == 'stale'
    finally:
        service.close()


@pytest.mark.parametrize('reason', ['timeout', 'unauthorized', 'invalid_response_shape'])
def test_other_provider_errors_do_not_reissue_request(tmp_path, reason):
    service, _, client = setup(tmp_path, [LLMProviderError(reason, public_reason=reason)])
    try:
        service.prepare_retrieval('我的画笔放在哪里？', now=10).result(timeout=5)
        assert len(client.calls) == 1
        assert not service.evidence_judge.format_repair_attempted
    finally:
        service.close()


def test_unverified_provider_does_not_receive_deepseek_specific_repair(tmp_path):
    service, _, client = setup(tmp_path, ['{'])
    client.base_url = 'https://another-provider.invalid'
    try:
        service.prepare_retrieval('我的画笔放在哪里？', now=10).result(timeout=5)
        assert len(client.calls) == 1
        assert not service.evidence_judge.format_repair_attempted
    finally:
        service.close()
