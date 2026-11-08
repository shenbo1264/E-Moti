"""Real pinned-BGE cache maintenance timing, not an answer-quality benchmark."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter

parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--model-cache', type=Path, required=True)
parser.add_argument('--size', type=int)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.size is None:
    runs = []
    for size in (300, 3000, 10000):
        path = args.output.with_name(args.output.stem + '-' + str(size) + '.json')
        subprocess.run([sys.executable, __file__, '--source-root', str(args.source_root),
            '--model-cache', str(args.model_cache), '--size', str(size), '--output', str(path)], check=True)
        runs.append(json.loads(path.read_text()))
    args.output.write_text(json.dumps({'status': 'measured_real_sqlite_and_pinned_bge_synthetic_text',
        'runs': runs, 'not_measured': ['answer correctness', 'LLM generation', 'desktop interaction']}, ensure_ascii=False, indent=2))
    print(json.dumps({'output': str(args.output), 'runs': len(runs)}))
    raise SystemExit
sys.path.insert(0, str(args.source_root / 'src'))
from guanghe_companion.emotional_memory import EmotionalMemoryEntry
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.semantic_memory import SemanticMemoryRetriever, MODEL_NAME, MODEL_REVISION

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
files = ['semantic_memory.py', 'memory_index.py', 'memory_index_schema.py', 'memory_document.py', 'emotional_memory.py']
hashes = {name: digest(args.source_root / 'src/guanghe_companion' / name) for name in files}
templates = [
 '用户在周末练习摄影，记录公园里的飞鸟、花朵与光线变化。这条记录来自用户明确分享的日常兴趣，描述一次已完成的活动。',
 '我们一起整理了书桌上的书籍与便签，给常用工具安排了固定位置。桌面互动事件已完成，来源记录保留了发生时间。',
 '用户喜欢清淡口味，平时会选择不加糖的茶饮。偏好来源是用户的直接陈述，没有推断健康状况或未说过的饮食禁忌。',
 '一次共同学习结束后，我们回顾了三个问题的解决过程，记录了检查条件和验证结果。这段经历来自已完成的互动事件。',
 '用户分享了喜欢的音乐类型和练习乐器的习惯，明确说这些是休息时的兴趣。这里没有记录任何外部软件的临时执行状态。',
 '共同游戏的一局顺利结束，我们记下了合作时发现的小技巧和使用道具的时机。该结果有真实的本地事件标识作为来源。',
]
entries = [EmotionalMemoryEntry(memory_id=f'synthetic-{i:06d}', character_id='xingxi_pixel_pet',
    owner_id='local_user', kind='玩家希望被记住', title=f'合成记忆{i}',
    summary=templates[i % len(templates)] + f' 记录编号{i}。', source='explicit_user_request',
    occurred_at=i + 1, created_at=i + 1, updated_at=i + 1, source_ids=(f'synthetic:{i}',))
    for i in range(args.size)]
entries[0] = replace(entries[0], summary='用户喜欢绿茶', metadata={
    'speaker': 'user', 'fact_slot': 'preference:饮料偏好:like', 'fact_domain': '饮料偏好', 'fact_value': '绿茶'})
now = args.size + 100
with tempfile.TemporaryDirectory(prefix='emoti-incremental-bge-') as temporary:
    memory = EmotionalMemoryService(root=temporary, character_id='xingxi_pixel_pet')
    started = perf_counter()
    memory.store.save_memories(entries)
    seed_ms = (perf_counter() - started) * 1000
    retriever = SemanticMemoryRetriever(cache_dir=args.model_cache, character_id=memory.character_id,
        owner_id=memory.owner_id, local_files_only=True)
    try:
        started = perf_counter()
        retriever.warmup().result(timeout=120)
        model_load_ms = (perf_counter() - started) * 1000
        def run(query, instant):
            started = perf_counter()
            retriever.prepare_indexed(query, memory.store, now=instant).result(timeout=240)
            return {'wall_ms': (perf_counter()-started)*1000, 'status': retriever.status,
                    'top_ids': list(retriever.candidate_ids(query, limit=4))}
        cold = run('我们上次共同游戏留下什么经验', now)
        warm = [run(query, now) for query in ('周末喜欢做什么活动', '一起学习时解决了哪些问题', '有哪些日常饮品偏好')]
        started = perf_counter()
        corrected = memory.correct(entries[0].memory_id, title='饮品偏好更正', summary='用户喜欢白茶', now=now+1)
        correction_write_ms = (perf_counter()-started)*1000
        retriever.invalidate()
        correction = run('用户喜欢什么茶', now+2)
        started = perf_counter()
        memory.forget(corrected.memory_id, now=now+3)
        forget_write_ms = (perf_counter()-started)*1000
        retriever.invalidate()
        forgotten = run('用户喜欢什么茶', now+4)
        assert cold['status']['encoded_entries_total'] == args.size
        assert all(row['status']['last_encoded_entries'] == 0 for row in warm)
        assert correction['status']['last_encoded_entries'] == 1
        assert forgotten['status']['last_encoded_entries'] == 0
        assert forgotten['status']['indexed_entries'] == args.size - 1
        assert entries[0].memory_id not in retriever.last_cosines and corrected.memory_id not in retriever.last_cosines
        result = {'size': args.size, 'source_sha256': hashes,
            'created_at_utc': datetime.now(timezone.utc).isoformat(), 'script_sha256': digest(Path(__file__)),
            'source_unchanged_during_run': all(digest(args.source_root/'src/guanghe_companion'/name)==value for name,value in hashes.items()),
            'model': {'name': MODEL_NAME, 'revision': MODEL_REVISION, 'provider': 'CPUExecutionProvider', 'threads': 2,
                'passage_batch_size': retriever.status['passage_batch_size'],
                'embedding_dimensions': next(iter(retriever._vectors.values())).shape[0]},
            'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                'logical_cpus': os.cpu_count(), 'openblas_threads': os.environ.get('OPENBLAS_NUM_THREADS'),
                'packages': {name: importlib.metadata.version(name) for name in ('fastembed','numpy','onnxruntime','huggingface-hub')}},
            'corpus': {'source': 'synthetic six-template Chinese text, not private data', 'min_chars': min(len(e.summary) for e in entries),
                'median_chars': statistics.median(len(e.summary) for e in entries), 'max_chars': max(len(e.summary) for e in entries),
                'normalization': 'exact float32 cosine; normalized cached passage matrix', 'all_current_companion': True},
            'seed_sqlite_ms': seed_ms, 'model_load_ms': model_load_ms, 'cold': cold, 'warm': warm,
            'warm_wall_p50_ms': statistics.median(r['wall_ms'] for r in warm), 'correction_write_ms': correction_write_ms,
            'correction': correction, 'forget_write_ms': forget_write_ms, 'forget': forgotten,
            'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
            'final_vector_bytes': sum(value.nbytes for value in retriever._vectors.values()),
            'final_matrix_cache_bytes': sum(value.nbytes for value in retriever._matrix_cache.values()),
            'assertions': 'cold N, warm 0, corrected 1, forgotten 0 passage encodes; revoked IDs absent'}
    finally:
        retriever.close()
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({'size': args.size, 'cold_ms': result['cold']['wall_ms'], 'warm_p50_ms': result['warm_wall_p50_ms'],
                  'corrected_encodes': result['correction']['status']['last_encoded_entries'],
                  'forget_encodes': result['forget']['status']['last_encoded_entries'], 'rss_mib': result['peak_rss_mib']}))
