from pathlib import Path
from guanghe_companion.plugin_journal import PluginJournal, redact


def test_journal_redacts_secrets(tmp_path: Path):
    journal=PluginJournal(tmp_path/'journal.jsonl')
    journal.append('x',plugin_id='p',payload={'api_key':'private','nested':{'token':'secret','ok':1}},now=1)
    text=(tmp_path/'journal.jsonl').read_text()
    assert 'private' not in text and 'secret' not in text and '[REDACTED]' in text


def test_journal_tail_and_clear(tmp_path: Path):
    journal=PluginJournal(tmp_path/'journal.jsonl')
    for i in range(4): journal.append('event',payload={'i':i},now=i)
    rows=journal.tail(2); assert [r['payload']['i'] for r in rows]==[2,3]
    journal.clear(); assert journal.tail()==()


def test_redact_handles_lists_and_unknown_objects():
    value=redact({'authorization':'Bearer abc','rows':[{'password':'x'},object()]})
    assert value['authorization']=='[REDACTED]' and value['rows'][0]['password']=='[REDACTED]'
