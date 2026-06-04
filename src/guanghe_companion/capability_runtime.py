from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from .capability_settings import CapabilitySettings
from .dialogue import DialogueRequest
from .screen_observation import ScreenObservationResult, ScreenObservationService
from .voice_asr import ASRResult, ASRService
from .voice_tts import TTSManager, TTSResult
from .web_search import WebSearchResult, WebSearchService


@dataclass(frozen=True, slots=True)
class WebSearchRuntimeResult:
    ok: bool
    message: str
    tool_results: list[dict[str, str]]
    display_text: str


@dataclass(frozen=True, slots=True)
class ASRRuntimeResult:
    ok: bool
    message: str
    text: str = ""
    dialogue_request: DialogueRequest | None = None


T = TypeVar("T")
ServiceRef = T | Callable[[], T]


@dataclass(slots=True)
class CapabilityRuntime:
    settings_saver: Callable[[], CapabilitySettings] = CapabilitySettings.default
    settings_reader: Callable[[], CapabilitySettings] = CapabilitySettings.default
    set_perception_summary: Callable[[str], None] = lambda summary: None
    set_tool_results: Callable[[list[dict[str, object]]], None] = lambda results: None
    screen_observation_service: ServiceRef[ScreenObservationService] | None = None
    web_search_service: ServiceRef[WebSearchService] | None = None
    tts_manager: ServiceRef[TTSManager] | None = None
    asr_service: ServiceRef[ASRService] | None = None

    def run_screen_observation(self) -> ScreenObservationResult:
        settings = self.settings_saver()
        result = self._screen_observation_service().observe(settings.screen_observation)
        if result.summary:
            self.set_perception_summary(result.summary)
        return result

    def run_web_search(self, query: str) -> WebSearchRuntimeResult:
        settings = self.settings_saver()
        result = self._web_search_service().search(query, settings.web_search)
        if result.tool_results:
            self.set_tool_results(result.tool_results)
        return WebSearchRuntimeResult(
            ok=result.ok,
            message=result.message,
            tool_results=result.tool_results,
            display_text=_format_web_search_display(result),
        )

    def run_tts_test(self, text: str) -> TTSResult:
        settings = self.settings_saver()
        return self._tts_manager().speak(text, settings.tts)

    def speak_text(self, text: str) -> TTSResult:
        settings = self.settings_reader()
        return self._tts_manager().speak(text, settings.tts)

    def stop_tts(self) -> TTSResult:
        settings = self.settings_reader()
        return self._tts_manager().stop(settings.tts)

    def start_asr(self) -> ASRResult:
        settings = self.settings_saver()
        return self._asr_service().start_recording(settings.asr)

    def stop_asr(self) -> ASRRuntimeResult:
        settings = self.settings_saver()
        result = self._asr_service().stop_and_transcribe(settings.asr)
        dialogue_request = None
        if result.text and settings.asr.auto_send:
            dialogue_request = DialogueRequest(text=result.text, source="asr")
        return ASRRuntimeResult(
            ok=result.ok,
            message=result.message,
            text=result.text,
            dialogue_request=dialogue_request,
        )

    def _screen_observation_service(self) -> ScreenObservationService:
        return _resolve_service(self.screen_observation_service, ScreenObservationService)

    def _web_search_service(self) -> WebSearchService:
        return _resolve_service(self.web_search_service, WebSearchService)

    def _tts_manager(self) -> TTSManager:
        return _resolve_service(self.tts_manager, TTSManager)

    def _asr_service(self) -> ASRService:
        return _resolve_service(self.asr_service, ASRService)


def _format_web_search_display(result: WebSearchResult) -> str:
    if not result.tool_results:
        return result.message
    lines = [result.message]
    for item in result.tool_results:
        title = item.get("title", "")
        summary = item.get("summary", "")
        url = item.get("url", "")
        lines.append(f"{title} - {summary}" + (f" ({url})" if url else ""))
    return "\n".join(lines)


def _resolve_service(service: ServiceRef[T] | None, factory: Callable[[], T]) -> T:
    if service is None:
        return factory()
    if callable(service) and not hasattr(service, "__dataclass_fields__"):
        return service()
    return service
