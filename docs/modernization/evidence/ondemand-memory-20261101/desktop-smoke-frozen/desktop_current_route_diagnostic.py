"""Post-freeze diagnostic, not a replacement or edit of the frozen smoke oracle.

Exercises actual QCoreApplication delivery, SQLite, production prompt building,
and real local BGE. The completed event is explicitly a synthetic test fixture.
No generation provider is configured or called and no visible window is tested.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from threading import get_ident

ROOT = Path('/workspace/scratch/ac4f72a6307d/development/E-Moti-ondemand-memory')
OUTPUT = ROOT / 'docs/modernization/evidence/ondemand-memory-20261101/desktop-smoke-frozen'
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from PySide6.QtCore import QCoreApplication
from desktop_memory_smoke import open_host, send, wait
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.focus_companion_runtime import FocusSkillEvent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(controller, query):
    controller._require_host_thread()
    controller._current_player_message = query
    try:
        context = controller.get_expression_context()
        request = ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=context)
        prompt = controller.ai_expressor.build_prompt(request)
        line = next(line for line in prompt.splitlines() if line.startswith('emotional_memory: '))
        payload = json.loads(line.removeprefix('emotional_memory: '))
        ids = [row['memory_id'] for row in payload.get('shared_memories', ())]
        for claim in payload.get('memory_overview', {}).get('claims', ()):
            ids.extend(claim.get('source_ids', ()))
        memory = controller.story_runtime.memory
        return {'query': query, 'prompt': prompt, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
            'prompt_status': 'built_not_sent', 'actual_provider_memory': payload, 'final_evidence_ids': sorted(set(ids)),
            'persona': request.persona, 'trace': memory.last_retrieval_trace.to_dict(),
            'semantic_status': memory.semantic_retriever.status,
            'semantic_cosines': memory.semantic_retriever.last_cosines}
    finally:
        controller._current_player_message = ''


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    paths = sorted((ROOT / 'src').rglob('*.py')) + [ROOT / 'tools/desktop_memory_smoke.py']
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    report = {'status': 'running', 'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_sha256': hashes, 'diagnostic_script_sha256': digest(Path(__file__)),
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'runtime': 'real Qt QCoreApplication event loop with QT_QPA_PLATFORM=offscreen; no visible GUI',
        'generation': 'not_run', 'generation_requests': 0, 'api_mode': 'disabled expressor, no --live',
        'steps': [], 'snapshots': {}, 'checks': {}, 'signal_threads': [], 'owner_thread': get_ident(),
        'limits': ['synthetic event fixture, not a genuine user-shared event',
            'one integration smoke, not retrieval accuracy evaluation', 'no actual model-generated answer',
            'persona configuration and provider prompt only, not behavioral consistency',
            'headless Qt dispatch, not rendered desktop or Windows device validation']}
    app = QCoreApplication.instance() or QCoreApplication([])
    drink = '下次见面给我捎点喝的，选哪一种比较合适？'
    episode_query = '还记得我们第一次一起摄影发生了什么吗？'
    controller = desktop = None
    with tempfile.TemporaryDirectory(prefix='emoti-desktop-current-route-') as temporary:
        def reopen():
            c, d = open_host(Path(temporary))
            d.snapshot_changed.connect(lambda unused: report['signal_threads'].append(get_ident()))
            return c, d
        try:
            controller, desktop = reopen()
            report['steps'].append(send(app, controller, desktop, '我喜欢乌龙茶，不喜欢太甜的饮料。'))
            before_ids = {row.memory_id for row in controller.story_runtime.memory.store.load_memories() if not row.deleted}
            desktop.close(); controller.close()
            controller, desktop = reopen()
            wait(app, controller.enable_semantic_memory(cache_dir=Path('/tmp/emoti-bge-model-cache'), local_files_only=True))
            report['checks']['restart_retains_exact_memory_ids'] = before_ids == {
                row.memory_id for row in controller.story_runtime.memory.store.load_memories() if not row.deleted}
            report['steps'].append(send(app, controller, desktop, drink))
            before = capture(controller, drink)
            report['snapshots']['before_correction'] = before
            report['checks']['fact_route_with_sufficient_evidence'] = (
                before['actual_provider_memory']['retrieval']['routes'] == ['fact']
                and before['actual_provider_memory']['retrieval']['status'] == 'sufficient')
            report['checks']['both_preferences_delivered_from_sources'] = (
                len(before['final_evidence_ids']) == 2 and before_ids == set(before['final_evidence_ids'])
                and '乌龙茶' in before['prompt'] and '不喜欢太甜' in before['prompt'])
            report['checks']['fact_query_avoids_passage_and_query_embedding'] = (
                before['semantic_status']['model_loaded']
                and before['semantic_status']['encoded_entries_total'] == 0
                and before['semantic_status']['query_embed_count'] == 0
                and before['trace']['semantic_status'] == 'not_needed')

            event = controller.story_runtime.record_focus_completion(FocusSkillEvent(
                event_type='focus_break_completed', speech='诊断事件已经结算', motion='relaxed',
                payload={'skill_id': 'synthetic_desktop_smoke'},
                memory_draft={'summary': '我们一起完成了第一次摄影活动，在公园拍摄飞鸟。'}),
                now=int(controller.now), event_id='fixture:desktop-smoke:completed-photography')
            report['synthetic_settled_event'] = event.to_dict()
            report['steps'].append(send(app, controller, desktop, episode_query))
            episode = capture(controller, episode_query)
            report['snapshots']['episode'] = episode
            report['checks']['episode_query_uses_real_bge_on_qt_worker'] = (
                episode['trace']['route'] == ('episode',)
                and episode['semantic_status']['query_embed_count'] > 0
                and episode['semantic_status']['encoded_entries_total'] >= 1
                and event.memory_id in episode['semantic_cosines'])
            report['checks']['completed_event_source_delivered'] = (
                event.memory_id in episode['final_evidence_ids']
                and '在公园拍摄飞鸟' in episode['prompt']
                and episode['actual_provider_memory']['retrieval']['status'] == 'sufficient')

            report['steps'].append(send(app, controller, desktop, '我现在改喝红茶了。'))
            report['steps'].append(send(app, controller, desktop, drink))
            corrected = capture(controller, drink)
            report['snapshots']['after_correction'] = corrected
            report['checks']['correction_replaces_value_in_final_provider_prompt'] = (
                '红茶' in corrected['prompt'] and '乌龙茶' not in corrected['prompt']
                and corrected['actual_provider_memory']['retrieval']['status'] == 'sufficient')
            report['steps'].append(send(app, controller, desktop, '别再记我的饮料偏好了。'))
            report['steps'].append(send(app, controller, desktop, drink))
            forgotten = capture(controller, drink)
            report['snapshots']['after_forget'] = forgotten
            report['checks']['forgotten_fact_is_unknown_without_nearby_event_leak'] = (
                forgotten['actual_provider_memory']['retrieval']['status'] == 'unknown'
                and not forgotten['final_evidence_ids']
                and all(fragment not in forgotten['prompt'] for fragment in ('乌龙茶', '红茶', '不喜欢太甜')))
            report['checks']['persona_configuration_stays_identical'] = before['persona'] == corrected['persona'] == forgotten['persona']
            report['steps'].append(send(app, controller, desktop, episode_query))
            remaining = capture(controller, episode_query)
            report['snapshots']['unrelated_event_retained'] = remaining
            report['checks']['unrelated_valid_event_retained_after_fact_forgetting'] = (
                event.memory_id in remaining['final_evidence_ids'] and '在公园拍摄飞鸟' in remaining['prompt']
                and remaining['semantic_status']['last_encoded_entries'] == 0)
            report['checks']['all_actual_qt_signal_deliveries_on_owner_thread'] = (
                bool(report['signal_threads']) and set(report['signal_threads']) == {report['owner_thread']})
            report['checks']['source_files_unchanged_during_diagnostic'] = all(digest(ROOT / key) == value for key, value in hashes.items())
            report['passed'] = all(report['checks'].values())
            report['status'] = 'passed' if report['passed'] else 'failed'
        except Exception as exc:
            report['status'] = 'failed'
            report['exception'] = {'type': type(exc).__name__, 'message': str(exc)}
            raise
        finally:
            if desktop is not None: desktop.close()
            if controller is not None: controller.close()
            (OUTPUT / 'current-route-diagnostic.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
            shutil.copyfile(Path(__file__), OUTPUT / Path(__file__).name)
    print(json.dumps({'status': report['status'], 'checks': report['checks']}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
