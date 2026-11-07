import argparse
import ast
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools'), str(ROOT)]

from eval_memory_small_batch import BatchMeter, balance, usage_cost
from eval_ondemand_generation import production_policy
from eval_ondemand_presentation import common_persona
from persona_behavior_eval import measured_usage
from guanghe_companion.expression_clients import client_config_from_settings
from guanghe_companion.expression_settings import ExpressionSettingsStore
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_refinement import build_refinement_prompt, review_rules
from guanghe_companion.expression_request import ExpressionRequest


def old_rules():
    source = subprocess.check_output(['git', 'show', 'a8e2dd6:src/guanghe_companion/expression_refinement.py'], cwd=ROOT).decode()
    assignment = next(node for node in ast.parse(source).body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == '_REVIEW' for target in node.targets))
    return '\n'.join(ast.literal_eval(assignment.value))


def run(args):
    if datetime.now(ZoneInfo('Asia/Shanghai')).weekday() < 5:
        raise ValueError('verify weekday pricing before using weekend accounting')
    settings = ExpressionSettingsStore(args.app_settings).load()
    if settings.model != 'deepseek-flash' or settings.base_url.rstrip('/') not in {'https://api.deepseek.com', 'https://api.deepseek.com/v1'}:
        raise ValueError('requires official Flash settings')
    args.output.mkdir(parents=True, exist_ok=False)
    meter = BatchMeter(args.output / 'provider-calls.json', settings.api_key)
    client = client_config_from_settings(settings).client
    client.transport = meter
    client.max_tokens = 1024
    persona = common_persona('xingxi_pixel_pet')

    def expression(text):
        return ExpressionRequest.from_snapshot({'character_name': persona['character_name'], 'player_message': text,
            'focus': 50, 'charge': 50, 'stability': 50, 'mood': 50, 'trust': 50}, context={'persona': persona})

    report = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'status': 'running', 'scope': 'three review comparisons and two production expression controls; no memory writes',
        'limits': {'model_requests': 10, 'peak_reserved_cny': '0.50', 'review_max_output_tokens': 1024,
                   'production_max_output_tokens': 4096}, 'rows': [], 'balance_before': balance(settings)}

    def save():
        report.update(usage=measured_usage(meter), reserved_peak_cny=str(meter.reserved), usage_price_cny=usage_cost(meter.records))
        (args.output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    def review(prompt, rules):
        start = meter.calls
        raw = client.complete(prompt, system_prompt=rules, reasoning_effort='none')
        parsed = json.loads(raw)
        if set(parsed) != {'edits', 'speech'} or not isinstance(parsed['speech'], str) or not isinstance(parsed['edits'], list):
            raise ValueError('invalid review response')
        return {'raw_output': raw, 'parsed': parsed, 'provider_call_indices': list(range(start, meter.calls))}

    try:
        known = json.loads(args.previous_calls.read_text(encoding='utf-8'))['calls'][0]
        prompt = known['wire_payload']['messages'][1]['content']
        row = {'id': 'known_preference', 'mode': 'same_saved_review_input', 'input': json.loads(prompt), 'before_call': known}
        report['rows'].append(row)
        row['after'] = review(prompt, review_rules())
        save()
        cases = [
            ('keyboard_color', '我把键盘换成了米白色。', '[calm] 米白色看着柔和些。选这个的人，审美果然不一般。'),
            ('watering', '我给阳台的薄荷浇水了。', '[joy] 薄荷又喝饱啦。你真是个细心又靠谱的人。'),
        ]
        for case_id, text, draft in cases:
            prompt = build_refinement_prompt(expression(text), {'type': 'speech', 'speech': draft, 'effect': 'ATTENTION'})
            row = {'id': case_id, 'mode': 'controlled_synthetic_draft_review', 'input': json.loads(prompt)}
            report['rows'].append(row)
            row['before'] = review(prompt, old_rules())
            save()
            row['after'] = review(prompt, review_rules())
            save()
        client.max_tokens = 4096
        expressor = ShinsekaiAIExpressor(llm_client=client, timeout_seconds=60, dialogue_policy=production_policy())
        try:
            for case_id, text in (
                ('own_preference', '我喜欢酸一点的柠檬蛋糕，你呢？'),
                ('requested_praise', '我终于把拖了两天的抽屉整理好了，夸我一句吧。'),
            ):
                if meter.stopped:
                    raise RuntimeError('provider batch stopped')
                expr = expression(text)
                start = meter.calls
                row = {'id': case_id, 'mode': 'production_expression', 'request': expr.to_prompt_dict(),
                       'provider_prompt': expressor.build_prompt(expr)}
                report['rows'].append(row)
                row['events'] = expressor.express(expr)
                row['fallback_reason'] = expressor.last_fallback_reason
                row['provider_call_indices'] = list(range(start, meter.calls))
                save()
        finally:
            expressor.close()
        report['status'] = 'completed'
    except Exception as exc:
        report.update(status='stopped', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        client.close()
        save()
        report['balance_after'] = balance(settings)
        save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('app-settings', 'previous-calls', 'output'):
        parser.add_argument('--' + key, required=True, type=Path)
    run(parser.parse_args())
