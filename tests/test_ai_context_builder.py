from __future__ import annotations


def test_ai_context_builder_bounds_and_sanitizes_readonly_payload():
    from guanghe_companion.ai_context_builder import AIContextBuilder
    from guanghe_companion.dialogue_history import DialogueHistoryEntry

    dialogue = [
        DialogueHistoryEntry(role="user", speaker="player", text=f"turn {index}\ntext")
        for index in range(7)
    ]
    long_term_memory = [
        {
            "category": f"cat-{index}",
            "summary": f"summary\t{index}",
            "source": "local_memory",
            "coins": 999,
        }
        for index in range(6)
    ]
    tool_results = [
        {
            "source": "web_search",
            "title": f"title {index}",
            "summary": f"summary\n{index}",
            "timestamp": "2026-06-24T12:00:00Z",
            "url": "https://example.invalid/private",
            "screenshot": "data:image/png;base64,unsafe",
            "coins": 999,
        }
        for index in range(4)
    ]

    payload = AIContextBuilder(
        dialogue_history=dialogue,
        long_term_memory=long_term_memory,
        perception_summary="  screen:\tIDE\npytest passed  ",
        tool_results=tool_results,
    ).build()

    assert set(payload) == {"recent_dialogue", "long_term_memory", "perception_summary", "tool_results"}
    assert [entry["text"] for entry in payload["recent_dialogue"]] == [
        "turn 2 text",
        "turn 3 text",
        "turn 4 text",
        "turn 5 text",
        "turn 6 text",
    ]
    assert len(payload["long_term_memory"]) == 5
    assert payload["long_term_memory"][0] == {
        "category": "cat-0",
        "summary": "summary 0",
        "source": "local_memory",
    }
    assert payload["perception_summary"] == "screen: IDE pytest passed"
    assert [entry["title"] for entry in payload["tool_results"]] == ["title 0", "title 1", "title 2"]
    assert "summary 0" in payload["tool_results"][0]["summary"]
    assert "\n" not in str(payload)
    assert "\t" not in str(payload)
    assert "data:image" not in str(payload)
    assert "url" not in str(payload)
    assert "coins" not in str(payload)


def test_ai_context_builder_ignores_invalid_rows_and_empty_values():
    from guanghe_companion.ai_context_builder import build_ai_context_payload

    payload = build_ai_context_payload(
        dialogue_history=[
            {"role": "bad", "speaker": "player", "text": "ignored"},
            {"role": "assistant", "speaker": "xingxi", "text": " kept "},
            ["not", "a", "mapping"],
        ],
        long_term_memory=[
            {"category": "profile", "summary": "", "source": "local"},
            {"category": "taste", "summary": "likes quiet chat", "source": "local"},
        ],
        perception_summary=object(),
        tool_results=[
            {"source": "web_search", "title": "topic", "summary": ""},
            {"source": "topic_scout", "title": "anime news", "summary": "short", "opening_line": "听一个话题吗？"},
        ],
    )

    assert payload == {
        "recent_dialogue": [
            {"role": "assistant", "speaker": "xingxi", "text": "kept"},
        ],
        "long_term_memory": [
            {"category": "taste", "summary": "likes quiet chat", "source": "local"},
        ],
        "tool_results": [
            {
                "source": "topic_scout",
                "title": "anime news",
                "summary": "short",
                "opening_line": "听一个话题吗？",
            }
        ],
    }
