import json
from pathlib import Path
from guanghe_companion.plugin_api import ActionRequest
from guanghe_companion.plugin_subsystem import PluginSubsystem


def copy_bundled(tmp_path: Path):
    import shutil
    source=Path(__file__).resolve().parents[1]/'plugins'
    app=tmp_path/'app'; app.mkdir(); shutil.copytree(source,app/'plugins')
    return app


def flaky(root: Path):
    root.mkdir(parents=True)
    (root/'emoti-plugin.json').write_text(json.dumps({'schema_version':1,'id':'emoti.community.flaky','name':'Flaky','version':'0.1.0','api_version':'1','entrypoint':'plugin.py:activate','description':'flaky','default_enabled':False,'permissions':['actions.register'],'dependencies':[],'settings':{},'contributes':{'actions':['flaky.fail']}},indent=2),encoding='utf-8')
    (root/'plugin.py').write_text("from guanghe_companion.plugin_api import ActionDefinition\ndef activate(ctx):\n def fail(req): raise RuntimeError('boom')\n ctx.register_action(ActionDefinition(action_id='flaky.fail',label='fail',handler=fail))\n",encoding='utf-8')


def test_subsystem_starts_bundled_plugins(tmp_path: Path):
    subsystem=PluginSubsystem(application_root=copy_bundled(tmp_path),user_data_root=tmp_path/'user')
    report=subsystem.start(); assert report.ok and 'emoti.core.capability-contracts' in report.loaded_plugin_ids
    subsystem.shutdown()


def test_subsystem_quarantines_repeated_failure(tmp_path: Path):
    app=copy_bundled(tmp_path); installed=tmp_path/'user/plugins/installed/emoti.community.flaky'; flaky(installed)
    subsystem=PluginSubsystem(application_root=app,user_data_root=tmp_path/'user'); subsystem.start(); subsystem.host.set_enabled('emoti.community.flaky',True); subsystem.host.reload_from_disk()
    for _ in range(3): result=subsystem.execute_action(ActionRequest(action_id='flaky.fail',character_id='x'))
    assert not result.ok and result.quarantined and subsystem.health.status('emoti.community.flaky').quarantined
    assert 'emoti.core.capability-contracts' in subsystem.runtime.loaded_plugin_ids


def test_subsystem_journal_records_success(tmp_path: Path):
    subsystem=PluginSubsystem(application_root=copy_bundled(tmp_path),user_data_root=tmp_path/'user'); subsystem.start(); subsystem.host.set_enabled('emoti.bundled.stargazing',True); subsystem.host.reload_from_disk()
    result=subsystem.execute_action(ActionRequest(action_id='stargazing.watch',character_id='x'))
    assert result.ok and any(row['event_type']=='plugin.action.completed' for row in subsystem.journal.tail())


def test_subsystem_bind_host_provider(tmp_path: Path):
    from guanghe_companion.plugin_provider_adapters import ExpressionProviderAdapter
    subsystem=PluginSubsystem(application_root=copy_bundled(tmp_path),user_data_root=tmp_path/'user'); subsystem.start()
    subsystem.bind_host_capabilities(expression=ExpressionProviderAdapter(lambda p:'ok'))
    assert subsystem.runtime.resolve_service('emoti.llm.expression').generate('x')=='ok'
    assert subsystem.runtime.list_service_providers('emoti.llm.expression')[0].provider_id=='host.expression'
