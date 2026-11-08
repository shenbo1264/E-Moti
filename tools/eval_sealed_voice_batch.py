import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]

from eval_memory_process_restart import ProcessBatchMeter, initialize_budget, write_json
from eval_memory_small_batch import balance, usage_cost
from eval_ondemand_generation import production_policy
from eval_ondemand_presentation import common_persona
from persona_behavior_eval import measured_usage
from guanghe_companion.expression_clients import client_config_from_settings
from guanghe_companion.expression_settings import ExpressionSettingsStore
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_request import ExpressionRequest


def run(args):
    raw = args.input.read_bytes()
    data = json.loads(raw)
    cases = data['voice']
    if len(cases) != 3 or len({row['id'] for row in cases}) != 3:
        raise ValueError('exactly three distinct sealed cases required')
    if any(not isinstance(row['text'], str) or not 0 < len(row['text']) <= 500 for row in cases):
        raise ValueError('invalid voice input')
    settings = ExpressionSettingsStore(args.app_settings).load()
    if settings.model != 'deepseek-flash' or settings.base_url.rstrip('/') not in {'https://api.deepseek.com', 'https://api.deepseek.com/v1'}:
        raise ValueError('official Flash configuration required')
    args.output.mkdir(parents=True, exist_ok=False)
    initialize_budget(args.output / 'budget.json')
    meter = ProcessBatchMeter(args.output, settings.api_key)
    client = client_config_from_settings(settings).client
    client.max_tokens = 4096
    client.transport = meter
    persona = common_persona('xingxi_pixel_pet')
    report = {'status': 'running', 'input_sha256': hashlib.sha256(raw).hexdigest(),
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'scope': 'three sealed production expressions; expected answers never sent to provider',
        'rows': [], 'grading': 'not_run', 'limits': {'requests': 10, 'reserved_cny': '0.50'}}
    try:
        report['balance_before'] = balance(settings)
        with ShinsekaiAIExpressor(llm_client=client, timeout_seconds=60, dialogue_policy=production_policy()) as expressor:
            for case in cases:
                expression = ExpressionRequest.from_snapshot({'character_name': persona['character_name'],
                    'player_message': case['text'], 'focus': 50, 'charge': 50, 'stability': 50,
                    'mood': 50, 'trust': 50}, context={'persona': persona})
                start = meter.calls
                row = {'id': case['id'], 'text': case['text'], 'provider_prompt': expressor.build_prompt(expression)}
                report['rows'].append(row)
                row['events'] = expressor.express(expression)
                row['fallback_reason'] = expressor.last_fallback_reason
                row['call_indices'] = list(range(start, meter.calls))
                write_json(args.output / 'results.json', report)
                if row['fallback_reason'] or meter.stopped:
                    raise RuntimeError('expression failed; no repeated or replacement sample')
        report['status'] = 'completed'
    except Exception as exc:
        report.update(status='stopped', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        report.update(usage=measured_usage(meter), usage_price_cny=usage_cost(meter.records),
            reserved_peak_cny=str(meter.reserved))
        write_json(args.output / 'results.json', report)
        client.close()
        meter.close()
        report['balance_after'] = balance(settings)
        write_json(args.output / 'results.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--app-settings', type=Path, required=True)
    run(parser.parse_args())
