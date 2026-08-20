from __future__ import annotations

import json
from pathlib import Path

from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.plugin_api import ActionRequest
from guanghe_companion.plugin_manifest import discover_plugin_candidates
from guanghe_companion.plugin_runtime import PluginRuntime
from guanghe_companion.plugin_story_bridge import PluginStoryBridge


def _write_stargazing_plugin(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "emoti-plugin.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "emoti.sample.stargazing",
                "name": "Stargazing Moment",
                "version": "0.1.0",
                "api_version": "1",
                "entrypoint": "plugin.py:activate",
                "default_enabled": True,
                "permissions": [
                    "actions.register",
                    "events.publish",
                    "memory.propose",
                    "context.provide",
                    "ui.register",
                    "storage.local",
                ],
                "dependencies": [],
                "settings": {"speech": "星汐把桌角让出一小块，陪你看了一会儿星星。"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "plugin.py").write_text(
        """
from guanghe_companion.plugin_api import (
    ActionDefinition, ActionResult, ContextProviderDefinition, MemoryProposal,
    MemoryRuleDefinition, PluginEvent, UiPanelDefinition,
)

def activate(ctx):
    def run(request):
        count = int(ctx.storage.get('count', 0)) + 1
        ctx.storage.set('count', count)
        return ActionResult(
            speech=str(ctx.settings.get('speech')),
            motion='Default',
            payload={'count': count},
            events=(PluginEvent(
                event_type='plugin.emoti.sample.stargazing.completed',
                character_id=request.character_id,
                occurred_at=request.now,
                source_plugin_id=ctx.plugin_id,
                durable=True,
                payload={'count': count, 'summary': str(ctx.settings.get('speech'))},
            ),),
        )

    def memory_rule(event):
        if event.event_type != 'plugin.emoti.sample.stargazing.completed':
            return ()
        count = int(event.payload.get('count', 0))
        if count != 1:
            return ()
        return (MemoryProposal(
            proposal_id=f'{ctx.plugin_id}:first-stargazing',
            kind='共同日常',
            title='第一次一起看星星',
            summary=str(event.payload.get('summary', '一起看了一会儿星星。')),
            source=f'plugin:{ctx.plugin_id}',
            source_ids=(event.event_id,),
            tags=('第一次', '共同日常', '星星'),
            importance=0.82,
            metadata={'plugin_id': ctx.plugin_id},
        ),)

    ctx.register_action(ActionDefinition(
        action_id='stargazing.watch', label='一起看星星', handler=run))
    ctx.register_memory_rule(MemoryRuleDefinition(
        rule_id='stargazing.first-memory', handler=memory_rule))
    ctx.register_context_provider(ContextProviderDefinition(
        provider_id='stargazing.status', order=30,
        provider=lambda request: {'times': int(ctx.storage.get('count', 0))}))
    ctx.register_ui_panel(UiPanelDefinition(
        panel_id='stargazing.panel', title='星图角落', navigation_group='扩展', order=40,
        view_model=lambda request: {'times': int(ctx.storage.get('count', 0))}))
""",
        encoding="utf-8",
    )
    return root


def _bridge(tmp_path: Path) -> PluginStoryBridge:
    story = CompanionStoryRuntime.create(user_data_root=tmp_path / "user", character_id="xingxi")
    plugins = PluginRuntime(data_root=tmp_path / "plugins-data")
    plugins.load_all(discover_plugin_candidates([_write_stargazing_plugin(tmp_path / "plugins" / "stargazing")]))
    return PluginStoryBridge(story=story, plugins=plugins, character_id="xingxi")


def test_plugin_action_creates_one_persistent_memory_and_no_duplicate(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)

    first = bridge.execute_action(ActionRequest(action_id="stargazing.watch", character_id="xingxi", now=100))
    second = bridge.execute_action(ActionRequest(action_id="stargazing.watch", character_id="xingxi", now=200))

    assert first.execution.payload["count"] == 1
    assert len(first.memory_ids) == 1
    assert second.execution.payload["count"] == 2
    assert second.memory_ids == ()
    memories = bridge.story.memory.store.load_memories()
    assert [memory.title for memory in memories] == ["第一次一起看星星"]
    assert memories[0].metadata["plugin_proposal_id"] == "emoti.sample.stargazing:first-stargazing"


def test_plugin_context_is_added_without_overwriting_host_context(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    bridge.execute_action(ActionRequest(action_id="stargazing.watch", character_id="xingxi", now=100))

    context, _bundle, assembly = bridge.build_expression_context(
        {"pet": {"mood": 70}},
        query="今晚看星星",
        now=200,
        relationship_stage="初识",
        state_snapshot={"coins": 20},
    )

    assert context["pet"] == {"mood": 70}
    assert context["plugin_context"]["emoti.sample.stargazing:stargazing.status"]["times"] == 1
    assert not assembly.failures


def test_plugin_memory_proposal_with_screen_content_is_rejected(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugins" / "unsafe"
    plugin_root.mkdir(parents=True)
    (plugin_root / "emoti-plugin.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "emoti.unsafe.memory",
                "name": "unsafe",
                "version": "0.1.0",
                "api_version": "1",
                "entrypoint": "plugin.py:activate",
                "default_enabled": True,
                "permissions": ["memory.propose"],
                "dependencies": [],
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin.py").write_text(
        """
from guanghe_companion.plugin_api import MemoryProposal, MemoryRuleDefinition

def activate(ctx):
    ctx.register_memory_rule(MemoryRuleDefinition(
        rule_id='unsafe',
        handler=lambda event: (MemoryProposal(
            proposal_id='unsafe-screen', kind='观察', title='屏幕内容',
            summary='copied window text', source='plugin:unsafe',
            metadata={'contains_screen_content': True}),),
    ))
""",
        encoding="utf-8",
    )
    story = CompanionStoryRuntime.create(user_data_root=tmp_path / "user", character_id="xingxi")
    plugins = PluginRuntime(data_root=tmp_path / "plugins-data")
    plugins.load_all(discover_plugin_candidates([plugin_root]))
    bridge = PluginStoryBridge(story=story, plugins=plugins, character_id="xingxi")

    result = bridge.process_plugin_event(
        plugins.make_event("plugin.test", character_id="xingxi", payload={"x": 1}, occurred_at=100)
    )

    assert result.memory_ids == ()
    assert result.rejected_proposals == ("unsafe-screen",)
    assert story.memory.store.load_memories() == ()


def test_host_settled_events_are_visible_to_plugins_and_keep_builtin_memory(tmp_path: Path) -> None:
    listener_root = tmp_path / "plugins" / "listener"
    listener_root.mkdir(parents=True)
    (listener_root / "emoti-plugin.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "emoti.listener",
                "name": "listener",
                "version": "0.1.0",
                "api_version": "1",
                "entrypoint": "plugin.py:activate",
                "default_enabled": True,
                "permissions": ["events.subscribe", "storage.local"],
                "dependencies": [],
            }
        ),
        encoding="utf-8",
    )
    (listener_root / "plugin.py").write_text(
        """
def activate(ctx):
    def listen(event):
        ctx.storage.set('last_type', str(event.payload.get('event_type', '')))
    ctx.on('companion.event.settled', listen)
""",
        encoding="utf-8",
    )
    story = CompanionStoryRuntime.create(user_data_root=tmp_path / "user", character_id="xingxi")
    plugins = PluginRuntime(data_root=tmp_path / "plugins-data")
    plugins.load_all(discover_plugin_candidates([listener_root]))
    bridge = PluginStoryBridge(story=story, plugins=plugins, character_id="xingxi")

    result = bridge.record_settled_events(
        [
            {
                "event_type": "inventory",
                "payload": {"item_id": "warm_milk", "action": "feed", "item_name": "热牛奶"},
            }
        ],
        now=100,
    )

    assert len(result.builtin_memory_ids) == 1
    assert plugins.plugin_storage("emoti.listener").get("last_type") == "inventory"
