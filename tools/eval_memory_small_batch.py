import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
from urllib import request
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools'), str(ROOT)]

from eval_ondemand_generation import RecordingTransport, redact, production_policy
from eval_ondemand_memory import load_datasets, make_entries, story_clock, expression_history, provider_evidence_payload, score_query
from eval_ondemand_presentation import common_persona
from persona_behavior_eval import measured_usage
from guanghe_companion.emotional_memory import EmotionalMemoryEntry
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.expression_clients import client_config_from_settings, _default_transport
from guanghe_companion.expression_settings import ExpressionSettingsStore
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge
from guanghe_companion.retrieval_contract import RetrievalBudget
from guanghe_companion.semantic_memory import SemanticMemoryRetriever


def reserve_request(payload, reserved, calls):
    if payload.get('model') != 'deepseek-flash' or payload.get('tools'):
        raise ValueError('only Flash text requests are allowed')
    if calls >= 10 or not 1 <= payload.get('max_tokens', 0) <= 4096:
        raise ValueError('request/output limit reached')
    # UTF-8字节数保守覆盖文本token；额外预留消息封装，全部按高峰未缓存价。
    size = len(json.dumps(payload['messages'], ensure_ascii=False).encode('utf-8')) + 1024
    upper = (Decimal(size) * 2 + Decimal(payload['max_tokens']) * 8) / 1000000
    if reserved + upper > Decimal('0.50'):
        raise ValueError('batch reserved cost would exceed CNY 0.50')
    return reserved + upper


class BatchMeter(RecordingTransport):
    def __init__(self, output, secret):
        super().__init__(delegate=_default_transport, api_style='chat', max_output_tokens=4096, max_requests=10)
        self.output, self.secret = output, secret
        self.reserved = Decimal('0')
        self.stopped = False

    def __call__(self, req, timeout):
        if self.stopped:
            raise RuntimeError('batch stopped after transport failure')
        self.reserved = reserve_request(json.loads(req.data), self.reserved, self.calls)
        stamp = datetime.now(timezone.utc).isoformat()
        try:
            return super().__call__(req, timeout)
        except Exception as exc:
            self.stopped = True
            if self.records:
                self.records[-1]['error_type'] = type(exc).__name__
                if isinstance(exc, HTTPError):
                    self.records[-1].update(http_status=exc.code, raw_error=exc.read().decode('utf-8', errors='replace'))
            raise
        finally:
            if self.records:
                self.records[-1]['requested_at_utc'] = stamp
            self.output.write_text(json.dumps(redact({'calls': self.records}, self.secret), ensure_ascii=False, indent=2), encoding='utf-8')


def usage_cost(records):
    total = Decimal('0')
    for row in records:
        usage = row.get('provider_response', {}).get('usage')
        if usage is None:
            continue
        local = datetime.fromisoformat(row['requested_at_utc']).astimezone(ZoneInfo('Asia/Shanghai'))
        # 本批在周末执行，无需推断中国调休工作日；工作日调用须另行核对费率。
        if local.weekday() < 5:
            raise ValueError('weekday pricing requires a verified holiday calendar')
        hit = usage.get('prompt_cache_hit_tokens', 0)
        miss = usage.get('prompt_cache_miss_tokens', usage.get('prompt_tokens', 0) - hit)
        total += (Decimal(hit) * Decimal('0.02') + Decimal(miss) + Decimal(usage.get('completion_tokens', 0)) * 4) / 1000000
    return str(total)


def balance(settings):
    req = request.Request('https://api.deepseek.com/user/balance', headers={'Authorization': 'Bearer ' + settings.api_key})
    with request.urlopen(req, timeout=15) as response:
        value = json.load(response)
    return {item['currency']: item['total_balance'] for item in value['balance_infos']}


def run(args):
    data = load_datasets(args.dataset_dir, ['holdout'])[0]
    queries = [q for q in data['queries'] if q['id'] in {'cq3', 'sq4'}]
    if len(queries) != 2:
        raise ValueError('requires the two specified seen regression cases')
    before = json.loads(args.before.read_text(encoding='utf-8'))
    review = json.loads(args.review_journal.read_text(encoding='utf-8'))['calls'][2]
    settings = ExpressionSettingsStore(args.app_settings).load()
    if settings.model != 'deepseek-flash' or settings.base_url.rstrip('/') not in {'https://api.deepseek.com', 'https://api.deepseek.com/v1'}:
        raise ValueError('requires official configured Flash')
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'scope': 'three seen failures only, not independent generalization or full lifecycle acceptance',
        'limits': {'calls': 10, 'output_tokens_per_call': 4096, 'reserved_peak_cny': '0.50'},
        'pricing_source': 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
        'price_cny_per_million': {'offpeak_cached': '0.02', 'offpeak_input': '1', 'offpeak_output': '4',
                                'reserved_peak_input': '2', 'reserved_peak_output': '8'},
        'rows': [], 'status': 'not_run'}
    def save():
        (args.output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    if not args.execute:
        return
    if datetime.now(ZoneInfo('Asia/Shanghai')).weekday() < 5:
        raise ValueError('verify weekday holiday pricing before running this saved weekend batch')
    report['balance_before'] = balance(settings)
    meter = BatchMeter(args.output / 'provider-calls.json', settings.api_key)
    client = client_config_from_settings(settings).client
    client.transport = meter
    client.max_tokens = 4096
    judge = MemoryEvidenceJudge(client)
    semantic = SemanticMemoryRetriever(cache_dir=args.model_cache, character_id=data['character_id'],
        owner_id=data['owner_id'], local_files_only=True)
    expressor = ShinsekaiAIExpressor(llm_client=client, timeout_seconds=60, dialogue_policy=production_policy())
    try:
        messages = review['wire_payload']['messages']
        original = json.loads(messages[1]['content'])
        raw = client.complete(messages[1]['content'], system_prompt=messages[0]['content'], reasoning_effort='none')
        revised = json.loads(raw)
        report['rows'].append({'id': 'review_format', 'before_call': review, 'original_review_input': original,
            'raw_output': raw, 'shape_valid': set(revised) == {'edits', 'speech'} and isinstance(revised['edits'], list)
            and isinstance(revised['speech'], str), 'provider_call_indices': [0]})
        save()
        semantic.warmup().result(timeout=600)
        persona = common_persona(data['character_id'])
        for query in queries:
            if meter.stopped:
                raise RuntimeError('stopped provider batch')
            start = meter.calls
            story = next(s for s in data['stories'] if s['id'] == query['story_id'])
            now, basis = story_clock(data, story)
            entries = make_entries(data, story['id'], 300, EmotionalMemoryEntry)
            service = EmotionalMemoryService(root=args.output / 'archives' / query['id'],
                character_id=data['character_id'], character_name=persona['character_name'], owner_id=data['owner_id'],
                semantic_retriever=semantic, evidence_judge=judge, time_basis=basis,
                retrieval_budget=RetrievalBudget(max_context_chars=6000))
            service.store.save_memories(e for e in entries if e.owner_id == data['owner_id'] and e.character_id == data['character_id'])
            pending = service.prepare_retrieval(query['text'], now=now, history=query.get('history', ()), scope=query['scope'])
            if pending is not None:
                pending.result(timeout=120)
            retrieved = service.retrieve(query['text'], now=now, history=query.get('history', ()), scope=query['scope'], top_k=4, layered=True)
            expr = ExpressionRequest.from_snapshot({'character_name': persona['character_name'], 'focus': 50,
                'charge': 50, 'stability': 50, 'mood': 50, 'trust': 50, 'player_message': query['text'],
                'recent_dialogue': expression_history(query.get('history', []), persona['character_name'])},
                context={'memory_v2_authoritative': True, 'persona': persona, 'emotional_memory': retrieved.bundle.to_prompt_payload()})
            prompt = expressor.build_prompt(expr)
            trace = retrieved.trace.to_dict()
            fingerprints = {e.memory_id: e.evidence_fingerprint() for e in entries}
            sources = {m['id']: {**m, '_expected_fingerprint': fingerprints[m['id']]}
                       for m in data['memories'] if m['story_id'] == story['id']}
            trace['router_evaluated'] = True
            score = score_query(query, provider_evidence_payload(prompt), list(trace['selected_memory_ids']), trace, sources)
            row = {'id': query['id'], 'before': next(r for r in before['rows'] if r['query_id'] == query['id']),
                'query': query['text'], 'after_retrieval': score, 'actual_expression_request': expr.to_prompt_dict(),
                'final_provider_prompt': prompt, 'judge_status': judge.status,
                'format_repair_attempted': judge.format_repair_attempted, 'format_failures': judge.format_failures}
            report['rows'].append(row)
            save()
            if meter.stopped:
                raise RuntimeError('provider failed during evidence preparation')
            row['events'] = expressor.express(expr)
            row['fallback_reason'] = expressor.last_fallback_reason
            row['provider_call_indices'] = list(range(start, meter.calls))
            save()
        report['status'] = 'completed'
    except Exception as exc:
        report.update(status='stopped', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        judge.close()
        semantic.close()
        expressor.close()
        report.update(usage=measured_usage(meter), reserved_peak_cny=str(meter.reserved),
                      usage_price_cny=usage_cost(meter.records))
        save()
        report['balance_after'] = balance(settings)
        save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('dataset-dir', 'before', 'review-journal', 'app-settings', 'model-cache', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    run(parser.parse_args())
