from pathlib import Path
from guanghe_companion.plugin_host import PluginHost, PluginPaths


def test_local_expression_fallback_loads_and_generates(tmp_path: Path):
    root=Path(__file__).resolve().parents[1]
    host=PluginHost(PluginPaths(root/'plugins',tmp_path/'installed',tmp_path/'config.json',tmp_path/'data'))
    report=host.start(); assert report.ok
    provider=host.runtime.resolve_service('emoti.llm.expression')
    assert provider is not None
    assert host.runtime.list_service_providers('emoti.llm.expression')[0].provider_id=='emoti.bundled.local-expression'
    result=provider.generate('我有点困')
    assert result['provider']=='local-expression-fallback' and result['events'][0]['speech']


def test_local_expression_fallback_is_reversible(tmp_path: Path):
    root=Path(__file__).resolve().parents[1]
    host=PluginHost(PluginPaths(root/'plugins',tmp_path/'installed',tmp_path/'config.json',tmp_path/'data')); host.start()
    host.runtime.unload('emoti.bundled.local-expression-fallback')
    import pytest
    with pytest.raises(Exception): host.runtime.resolve_service('emoti.llm.expression')
