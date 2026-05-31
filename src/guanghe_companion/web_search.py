from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from .capability_settings import WebSearchSettings
from .expression_context import _sanitize_context_string

SearchAdapter = Callable[[str, int, int], Iterable[dict[str, object]]]


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    ok: bool
    message: str
    tool_results: list[dict[str, str]]


class WebSearchService:
    def __init__(self, adapter: SearchAdapter | None = None) -> None:
        self._adapter = adapter

    def search(self, query: str, settings: WebSearchSettings) -> WebSearchResult:
        if not settings.enabled:
            return WebSearchResult(False, "联网搜索未启用", [])
        sanitized_query = _sanitize_context_string(str(query), 80)
        if not sanitized_query:
            return WebSearchResult(False, "搜索词为空", [])
        adapter = self._adapter or _ddgs_adapter()
        if adapter is None:
            return WebSearchResult(False, "ddgs 未安装，无法执行联网搜索", [])
        try:
            raw_results = adapter(sanitized_query, settings.max_results, settings.timeout_seconds)
        except Exception as exc:
            return WebSearchResult(False, f"联网搜索失败：{exc}", [])
        tool_results = _sanitize_search_results(raw_results, settings.max_results)
        if not tool_results:
            return WebSearchResult(False, "联网搜索没有返回可用来源", [])
        return WebSearchResult(True, "搜索完成，结果已提供给星汐", tool_results)


def _ddgs_adapter() -> SearchAdapter | None:
    try:
        from ddgs import DDGS
    except ImportError:
        return None

    def run(query: str, max_results: int, timeout: int) -> Iterable[dict[str, object]]:
        with DDGS(timeout=timeout) as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    return run


def _sanitize_search_results(raw_results: Iterable[dict[str, object]], max_results: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for entry in raw_results:
        if not isinstance(entry, dict):
            continue
        title = _sanitize_context_string(str(entry.get("title") or ""), 80)
        summary = _sanitize_context_string(str(entry.get("body") or entry.get("summary") or ""), 180)
        url = _sanitize_context_string(str(entry.get("href") or entry.get("url") or ""), 240)
        if not title or not summary:
            continue
        item = {
            "source": "web_search",
            "title": title,
            "summary": summary,
            "timestamp": timestamp,
        }
        if url:
            item["url"] = url
        results.append(item)
        if len(results) >= max_results:
            break
    return results
