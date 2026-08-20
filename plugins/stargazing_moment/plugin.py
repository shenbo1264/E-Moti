from __future__ import annotations

from guanghe_companion.plugin_api import (
    ActionDefinition,
    ActionResult,
    ContextProviderDefinition,
    MemoryProposal,
    MemoryRuleDefinition,
    PluginEvent,
    UiPanelDefinition,
)


def activate(ctx):
    def watch_stars(request):
        count = int(ctx.storage.get("count", 0)) + 1
        ctx.storage.set("count", count)
        speech = str(ctx.settings.get("speech", "一起看了一会儿星星。"))
        return ActionResult(
            speech=speech,
            motion="Default",
            payload={"count": count},
            events=(
                PluginEvent(
                    event_type="plugin.emoti.bundled.stargazing.completed",
                    character_id=request.character_id,
                    occurred_at=request.now,
                    durable=True,
                    payload={"count": count, "summary": speech},
                ),
            ),
        )

    def remember_first_time(event):
        if event.event_type != "plugin.emoti.bundled.stargazing.completed":
            return ()
        count = int(event.payload.get("count", 0))
        return (
            MemoryProposal(
                proposal_id=f"{ctx.plugin_id}:first-stargazing",
                kind="共同日常",
                title="第一次一起看星星",
                summary=str(event.payload.get("summary", "一起看了一会儿星星。")),
                source=f"plugin:{ctx.plugin_id}",
                source_ids=(event.event_id,),
                tags=("第一次", "共同日常", "星星"),
                importance=0.82,
                metadata={"plugin_id": ctx.plugin_id, "count": count},
            ),
        )

    ctx.register_action(
        ActionDefinition(
            action_id="stargazing.watch",
            label="一起看星星",
            description="在桌角留出一小段安静的共同时间。",
            handler=watch_stars,
        )
    )
    ctx.register_memory_rule(
        MemoryRuleDefinition(
            rule_id="stargazing.first-memory",
            handler=remember_first_time,
        )
    )
    ctx.register_context_provider(
        ContextProviderDefinition(
            provider_id="stargazing.status",
            order=30,
            provider=lambda request: {
                "times": int(ctx.storage.get("count", 0)),
                "available": True,
            },
        )
    )
    ctx.register_ui_panel(
        UiPanelDefinition(
            panel_id="stargazing.panel",
            title="星图角落",
            navigation_group="扩展",
            order=40,
            description="展示这项互动的本地次数和纪念状态。",
            view_model=lambda request: {
                "times": int(ctx.storage.get("count", 0)),
                "empty_copy": "今晚还没有一起看过星星。",
            },
        )
    )
