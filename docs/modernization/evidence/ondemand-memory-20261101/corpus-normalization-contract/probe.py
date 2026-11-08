import importlib.util,json,sys
from pathlib import Path
source=Path(sys.argv[1]); tool=Path(sys.argv[2]); sys.path.insert(0,str(source/'src'))
spec=importlib.util.spec_from_file_location('evaluation',tool); ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
from guanghe_companion.emotional_memory import EmotionalMemoryEntry
row={'id':'typed','story_id':'s','kind':'用户事实','title':'纸张配置','summary':'用户纸张配置为grid，边距是0。','source':'user_chat','source_ids':['user-statement'],'occurred_at':1,'created_at':1,'updated_at':1,'metadata':{'fact_subject':'user:self','fact_value':{'layout':'grid','margin':0}}}
data={'owner_id':'owner','character_id':'character','memories':[row]}
inputs=ev.make_input_rows(data,'s',3); entries=ev.make_entries(data,'s',3,EmotionalMemoryEntry,input_rows=inputs)
print(json.dumps({'source_root':str(source),**ev.corpus_provenance(inputs,entries)},ensure_ascii=False))
