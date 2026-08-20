from pathlib import Path
from dataclasses import dataclass
from guanghe_companion.plugin_api import ServiceDefinition
from guanghe_companion.plugin_provider_adapters import (
    ASRProviderAdapter, ExpressionProviderAdapter, ScreenSummaryProviderAdapter,
    TTSProviderAdapter, WebSearchProviderAdapter, register_host_capability_providers,
)
from guanghe_companion.plugin_runtime import PluginRuntime


def definitions(runtime):
    for service_id, methods in (
        ('emoti.llm.expression',('generate',)),('emoti.voice.tts',('synthesize',)),('emoti.voice.asr',('transcribe',)),('emoti.context.screen-summary',('summarize',)),('emoti.context.web-search',('search',))
    ):
        runtime._service_definitions.register(owner_id='test',contribution_id=service_id,value=ServiceDefinition(service_id=service_id,version='1',description='test',required_methods=methods))


def test_adapters_delegate():
    assert ExpressionProviderAdapter(lambda p:p+'!').generate('x')=='x!'
    assert TTSProviderAdapter(lambda text:{'text':text}).synthesize('hi')=={'text':'hi'}
    assert ASRProviderAdapter(lambda audio:len(audio)).transcribe(b'12')==2
    assert ScreenSummaryProviderAdapter(lambda:'screen').summarize()=='screen'
    assert WebSearchProviderAdapter(lambda q:[{"title": q}]).search('x')==[{"title": "x"}]


def test_host_provider_is_registered_with_priority(tmp_path: Path):
    runtime=PluginRuntime(data_root=tmp_path/'data'); definitions(runtime)
    handles=register_host_capability_providers(runtime,expression=ExpressionProviderAdapter(lambda p:'host'))
    provider=runtime.resolve_service('emoti.llm.expression')
    assert provider.generate('x')=='host'
    assert runtime.list_service_providers('emoti.llm.expression')[0].provider_id=='host.expression'
    handles[0].dispose()
    import pytest
    with pytest.raises(Exception): runtime.resolve_service('emoti.llm.expression')


def test_invalid_provider_contract_is_rejected(tmp_path: Path):
    runtime=PluginRuntime(data_root=tmp_path/'data'); definitions(runtime)
    try:
        register_host_capability_providers(runtime,expression=object())
    except Exception as exc:
        assert 'does not implement' in str(exc)
    else:
        raise AssertionError('expected contract failure')


def test_screen_and_search_adapters_return_read_only_sanitized_values():
    @dataclass
    class ScreenResult:
        ok: bool
        message: str
        summary: str

    @dataclass
    class SearchResult:
        ok: bool
        message: str
        tool_results: list[dict[str, str]]

    screen_settings = object()
    search_settings = object()
    screen = ScreenSummaryProviderAdapter(
        lambda settings: ScreenResult(True, "ok", "用户在编辑文档。"),
        settings_provider=lambda: screen_settings,
    )
    search = WebSearchProviderAdapter(
        lambda query, settings: SearchResult(
            True,
            "ok",
            [{"source": "web_search", "title": query, "summary": "安全来源卡"}],
        ),
        settings_provider=lambda: search_settings,
    )

    assert screen.summarize() == "用户在编辑文档。"
    assert search.search("桌宠") == [
        {"source": "web_search", "title": "桌宠", "summary": "安全来源卡"}
    ]
