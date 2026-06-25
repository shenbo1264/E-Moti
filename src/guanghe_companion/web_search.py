from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from .capability_settings import WebSearchSettings
from .expression_context import _sanitize_context_string

SearchAdapter = Callable[[str, int, int], Iterable[dict[str, object]]]
SEARCH_FETCH_MULTIPLIER = 3
MAX_SEARCH_FETCH_RESULTS = 10
SEARCH_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+#.-]{1,}|[\u4e00-\u9fff]{2,}")
SEARCH_STOP_WORDS = {
    "about",
    "and",
    "for",
    "from",
    "into",
    "news",
    "search",
    "the",
    "with",
}
LOW_QUALITY_RESULT_TERMS = {
    "บาคาร่า",
    "betting",
    "casino",
    "escort",
    "gambling",
    "jackpot",
    "lottery",
    "porn",
    "slots",
    "贷款",
}


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
        fetch_limit = _search_fetch_limit(settings.max_results)
        try:
            raw_results = adapter(sanitized_query, fetch_limit, settings.timeout_seconds)
        except Exception as exc:
            return WebSearchResult(False, f"联网搜索失败：{exc}", [])
        tool_results = _sanitize_search_results(raw_results, settings.max_results, query=sanitized_query)
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


def _sanitize_search_results(
    raw_results: Iterable[dict[str, object]],
    max_results: int,
    *,
    query: str = "",
) -> list[dict[str, str]]:
    candidates: list[tuple[int, int, dict[str, str]]] = []
    query_terms = _meaningful_query_terms(query)
    require_relevance = len(query_terms) >= 3
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for index, entry in enumerate(raw_results):
        if not isinstance(entry, dict):
            continue
        title = _sanitize_context_string(str(entry.get("title") or ""), 80)
        summary = _sanitize_context_string(str(entry.get("body") or entry.get("summary") or ""), 180)
        url = _sanitize_context_string(str(entry.get("href") or entry.get("url") or ""), 240)
        if not title or not summary:
            continue
        if _is_low_quality_result(title=title, summary=summary, url=url):
            continue
        relevance = _search_relevance_score(title=title, summary=summary, url=url, query_terms=query_terms)
        if require_relevance and relevance <= 0:
            continue
        item = {
            "source": "web_search",
            "title": title,
            "summary": summary,
            "timestamp": timestamp,
        }
        if url:
            item["url"] = url
        candidates.append((relevance, index, item))
    if query_terms:
        candidates.sort(key=lambda candidate: (-candidate[0], candidate[1]))
    return [item for _, _, item in candidates[:max_results]]


def _search_fetch_limit(max_results: int) -> int:
    return min(MAX_SEARCH_FETCH_RESULTS, max(max_results, max_results * SEARCH_FETCH_MULTIPLIER))


def _meaningful_query_terms(query: str) -> set[str]:
    terms: set[str] = set()
    for match in SEARCH_TOKEN_PATTERN.finditer(query.lower()):
        term = match.group(0).strip(".-")
        if len(term) < 2 or term in SEARCH_STOP_WORDS:
            continue
        terms.add(term)
    return terms


def _is_low_quality_result(*, title: str, summary: str, url: str) -> bool:
    combined = f"{title} {summary} {url}".lower()
    if any(term in combined for term in LOW_QUALITY_RESULT_TERMS):
        return True
    if not url:
        return False
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.scheme not in {"http", "https"})


def _search_relevance_score(*, title: str, summary: str, url: str, query_terms: set[str]) -> int:
    if not query_terms:
        return 0
    title_text = title.lower()
    summary_text = summary.lower()
    url_text = url.lower()
    score = 0
    for term in query_terms:
        if term in title_text:
            score += 3
        if term in summary_text:
            score += 1
        if term in url_text:
            score += 1
    return score
