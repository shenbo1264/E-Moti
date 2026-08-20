from __future__ import annotations

from guanghe_companion.plugin_api import ServiceDefinition


SERVICES = (
    ServiceDefinition(
        service_id="emoti.llm.expression",
        version="1",
        description="Generate validated companion expression output from read-only context.",
        required_methods=("generate",),
    ),
    ServiceDefinition(
        service_id="emoti.voice.tts",
        version="1",
        description="Synthesize validated companion speech into audio.",
        required_methods=("synthesize",),
    ),
    ServiceDefinition(
        service_id="emoti.voice.asr",
        version="1",
        description="Transcribe user-authorized audio into player text.",
        required_methods=("transcribe",),
    ),
    ServiceDefinition(
        service_id="emoti.context.screen-summary",
        version="1",
        description="Produce a privacy-filtered, read-only summary for the current moment.",
        required_methods=("summarize",),
    ),
    ServiceDefinition(
        service_id="emoti.context.web-search",
        version="1",
        description="Return bounded public-search results for expression context.",
        required_methods=("search",),
    ),
)


def activate(ctx):
    for definition in SERVICES:
        ctx.define_service(definition)
