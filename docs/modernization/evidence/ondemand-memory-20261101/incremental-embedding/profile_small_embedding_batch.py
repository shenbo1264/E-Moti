"""Real FastEmbed batch-size experiment; production files are unchanged."""
import json
from pathlib import Path
import runpy
import sys
from fastembed import TextEmbedding
original = TextEmbedding.passage_embed

def passage_embed(self, texts, **kwargs):
    kwargs['batch_size'] = 64
    return original(self, texts, **kwargs)

TextEmbedding.passage_embed = passage_embed
script = Path(__file__).with_name('profile_incremental_embeddings.py')
result = Path(__file__).with_name('incremental-embedding-batch64-300.json')
sys.argv = [str(script), '--source-root', '/workspace/scratch/ac4f72a6307d/development/E-Moti-ondemand-memory',
    '--model-cache', '/tmp/emoti-bge-model-cache', '--size', '300', '--output', str(result)]
runpy.run_path(str(script), run_name='__main__')
data = json.loads(result.read_text())
data['experiment'] = {'type': 'real_FastEmbed_batch_parameter_override', 'batch_size': 64,
                      'production_source_changed': False, 'not_a_quality_comparison': True}
result.write_text(json.dumps(data, ensure_ascii=False, indent=2))
