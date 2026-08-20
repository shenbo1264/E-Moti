from pathlib import Path
from guanghe_companion.plugin_health import PluginHealthStore


def test_health_failure_quarantines_after_three(tmp_path: Path):
    store=PluginHealthStore(tmp_path/'health.json')
    assert not store.record_failure('p',RuntimeError('one'),now=1).quarantined
    assert not store.record_failure('p',RuntimeError('two'),now=2).quarantined
    status=store.record_failure('p',RuntimeError('three'),now=3)
    assert status.quarantined and status.consecutive_failures==3


def test_health_success_resets_failure_count(tmp_path: Path):
    store=PluginHealthStore(tmp_path/'health.json'); store.record_failure('p','bad',now=1)
    status=store.record_success('p',now=2)
    assert status.consecutive_failures==0 and status.last_success_at==2


def test_health_persists_and_clears_quarantine(tmp_path: Path):
    path=tmp_path/'health.json'; store=PluginHealthStore(path,quarantine_threshold=1); store.record_failure('p','bad',now=1)
    restored=PluginHealthStore(path,quarantine_threshold=1); assert restored.status('p').quarantined
    assert not restored.clear_quarantine('p').quarantined


def test_health_remove(tmp_path: Path):
    store=PluginHealthStore(tmp_path/'health.json'); store.record_failure('p','bad'); store.remove('p')
    assert store.status('p').consecutive_failures==0
