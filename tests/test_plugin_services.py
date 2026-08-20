from __future__ import annotations

import json
from pathlib import Path

import pytest

from guanghe_companion.plugin_manifest import discover_plugin_candidates
from guanghe_companion.plugin_runtime import PluginLoadError, PluginRuntime


def _plugin(
    root: Path,
    plugin_id: str,
    source: str,
    *,
    dependencies: list[str] | None = None,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "emoti-plugin.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": plugin_id,
                "name": plugin_id,
                "version": "0.1.0",
                "api_version": "1",
                "entrypoint": "plugin.py:activate",
                "default_enabled": False,
                "permissions": ["services.register"],
                "dependencies": dependencies or [],
            }
        ),
        encoding="utf-8",
    )
    (root / "plugin.py").write_text(source, encoding="utf-8")


def test_service_definition_provider_consumer_seam(tmp_path: Path) -> None:
    collection = tmp_path / "plugins"
    _plugin(
        collection / "definition",
        "emoti.service.definition",
        """
from guanghe_companion.plugin_api import ServiceDefinition

def activate(ctx):
    ctx.define_service(ServiceDefinition(
        service_id='emoti.greeting', version='1', description='greeting seam',
        required_methods=('greet',)))
""",
    )
    _plugin(
        collection / "provider",
        "emoti.service.provider",
        """
from guanghe_companion.plugin_api import ServiceProviderDefinition

class Provider:
    def greet(self, name):
        return f'hello {name}'

def activate(ctx):
    ctx.register_service_provider(ServiceProviderDefinition(
        provider_id='emoti.greeting.local', service_id='emoti.greeting',
        provider=Provider(), priority=10))
""",
        dependencies=["emoti.service.definition"],
    )
    runtime = PluginRuntime(data_root=tmp_path / "data")
    runtime.load_all(
        discover_plugin_candidates([collection]),
        enabled_ids={"emoti.service.provider"},
    )

    provider = runtime.resolve_service("emoti.greeting")

    assert provider.greet("Xingxi") == "hello Xingxi"
    assert [item.provider_id for item in runtime.list_service_providers("emoti.greeting")] == [
        "emoti.greeting.local"
    ]


def test_service_provider_must_implement_required_methods(tmp_path: Path) -> None:
    collection = tmp_path / "plugins"
    _plugin(
        collection / "definition",
        "emoti.service.definition",
        """
from guanghe_companion.plugin_api import ServiceDefinition

def activate(ctx):
    ctx.define_service(ServiceDefinition(
        service_id='emoti.greeting', version='1', description='greeting seam',
        required_methods=('greet',)))
""",
    )
    _plugin(
        collection / "provider",
        "emoti.service.bad",
        """
from guanghe_companion.plugin_api import ServiceProviderDefinition

class BadProvider:
    pass

def activate(ctx):
    ctx.register_service_provider(ServiceProviderDefinition(
        provider_id='emoti.greeting.bad', service_id='emoti.greeting',
        provider=BadProvider()))
""",
        dependencies=["emoti.service.definition"],
    )
    runtime = PluginRuntime(data_root=tmp_path / "data")

    with pytest.raises(PluginLoadError, match="greet"):
        runtime.load_all(
            discover_plugin_candidates([collection]),
            enabled_ids={"emoti.service.bad"},
        )

    assert runtime.loaded_plugin_ids == ()


def test_highest_priority_provider_is_selected_and_unload_is_reversible(tmp_path: Path) -> None:
    collection = tmp_path / "plugins"
    _plugin(
        collection / "definition",
        "emoti.service.definition",
        """
from guanghe_companion.plugin_api import ServiceDefinition

def activate(ctx):
    ctx.define_service(ServiceDefinition(
        service_id='emoti.greeting', version='1', description='greeting seam',
        required_methods=('greet',)))
""",
    )
    for suffix, priority in (("low", 1), ("high", 20)):
        _plugin(
            collection / suffix,
            f"emoti.service.{suffix}",
            f"""
from guanghe_companion.plugin_api import ServiceProviderDefinition

class Provider:
    def greet(self, name):
        return '{suffix}'

def activate(ctx):
    ctx.register_service_provider(ServiceProviderDefinition(
        provider_id='emoti.greeting.{suffix}', service_id='emoti.greeting',
        provider=Provider(), priority={priority}))
""",
            dependencies=["emoti.service.definition"],
        )
    runtime = PluginRuntime(data_root=tmp_path / "data")
    runtime.load_all(
        discover_plugin_candidates([collection]),
        enabled_ids={"emoti.service.low", "emoti.service.high"},
    )

    assert runtime.resolve_service("emoti.greeting").greet("x") == "high"

    runtime.unload("emoti.service.high")
    assert runtime.resolve_service("emoti.greeting").greet("x") == "low"
