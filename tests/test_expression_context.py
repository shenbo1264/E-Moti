from guanghe_companion.ai_expressor import ExpressionRequest
from guanghe_companion.character_pack import load_default_character_pack
from guanghe_companion.controller import CompanionController
from guanghe_companion.expression_context import (
    CharacterProfileExpressionContextProvider,
    ExpressionContextChain,
    ManualPerceptionExpressionContextProvider,
    MockSearchExpressionContextProvider,
)


def test_character_profile_expression_context_returns_local_tool_results_only():
    pack = load_default_character_pack()
    provider = CharacterProfileExpressionContextProvider(pack)

    context = provider()

    assert set(context) == {"tool_results"}
    assert context["tool_results"] == [
        {
            "source": "local_character_pack",
            "title": "星汐 | 桌面频率同伴",
            "summary": "一个住在桌面上的原创类人伴侣。她通过状态、动作和结构化事件来回应玩家。",
        },
        {
            "source": "local_character_pack",
            "title": "modes",
            "summary": "Glow: 情绪稳定且主动亲近。 / Calm: 频率平稳，适合日常互动。 / Frayed: 开始疲惫或分心，需要轻一点的陪伴。",
        },
    ]
    assert "perception_summary" not in context
    assert "inventory" not in str(context)
    assert "coins" not in str(context)


def test_mock_search_expression_context_returns_timestamped_tool_results_only():
    provider = MockSearchExpressionContextProvider(
        query="星汐 口吻",
        results=[
            {
                "title": "表达设定",
                "summary": "保持轻柔、短句、陪伴感。",
                "timestamp": "2026-05-19T12:00:00+08:00",
                "url": "https://example.invalid/profile",
                "coins": 999,
            },
            {
                "title": "空摘要会被忽略",
                "summary": "   ",
                "timestamp": "2026-05-19T12:01:00+08:00",
            },
        ],
    )

    context = provider()

    assert context == {
        "tool_results": [
            {
                "source": "mock_search",
                "title": "星汐 口吻: 表达设定",
                "summary": "保持轻柔、短句、陪伴感。",
                "timestamp": "2026-05-19T12:00:00+08:00",
            }
        ]
    }
    assert "url" not in str(context)
    assert "coins" not in str(context)


def test_mock_search_expression_context_bounds_result_fields():
    provider = MockSearchExpressionContextProvider(
        query="q" * 120,
        results=[
            {
                "title": "t" * 120,
                "summary": "s" * 260,
                "timestamp": "2026-05-19T12:00:00+08:00-extra-data",
            },
        ],
    )

    context = provider()

    assert context == {
        "tool_results": [
            {
                "source": "mock_search",
                "title": f"{'q' * 40}: {'t' * 38}",
                "summary": "s" * 180,
                "timestamp": "2026-05-19T12:00:00+08:00",
            }
        ]
    }


def test_mock_search_expression_context_flattens_control_characters():
    provider = MockSearchExpressionContextProvider(
        query="star\nsea",
        results=[
            {
                "title": "voice\tstyle",
                "summary": "gentle\nshort",
                "timestamp": "2026-05-19\n12:00",
            },
        ],
    )

    context = provider()

    assert context == {
        "tool_results": [
            {
                "source": "mock_search",
                "title": "star sea: voice style",
                "summary": "gentle short",
                "timestamp": "2026-05-19 12:00",
            }
        ]
    }


def test_mock_search_expression_context_bounds_combined_title():
    provider = MockSearchExpressionContextProvider(
        query="manual search query that is already pretty long",
        results=[
            {
                "title": "result title that should not make the combined title too long",
                "summary": "short summary",
                "timestamp": "2026-05-19T12:00:00+08:00",
            },
        ],
    )

    title = provider()["tool_results"][0]["title"]

    assert len(title) <= 80


def test_mock_search_expression_context_ignores_non_string_query():
    provider = MockSearchExpressionContextProvider(
        query=object(),
        results=[
            {
                "title": "expression style",
                "summary": "keep replies short and gentle",
                "timestamp": "2026-05-19T12:00:00+08:00",
            },
        ],
    )

    assert provider() == {}


def test_mock_search_expression_context_ignores_non_iterable_results():
    provider = MockSearchExpressionContextProvider(
        query="starsea voice",
        results=object(),
    )

    assert provider() == {}


def test_mock_search_expression_context_skips_non_mapping_results():
    provider = MockSearchExpressionContextProvider(
        query="starsea voice",
        results=[
            ["not", "a", "mapping"],
            {
                "title": "expression style",
                "summary": "keep replies short and gentle",
                "timestamp": "2026-05-19T12:00:00+08:00",
            },
        ],
    )

    context = provider()

    assert context == {
        "tool_results": [
            {
                "source": "mock_search",
                "title": "starsea voice: expression style",
                "summary": "keep replies short and gentle",
                "timestamp": "2026-05-19T12:00:00+08:00",
            }
        ]
    }


def test_manual_perception_context_is_disabled_by_default():
    provider = ManualPerceptionExpressionContextProvider(
        summary="current window: draft notes",
    )

    context = provider()

    assert context == {}


def test_manual_perception_context_returns_sanitized_summary_when_enabled():
    provider = ManualPerceptionExpressionContextProvider(
        summary="  current window: draft notes  ",
        enabled=True,
    )

    context = provider()

    assert context == {"perception_summary": "current window: draft notes"}


def test_manual_perception_context_flattens_control_characters_when_enabled():
    provider = ManualPerceptionExpressionContextProvider(
        summary="window title:\tDraft\napp: Notes",
        enabled=True,
    )

    context = provider()

    assert context == {"perception_summary": "window title: Draft app: Notes"}


def test_manual_perception_context_bounds_enabled_summary():
    long_summary = "x" * 320
    long_provider = ManualPerceptionExpressionContextProvider(summary=long_summary, enabled=True)
    invalid_provider = ManualPerceptionExpressionContextProvider(summary=object(), enabled=True)

    assert long_provider() == {"perception_summary": "x" * 240}
    assert invalid_provider() == {}


def test_controller_routes_character_profile_context_without_snapshot_shape_changes(tmp_path):
    captured = {}

    class CapturingExpressor:
        def express(self, snapshot, effect=None):
            captured["request"] = snapshot
            return []

    provider = CharacterProfileExpressionContextProvider(load_default_character_pack())
    controller = CompanionController(
        save_path=tmp_path / "save.json",
        auto_load=False,
        ai_expressor=CapturingExpressor(),
        expression_context_provider=provider,
    )

    snapshot = controller.perform_action("touch")

    request = captured["request"]
    assert isinstance(request, ExpressionRequest)
    assert request.tool_results[0]["source"] == "local_character_pack"
    assert request.tool_results[0]["title"] == "星汐 | 桌面频率同伴"
    assert request.perception_summary == ""
    assert "tool_results" not in snapshot
    assert "perception_summary" not in snapshot
    assert snapshot["mood"] == 62


def test_expression_context_chain_merges_readonly_provider_outputs():
    chain = ExpressionContextChain(
        [
            lambda: {
                "perception_summary": "window: writing notes",
                "tool_results": [
                    {"source": "local", "title": "profile", "summary": "gentle voice"},
                ],
                "coins": 999,
            },
            lambda: {
                "perception_summary": "tool: profile loaded",
                "tool_results": [
                    {"source": "memory", "title": "recent", "summary": "touch happened"},
                ],
                "inventory": {"warm_milk": 99},
            },
        ]
    )

    context = chain()

    assert context == {
        "perception_summary": "window: writing notes tool: profile loaded",
        "tool_results": [
            {"source": "local", "title": "profile", "summary": "gentle voice"},
            {"source": "memory", "title": "recent", "summary": "touch happened"},
        ],
    }


def test_expression_context_chain_flattens_merged_perception_separator():
    chain = ExpressionContextChain(
        [
            lambda: {"perception_summary": "window: writing notes"},
            lambda: {"perception_summary": "tool: profile loaded"},
        ]
    )

    context = chain()

    assert context["perception_summary"] == "window: writing notes tool: profile loaded"
    assert "\n" not in context["perception_summary"]


def test_expression_context_chain_sanitizes_and_caps_tool_results():
    chain = ExpressionContextChain(
        [
            lambda: {
                "tool_results": [
                    {
                        "source": "local",
                        "title": "profile",
                        "summary": "gentle voice",
                        "timestamp": "2026-05-19T12:00:00+08:00",
                        "coins": 999,
                    },
                    {"source": "bad", "title": "missing summary"},
                ],
            },
            lambda: {
                "tool_results": [
                    {"source": "search", "title": "one", "summary": "first", "url": "https://example.invalid/1"},
                    {"source": "search", "title": "two", "summary": "second"},
                    {"source": "search", "title": "overflow", "summary": "ignored after cap"},
                ],
            },
        ]
    )

    context = chain()

    assert context == {
        "tool_results": [
            {
                "source": "local",
                "title": "profile",
                "summary": "gentle voice",
                "timestamp": "2026-05-19T12:00:00+08:00",
            },
            {"source": "search", "title": "one", "summary": "first"},
            {"source": "search", "title": "two", "summary": "second"},
        ]
    }
    assert "coins" not in str(context)
    assert "url" not in str(context)
    assert "overflow" not in str(context)


def test_expression_context_chain_bounds_tool_result_fields():
    chain = ExpressionContextChain(
        [
            lambda: {
                "tool_results": [
                    {
                        "source": "s" * 90,
                        "title": "t" * 120,
                        "summary": "m" * 260,
                        "timestamp": "2026-05-19T12:00:00+08:00-extra-data",
                    },
                ],
            },
        ]
    )

    context = chain()

    assert context == {
        "tool_results": [
            {
                "source": "s" * 60,
                "title": "t" * 80,
                "summary": "m" * 180,
                "timestamp": "2026-05-19T12:00:00+08:00",
            },
        ]
    }


def test_expression_context_chain_flattens_tool_result_control_characters():
    chain = ExpressionContextChain(
        [
            lambda: {
                "tool_results": [
                    {
                        "source": "mock\nsearch",
                        "title": "title\twith tab",
                        "summary": "summary\nwith newline",
                        "timestamp": "2026-05-19\n12:00",
                    },
                ],
            },
        ]
    )

    context = chain()

    assert context == {
        "tool_results": [
            {
                "source": "mock search",
                "title": "title with tab",
                "summary": "summary with newline",
                "timestamp": "2026-05-19 12:00",
            }
        ]
    }


def test_expression_context_chain_keeps_later_perception_after_tool_result_cap():
    chain = ExpressionContextChain(
        [
            lambda: {
                "tool_results": [
                    {"source": "search", "title": "one", "summary": "first"},
                    {"source": "search", "title": "two", "summary": "second"},
                    {"source": "search", "title": "three", "summary": "third"},
                ],
            },
            lambda: {
                "perception_summary": "manual screen note",
                "tool_results": [
                    {"source": "search", "title": "overflow", "summary": "ignored after cap"},
                ],
            },
        ]
    )

    context = chain()

    assert context["perception_summary"] == "manual screen note"
    assert [entry["title"] for entry in context["tool_results"]] == ["one", "two", "three"]
    assert "overflow" not in str(context)


def test_expression_context_chain_bounds_merged_perception_summary():
    chain = ExpressionContextChain(
        [
            lambda: {"perception_summary": "x" * 320},
            lambda: {"perception_summary": "ignored after cap"},
        ]
    )

    context = chain()

    assert context == {"perception_summary": "x" * 240}


def test_expression_context_chain_ignores_failed_or_invalid_providers():
    def failing_provider():
        raise RuntimeError("offline")

    chain = ExpressionContextChain(
        [
            failing_provider,
            lambda: ["not a dict"],
            lambda: {
                "perception_summary": "manual context",
                "tool_results": [
                    {"source": "local", "title": "safe", "summary": "still available"},
                ],
            },
        ]
    )

    assert chain() == {
        "perception_summary": "manual context",
        "tool_results": [
            {"source": "local", "title": "safe", "summary": "still available"},
        ],
    }


def test_expression_context_chain_can_reuse_one_shot_provider_iterables():
    providers = (
        provider
        for provider in [
            lambda: {"perception_summary": "manual screen note"},
            lambda: {
                "tool_results": [
                    {"source": "local", "title": "profile", "summary": "gentle voice"},
                ]
            },
        ]
    )
    chain = ExpressionContextChain(providers)

    first_context = chain()
    second_context = chain()

    assert first_context == {
        "perception_summary": "manual screen note",
        "tool_results": [
            {"source": "local", "title": "profile", "summary": "gentle voice"},
        ],
    }
    assert second_context == first_context
