from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile

from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.plugin_api import ActionRequest
from guanghe_companion.plugin_center_controller import PluginCenterController
from guanghe_companion.plugin_package import build_plugin_archive
from guanghe_companion.plugin_provider_adapters import ExpressionProviderAdapter
from guanghe_companion.plugin_story_bridge import PluginStoryBridge
from guanghe_companion.plugin_subsystem import PluginSubsystem


def _write_plugin(root: Path, plugin_id: str, *, action_id: str, source: str, default_enabled: bool=False):
    root.mkdir(parents=True,exist_ok=True)
    (root/'emoti-plugin.json').write_text(json.dumps({
        'schema_version':1,'id':plugin_id,'name':plugin_id,'version':'0.1.0','api_version':'1','entrypoint':'plugin.py:activate','description':'smoke plugin','default_enabled':default_enabled,'permissions':['actions.register'],'dependencies':[],'settings':{},'contributes':{'actions':[action_id]}
    },indent=2),encoding='utf-8')
    (root/'plugin.py').write_text(source,encoding='utf-8')
    (root/'README.md').write_text('# smoke\n',encoding='utf-8')


def main(argv=None):
    parser=argparse.ArgumentParser(); parser.add_argument('--report',type=Path,required=True); args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='emoti-plugin-v2-smoke-') as tmp:
        tmp=Path(tmp); fake=tmp/'app'; fake.mkdir(); shutil.copytree((root/'plugins').resolve(), fake/'plugins')
        user=tmp/'user'; subsystem=PluginSubsystem(application_root=fake,user_data_root=user); boot=subsystem.start()
        center=PluginCenterController(subsystem)
        center.set_enabled('emoti.bundled.stargazing',True)
        story=CompanionStoryRuntime.create(user_data_root=tmp/'story',character_id='xingxi_pixel_pet')
        bridge=PluginStoryBridge(story,subsystem.runtime,'xingxi_pixel_pet')
        first=bridge.execute_action(ActionRequest(action_id='stargazing.watch',character_id='xingxi_pixel_pet',now=100,state_snapshot={}))
        second=bridge.execute_action(ActionRequest(action_id='stargazing.watch',character_id='xingxi_pixel_pet',now=200,state_snapshot={}))
        context=subsystem.runtime.build_context(character_id='xingxi_pixel_pet',query='星星',now=200,state_snapshot={})

        # Host provider must outrank the bundled offline fallback.
        subsystem.bind_host_capabilities(expression=ExpressionProviderAdapter(lambda prompt:{'provider':'host'}))
        provider=subsystem.runtime.resolve_service('emoti.llm.expression')
        host_preferred=provider.generate('smoke').get('provider')=='host' and subsystem.runtime.list_service_providers('emoti.llm.expression')[0].provider_id=='host.expression'

        # Package, install, enable, execute, disable and uninstall a community plugin.
        source_root=tmp/'community-source'
        _write_plugin(source_root,'emoti.community.greeting',action_id='community.greet',source="""from guanghe_companion.plugin_api import ActionDefinition, ActionResult\ndef activate(ctx):\n    ctx.register_action(ActionDefinition(action_id='community.greet',label='打招呼',handler=lambda req: ActionResult(speech='星汐朝你挥了挥手。',motion='Raised')))\n""")
        archive=tmp/'community-plugin.zip'; package=build_plugin_archive(source_root,archive); archive_built=archive.exists()
        install=subsystem.install(archive); center=PluginCenterController(subsystem); enable=center.set_enabled('emoti.community.greeting',True)
        community=subsystem.execute_action(ActionRequest(action_id='community.greet',character_id='xingxi_pixel_pet',now=300,state_snapshot={}))
        disable=center.set_enabled('emoti.community.greeting',False); uninstall=center.uninstall('emoti.community.greeting')

        # Three consecutive failures quarantine one plugin without taking down the host.
        flaky=user/'plugins'/'installed'/'emoti.community.flaky'
        _write_plugin(flaky,'emoti.community.flaky',action_id='flaky.fail',source="""from guanghe_companion.plugin_api import ActionDefinition\ndef activate(ctx):\n    def fail(req): raise RuntimeError('deliberate smoke failure')\n    ctx.register_action(ActionDefinition(action_id='flaky.fail',label='失败测试',handler=fail))\n""")
        subsystem.host.reload_from_disk(); center=PluginCenterController(subsystem); center.set_enabled('emoti.community.flaky',True)
        failures=[]
        for _ in range(3): failures.append(subsystem.execute_action(ActionRequest(action_id='flaky.fail',character_id='xingxi_pixel_pet',now=400,state_snapshot={})))
        flaky_status=subsystem.health.status('emoti.community.flaky')

        subsystem.journal.append('test.redaction',plugin_id='smoke',payload={'api_key':'private-value-must-not-leak','status':'ok'})
        journal_text=json.dumps(subsystem.journal.tail(20),ensure_ascii=False)
        catalog=PluginCenterController(subsystem).snapshot()
        subsystem.shutdown()

    checks={
        'boot_ok':boot.ok,'stargazing_first_memory':len(first.memory_ids)==1,'stargazing_repeat_deduplicated':len(second.memory_ids)==0,
        'stargazing_context_count':bool(context.sections),'host_provider_preferred':host_preferred,
        'community_archive_built':archive_built,'community_install_ok':install.ok,'community_enable_ok':enable.ok,
        'community_action_ok':community.ok and getattr(community.value,'speech','')=='星汐朝你挥了挥手。','community_disable_ok':disable.ok,'community_uninstall_ok':uninstall.ok,
        'flaky_failed_three_times':all(not row.ok for row in failures),'flaky_quarantined':flaky_status.quarantined,
        'host_survived_flaky_plugin':len(catalog.get('plugins',[]))>=3,
        'journal_redacted':'private-value-must-not-leak' not in journal_text and '[REDACTED]' in journal_text,
        'catalog_available':bool(catalog.get('plugins')),
    }
    payload={'ok':all(checks.values()),'checks':checks,'boot':boot.to_dict(),'community_package':package.to_dict(),'community_install':install.to_dict(),'flaky_status':flaky_status.to_dict(),'catalog':catalog,'private_data_in_report':False}
    args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps(payload,ensure_ascii=True,indent=2,sort_keys=True)+'\n',encoding='ascii')
    print(json.dumps(payload,ensure_ascii=False,indent=2)); return 0 if payload['ok'] else 1
if __name__=='__main__': raise SystemExit(main())
