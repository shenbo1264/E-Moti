from __future__ import annotations

from guanghe_companion.plugin_api import ServiceProviderDefinition


class LocalExpressionProvider:
    def __init__(self, default_line: str) -> None:
        self.default_line = default_line

    def generate(self, prompt: str) -> dict[str, object]:
        text = self.default_line
        lowered = str(prompt).lower()
        if "sleep" in lowered or "困" in str(prompt):
            text = "唔……先歇一会儿也没关系。我在桌角等你。"
        elif "gift" in lowered or "礼物" in str(prompt):
            text = "给、给我的？那我就好好收下了。"
        return {
            "provider": "local-expression-fallback",
            "events": [
                {
                    "type": "speech",
                    "speech": text,
                    "effect": "ATTENTION",
                    "motion_hint": "Default",
                    "intent_hint": "stay_quiet"
                }
            ]
        }


def activate(ctx):
    ctx.register_service_provider(
        ServiceProviderDefinition(
            provider_id="emoti.bundled.local-expression",
            service_id="emoti.llm.expression",
            provider=LocalExpressionProvider(str(ctx.settings.get("default_line", "我在这里。"))),
            priority=-100,
            description="Offline deterministic expression fallback",
        )
    )
