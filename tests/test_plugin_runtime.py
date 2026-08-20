from __future__ import annotations

import json
from pathlib import Path

import pytest

from guanghe_companion.plugin_api import (
    ActionRequest,
    PluginEvent,
    PluginPermission,
    SkillRequest,
)
from guanghe_companion.plugin_manifest import discover_plugin_candidates
from guanghe_companion.plugin_runtime import (
    PluginDependencyError,
    PluginLoadError,
    PluginPermissionError,
    PluginRuntime,
)


def _plugin(
    root: Path,
    plugin_id: str,
    source: str,
    *,
    permissions: tuple[str, ...] = (),
    dependencies: tuple[object, ...] = (),
    default_enabled: bool = False,
    settings: dict[str, object] | None = None,
) -> Path:
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
                "default_enabled": default_enabled,
                "permissions": list(permissions),
                "dependencies": list(dependencies),
                "settings": settings or {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "plugin.py").write_text(source, encoding="utf-8")
    return root


def _runtime(tmp_path: Path, **kwargs: object) -> PluginRuntime:
    return PluginRuntime(data_root=tmp_path / "plugin-data", **kwargs)


def test_load_and_unload_reverses_action_registration(tmp_path: Path) -> None:
    root = _plugin(
        tmp_path / "plugins" / "sample",
        "emoti.sample.action",
        """
from guanghe_companion.plugin_api import ActionDefinition, ActionResult

def activate(ctx):
    ctx.register_action(ActionDefinition(
        action_id='sample.wave',
        label='挥挥手',
        handler=lambda request: ActionResult(speech='星汐挥了挥手。', motion='Default'),
    ))
""",
        permissions=("actions.register",),
    )
    runtime = _runtime(tmp_path)
    candidate = discover_plugin_candidates([root])[0]

    runtime.load(candidate)
    assert [item.action_id for item in runtime.list_actions()] == ["sample.wave"]
    result = runtime.execute_action(ActionRequest(action_id="sample.wave", character_id="xingxi"))
    assert result.speech == "星汐挥了挥手。"

    runtime.unload("emoti.sample.action")
    assert runtime.list_actions() == ()


def test_partial_activation_failure_rolls_back_effects(tmp_path: Path) -> None:
    root = _plugin(
        tmp_path / "plugins" / "broken",
        "emoti.broken",
        """
from guanghe_companion.plugin_api import ActionDefinition, ActionResult

def activate(ctx):
    ctx.register_action(ActionDefinition(
        action_id='broken.temp',
        label='临时',
        handler=lambda request: ActionResult(speech='temp'),
    ))
    raise RuntimeError('activation exploded')
""",
        permissions=("actions.register",),
    )
    runtime = _runtime(tmp_path)

    with pytest.raises(PluginLoadError, match="activation exploded"):
        runtime.load(discover_plugin_candidates([root])[0])

    assert runtime.list_actions() == ()
    assert runtime.status("emoti.broken").state == "failed"


def test_required_dependencies_load_in_order(tmp_path: Path) -> None:
    collection = tmp_path / "plugins"
    _plugin(
        collection / "base",
        "emoti.base",
        "def activate(ctx):\n    ctx.storage.set('loaded', True)\n",
        permissions=("storage.local",),
    )
    _plugin(
        collection / "feature",
        "emoti.feature",
        "def activate(ctx):\n    ctx.storage.set('loaded', True)\n",
        permissions=("storage.local",),
        dependencies=("emoti.base",),
    )
    runtime = _runtime(tmp_path)

    loaded = runtime.load_all(discover_plugin_candidates([collection]), enabled_ids={"emoti.feature"})

    assert loaded == ("emoti.base", "emoti.feature")
    assert runtime.loaded_plugin_ids == ("emoti.base", "emoti.feature")


def test_missing_dependency_is_reported(tmp_path: Path) -> None:
    root = _plugin(
        tmp_path / "plugins" / "feature",
        "emoti.feature",
        "def activate(ctx):\n    pass\n",
        dependencies=("emoti.missing",),
    )
    runtime = _runtime(tmp_path)

    with pytest.raises(PluginDependencyError, match="emoti.missing"):
        runtime.load_all(discover_plugin_candidates([root]), enabled_ids={"emoti.feature"})


def test_dependency_cycle_is_reported(tmp_path: Path) -> None:
    collection = tmp_path / "plugins"
    _plugin(collection / "a", "emoti.a", "def activate(ctx):\n    pass\n", dependencies=("emoti.b",))
    _plugin(collection / "b", "emoti.b", "def activate(ctx):\n    pass\n", dependencies=("emoti.a",))
    runtime = _runtime(tmp_path)

    with pytest.raises(PluginDependencyError, match="cycle"):
        runtime.load_all(discover_plugin_candidates([collection]), enabled_ids={"emoti.a"})


def test_default_enabled_plugins_load_without_explicit_ids(tmp_path: Path) -> None:
    collection = tmp_path / "plugins"
    _plugin(collection / "on", "emoti.on", "def activate(ctx):\n    pass\n", default_enabled=True)
    _plugin(collection / "off", "emoti.off", "def activate(ctx):\n    pass\n", default_enabled=False)
    runtime = _runtime(tmp_path)

    loaded = runtime.load_all(discover_plugin_candidates([collection]))

    assert loaded == ("emoti.on",)


def test_sensitive_permission_requires_explicit_grant(tmp_path: Path) -> None:
    root = _plugin(
        tmp_path / "plugins" / "network",
        "emoti.network",
        "def activate(ctx):\n    ctx.require('network.http')\n",
        permissions=("network.http",),
    )
    candidate = discover_plugin_candidates([root])[0]

    with pytest.raises(PluginPermissionError, match="network.http"):
        _runtime(tmp_path).load(candidate)

    runtime = _runtime(
        tmp_path,
        permission_grants={"emoti.network": {PluginPermission.NETWORK_HTTP}},
    )
    runtime.load(candidate)
    assert runtime.status("emoti.network").state == "loaded"


def test_undeclared_permission_is_denied_even_if_granted(tmp_path: Path) -> None:
    root = _plugin(
        tmp_path / "plugins" / "network",
        "emoti.network",
        "def activate(ctx):\n    ctx.require('network.http')\n",
        permissions=(),
    )
    runtime = _runtime(
        tmp_path,
        permission_grants={"emoti.network": {PluginPermission.NETWORK_HTTP}},
    )

    with pytest.raises(PluginPermissionError, match="not declared"):
        runtime.load(discover_plugin_candidates([root])[0])


def test_plugin_storage_is_scoped_per_plugin(tmp_path: Path) -> None:
    collection = tmp_path / "plugins"
    source = "def activate(ctx):\n    ctx.storage.set('value', ctx.settings.get('value'))\n"
    _plugin(collection / "a", "emoti.a", source, permissions=("storage.local",), settings={"value": "A"})
    _plugin(collection / "b", "emoti.b", source, permissions=("storage.local",), settings={"value": "B"})
    runtime = _runtime(tmp_path)
    runtime.load_all(discover_plugin_candidates([collection]), enabled_ids={"emoti.a", "emoti.b"})

    assert runtime.plugin_storage("emoti.a").get("value") == "A"
    assert runtime.plugin_storage("emoti.b").get("value") == "B"
    assert runtime.plugin_storage("emoti.a").path != runtime.plugin_storage("emoti.b").path


def test_event_listener_failure_is_contained(tmp_path: Path) -> None:
    collection = tmp_path / "plugins"
    _plugin(
        collection / "bad",
        "emoti.listener.bad",
        "def activate(ctx):\n    ctx.on('companion.event.settled', lambda event: 1 / 0)\n",
        permissions=("events.subscribe",),
    )
    _plugin(
        collection / "good",
        "emoti.listener.good",
        "def activate(ctx):\n    ctx.on('companion.event.settled', lambda event: 'ok')\n",
        permissions=("events.subscribe",),
    )
    runtime = _runtime(tmp_path)
    runtime.load_all(discover_plugin_candidates([collection]), enabled_ids={"emoti.listener.bad", "emoti.listener.good"})

    report = runtime.emit(PluginEvent(event_type="companion.event.settled", payload={"kind": "touch"}))

    assert report.results == ("ok",)
    assert len(report.failures) == 1
    assert report.failures[0].plugin_id == "emoti.listener.bad"


def test_action_receives_read_only_state_snapshot(tmp_path: Path) -> None:
    root = _plugin(
        tmp_path / "plugins" / "immutable",
        "emoti.immutable",
        """
from guanghe_companion.plugin_api import ActionDefinition, ActionResult

def handler(request):
    request.state_snapshot['coins'] = 999
    return ActionResult(speech='bad')

def activate(ctx):
    ctx.register_action(ActionDefinition(action_id='immutable.test', label='test', handler=handler))
""",
        permissions=("actions.register",),
    )
    runtime = _runtime(tmp_path)
    runtime.load(discover_plugin_candidates([root])[0])

    with pytest.raises(PluginLoadError, match="read-only"):
        runtime.execute_action(
            ActionRequest(action_id="immutable.test", character_id="xingxi", state_snapshot={"coins": 20})
        )


def test_skill_execution_and_user_confirmation_metadata(tmp_path: Path) -> None:
    root = _plugin(
        tmp_path / "plugins" / "skill",
        "emoti.skill",
        """
from guanghe_companion.plugin_api import SkillDefinition, SkillResult

def activate(ctx):
    ctx.register_skill(SkillDefinition(
        skill_id='skill.local.chime',
        title='播放星铃',
        description='播放一声本地提示音',
        requires_confirmation=True,
        handler=lambda request: SkillResult(speech='叮。', payload={'played': True}),
    ))
""",
        permissions=("skills.register",),
    )
    runtime = _runtime(tmp_path)
    runtime.load(discover_plugin_candidates([root])[0])

    definition = runtime.list_skills()[0]
    result = runtime.execute_skill(SkillRequest(skill_id=definition.skill_id, character_id="xingxi", user_confirmed=True))

    assert definition.requires_confirmation is True
    assert result.payload["played"] is True



def test_skill_requiring_confirmation_cannot_run_without_current_confirmation(tmp_path: Path) -> None:
    root = _plugin(
        tmp_path / "plugins" / "skill-confirm",
        "emoti.skill.confirm",
        """
from guanghe_companion.plugin_api import SkillDefinition, SkillResult

def activate(ctx):
    ctx.register_skill(SkillDefinition(
        skill_id='skill.confirmed', title='确认技能', description='needs consent',
        requires_confirmation=True, handler=lambda request: SkillResult(speech='ran')))
""",
        permissions=("skills.register",),
    )
    runtime = _runtime(tmp_path)
    runtime.load(discover_plugin_candidates([root])[0])

    with pytest.raises(PluginPermissionError, match="confirmation"):
        runtime.execute_skill(SkillRequest(skill_id="skill.confirmed", character_id="xingxi"))


def test_context_sections_are_namespaced_and_ordered(tmp_path: Path) -> None:
    collection = tmp_path / "plugins"
    _plugin(
        collection / "late",
        "emoti.context.late",
        """
from guanghe_companion.plugin_api import ContextProviderDefinition

def activate(ctx):
    ctx.register_context_provider(ContextProviderDefinition(
        provider_id='late', order=20, provider=lambda request: {'value': 'late'}))
""",
        permissions=("context.provide",),
    )
    _plugin(
        collection / "early",
        "emoti.context.early",
        """
from guanghe_companion.plugin_api import ContextProviderDefinition

def activate(ctx):
    ctx.register_context_provider(ContextProviderDefinition(
        provider_id='early', order=10, provider=lambda request: {'value': 'early'}))
""",
        permissions=("context.provide",),
    )
    runtime = _runtime(tmp_path)
    runtime.load_all(discover_plugin_candidates([collection]), enabled_ids={"emoti.context.late", "emoti.context.early"})

    assembly = runtime.build_context(character_id="xingxi", query="hello", state_snapshot={})

    assert list(assembly.sections) == ["emoti.context.early:early", "emoti.context.late:late"]
    assert assembly.sections["emoti.context.early:early"]["value"] == "early"


def test_ui_panels_are_metadata_only_and_reversible(tmp_path: Path) -> None:
    root = _plugin(
        tmp_path / "plugins" / "ui",
        "emoti.ui",
        """
from guanghe_companion.plugin_api import UiPanelDefinition

def activate(ctx):
    ctx.register_ui_panel(UiPanelDefinition(
        panel_id='ui.star-map', title='星图', navigation_group='扩展', order=50,
        view_model=lambda request: {'stars': 3}))
""",
        permissions=("ui.register",),
    )
    runtime = _runtime(tmp_path)
    runtime.load(discover_plugin_candidates([root])[0])

    panels = runtime.list_ui_panels()
    assert panels[0].title == "星图"
    assert runtime.build_ui_panel_model("ui.star-map", character_id="xingxi") == {"stars": 3}

    runtime.unload("emoti.ui")
    assert runtime.list_ui_panels() == ()


def test_cannot_unload_dependency_while_dependent_is_loaded(tmp_path: Path) -> None:
    collection = tmp_path / "plugins"
    _plugin(collection / "base", "emoti.base", "def activate(ctx):\n    pass\n")
    _plugin(collection / "child", "emoti.child", "def activate(ctx):\n    pass\n", dependencies=("emoti.base",))
    runtime = _runtime(tmp_path)
    runtime.load_all(discover_plugin_candidates([collection]), enabled_ids={"emoti.child"})

    with pytest.raises(PluginDependencyError, match="emoti.child"):
        runtime.unload("emoti.base")

    runtime.unload("emoti.child")
    runtime.unload("emoti.base")
    assert runtime.loaded_plugin_ids == ()


def test_reload_replaces_module_and_registrations(tmp_path: Path) -> None:
    root = _plugin(
        tmp_path / "plugins" / "reload",
        "emoti.reload",
        """
from guanghe_companion.plugin_api import ActionDefinition, ActionResult

def activate(ctx):
    ctx.register_action(ActionDefinition(action_id='reload.action', label='v1', handler=lambda request: ActionResult(speech='v1')))
""",
        permissions=("actions.register",),
    )
    runtime = _runtime(tmp_path)
    candidate = discover_plugin_candidates([root])[0]
    runtime.load(candidate)
    assert runtime.execute_action(ActionRequest(action_id="reload.action", character_id="x")).speech == "v1"

    (root / "plugin.py").write_text(
        """
from guanghe_companion.plugin_api import ActionDefinition, ActionResult

def activate(ctx):
    ctx.register_action(ActionDefinition(action_id='reload.action', label='v2', handler=lambda request: ActionResult(speech='v2')))
""",
        encoding="utf-8",
    )
    runtime.reload("emoti.reload")

    assert runtime.execute_action(ActionRequest(action_id="reload.action", character_id="x")).speech == "v2"


def test_api_major_mismatch_is_rejected(tmp_path: Path) -> None:
    root = _plugin(tmp_path / "plugins" / "future", "emoti.future", "def activate(ctx):\n    pass\n")
    manifest_path = root / "emoti-plugin.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["api_version"] = "2"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PluginLoadError, match="API version"):
        _runtime(tmp_path).load(discover_plugin_candidates([root])[0])
