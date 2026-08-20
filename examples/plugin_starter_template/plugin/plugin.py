from guanghe_companion.plugin_api import ActionDefinition, ActionResult


def activate(ctx):
    ctx.register_action(
        ActionDefinition(
            action_id="community.wave",
            label="挥挥手",
            description="一个不修改养成状态的本地互动。",
            handler=lambda request: ActionResult(
                speech=str(ctx.settings.get("speech", "星汐朝你挥了挥手。")),
                motion="Raised",
            ),
        )
    )
