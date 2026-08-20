from __future__ import annotations

"""Adapters that expose existing E-Moti capabilities through plugin service seams."""

from dataclasses import dataclass
from collections.abc import Mapping
from typing import Callable

from .plugin_api import ServiceProviderDefinition
from .plugin_runtime import PluginRuntime, RegistrationHandle
from .expression_context import _sanitize_perception_summary


@dataclass(slots=True)
class ExpressionProviderAdapter:
    callback: Callable[[str], object]
    def generate(self, prompt: str) -> object:
        return self.callback(prompt)


@dataclass(slots=True)
class TTSProviderAdapter:
    callback: Callable[..., object]
    settings_provider: Callable[[], object] | None = None
    def synthesize(self, text: str, settings: object = None) -> object:
        effective = settings if settings is not None else _provided_settings(self.settings_provider)
        return self.callback(text, effective) if effective is not None else self.callback(text)


@dataclass(slots=True)
class ASRProviderAdapter:
    callback: Callable[..., object]
    settings_provider: Callable[[], object] | None = None
    def transcribe(self, audio: bytes, settings: object = None) -> object:
        effective = settings if settings is not None else _provided_settings(self.settings_provider)
        return self.callback(audio, effective) if effective is not None else self.callback(audio)


@dataclass(slots=True)
class ScreenSummaryProviderAdapter:
    callback: Callable[..., object]
    settings_provider: Callable[[], object] | None = None
    def summarize(self, settings: object = None) -> object:
        effective = settings if settings is not None else _provided_settings(self.settings_provider)
        result = self.callback(effective) if effective is not None else self.callback()
        if isinstance(result, str):
            return _sanitize_perception_summary(result)
        if getattr(result, "ok", True) is False:
            return ""
        return _sanitize_perception_summary(str(getattr(result, "summary", "")))


@dataclass(slots=True)
class WebSearchProviderAdapter:
    callback: Callable[..., object]
    settings_provider: Callable[[], object] | None = None
    def search(self, query: str, settings: object = None) -> object:
        effective = settings if settings is not None else _provided_settings(self.settings_provider)
        result = self.callback(query, effective) if effective is not None else self.callback(query)
        rows = getattr(result, "tool_results", result)
        if getattr(result, "ok", True) is False or not isinstance(rows, list):
            return []
        return [dict(row) for row in rows if isinstance(row, Mapping)]


def _provided_settings(provider: Callable[[], object] | None) -> object | None:
    return provider() if provider is not None else None


def register_host_capability_providers(
    runtime: PluginRuntime,
    *,
    expression: object | None = None,
    tts: object | None = None,
    asr: object | None = None,
    screen_summary: object | None = None,
    web_search: object | None = None,
    priority: int = 1000,
) -> tuple[RegistrationHandle, ...]:
    rows = (
        ("host.expression", "emoti.llm.expression", expression),
        ("host.tts", "emoti.voice.tts", tts),
        ("host.asr", "emoti.voice.asr", asr),
        ("host.screen-summary", "emoti.context.screen-summary", screen_summary),
        ("host.web-search", "emoti.context.web-search", web_search),
    )
    handles: list[RegistrationHandle] = []
    for provider_id, service_id, provider in rows:
        if provider is None:
            continue
        handles.append(
            runtime.register_host_service_provider(
                ServiceProviderDefinition(
                    provider_id=provider_id,
                    service_id=service_id,
                    provider=provider,
                    priority=priority,
                    description="E-Moti host capability adapter",
                )
            )
        )
    return tuple(handles)
