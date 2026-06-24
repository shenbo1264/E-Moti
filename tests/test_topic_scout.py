from __future__ import annotations


def test_topic_scout_builds_safe_query_and_permission_topic_cards():
    from guanghe_companion.capability_settings import WebSearchSettings
    from guanghe_companion.topic_scout import TopicScout
    from guanghe_companion.web_search import WebSearchResult

    class FakeSearchService:
        def __init__(self):
            self.calls = []

        def search(self, query, settings):
            self.calls.append((query, settings))
            return WebSearchResult(
                ok=True,
                message="ok",
                tool_results=[
                    {
                        "source": "web_search",
                        "title": "Anime desktop pet trend",
                        "summary": "Players want small companions that react to mood.",
                        "timestamp": "2026-06-24T12:00:00Z",
                        "url": "https://example.invalid/topic",
                    },
                    {
                        "source": "web_search",
                        "title": "Virtual companion memory",
                        "summary": "Users dislike generic chatbot replies.",
                    },
                ],
            )

    settings = WebSearchSettings(enabled=True, max_results=3, timeout_seconds=7)
    context = {
        "recent_dialogue": [
            {"role": "user", "speaker": "player", "text": "I want anime pet news\nand memes"},
        ],
        "long_term_memory": [
            {"category": "interest", "summary": "likes AI companions", "source": "profile"},
        ],
    }
    service = FakeSearchService()

    result = TopicScout(search_service=service).scout(
        context=context,
        settings=settings,
        interests=["desktop pet"],
    )

    assert result.ok is True
    assert service.calls == [("desktop pet I want anime pet news and memes likes AI companions", settings)]
    assert result.cards == [
        {
            "source": "web_search",
            "title": "Anime desktop pet trend",
            "summary": "Players want small companions that react to mood.",
            "timestamp": "2026-06-24T12:00:00Z",
            "opening_line": "我刚看到一个关于 Anime desktop pet trend 的小话题，要听听吗？",
        },
        {
            "source": "web_search",
            "title": "Virtual companion memory",
            "summary": "Users dislike generic chatbot replies.",
            "opening_line": "我刚看到一个关于 Virtual companion memory 的小话题，要听听吗？",
        },
    ]
    assert "url" not in str(result.cards)


def test_topic_scout_returns_clear_skip_without_search_signal():
    from guanghe_companion.capability_settings import WebSearchSettings
    from guanghe_companion.topic_scout import TopicScout

    class FailingIfCalledSearchService:
        def search(self, query, settings):
            raise AssertionError("search should not be called")

    result = TopicScout(search_service=FailingIfCalledSearchService()).scout(
        context={"recent_dialogue": []},
        settings=WebSearchSettings(enabled=True),
    )

    assert result.ok is False
    assert result.reason == "empty_query"
    assert result.cards == []


def test_topic_scout_bounds_results_and_sanitizes_opening_lines():
    from guanghe_companion.capability_settings import WebSearchSettings
    from guanghe_companion.topic_scout import TopicScout
    from guanghe_companion.web_search import WebSearchResult

    class FakeSearchService:
        def search(self, query, settings):
            return WebSearchResult(
                ok=True,
                message="ok",
                tool_results=[
                    {
                        "source": "web_search",
                        "title": f"title\n{index}",
                        "summary": "summary\ttext",
                    }
                    for index in range(5)
                ],
            )

    result = TopicScout(search_service=FakeSearchService()).scout(
        context={"recent_dialogue": [{"role": "user", "speaker": "player", "text": "AI news"}]},
        settings=WebSearchSettings(enabled=True, max_results=5),
    )

    assert result.ok is True
    assert len(result.cards) == 3
    assert [card["title"] for card in result.cards] == ["title 0", "title 1", "title 2"]
    assert "\n" not in str(result.cards)
    assert "\t" not in str(result.cards)
