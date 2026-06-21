from __future__ import annotations

from guanghe_companion.capability_settings import WebSearchSettings


def test_fake_web_search_results_are_sanitized():
    from guanghe_companion.web_search import WebSearchService

    def fake_adapter(query, max_results, timeout):
        assert query == "星汐 demo"
        assert max_results == 2
        assert timeout == 9
        return [
            {
                "title": "  标题\n一  ",
                "body": "摘要\t内容" * 40,
                "href": "https://example.test/a",
            },
            {"title": "标题二", "body": "摘要二", "href": "https://example.test/b"},
        ]

    service = WebSearchService(adapter=fake_adapter)
    result = service.search("  星汐 demo  ", WebSearchSettings(enabled=True, max_results=2, timeout_seconds=9))

    assert result.ok is True
    assert len(result.tool_results) == 2
    assert result.tool_results[0]["source"] == "web_search"
    assert result.tool_results[0]["title"] == "标题 一"
    assert len(result.tool_results[0]["summary"]) <= 180
    assert result.tool_results[0]["url"] == "https://example.test/a"


def test_web_search_disabled_and_dependency_missing_are_explicit(monkeypatch):
    import guanghe_companion.web_search as web_search
    from guanghe_companion.web_search import WebSearchService

    disabled = WebSearchService(adapter=lambda query, max_results, timeout: []).search(
        "query", WebSearchSettings(enabled=False)
    )
    monkeypatch.setattr(web_search, "_ddgs_adapter", lambda: None)
    missing = WebSearchService(adapter=None).search("query", WebSearchSettings(enabled=True))

    assert disabled.ok is False
    assert "未启用" in disabled.message
    assert missing.ok is False
    assert "ddgs" in missing.message


def test_web_search_empty_or_failed_results_return_clear_message():
    from guanghe_companion.web_search import WebSearchService

    empty = WebSearchService(adapter=lambda query, max_results, timeout: []).search(
        "query", WebSearchSettings(enabled=True)
    )

    def failing_adapter(query, max_results, timeout):
        raise RuntimeError("network down")

    failed = WebSearchService(adapter=failing_adapter).search("query", WebSearchSettings(enabled=True))

    assert empty.ok is False
    assert "没有返回可用来源" in empty.message
    assert failed.ok is False
    assert "network down" in failed.message
