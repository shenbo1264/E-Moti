from guanghe_companion.ai_expressor import ExpressionRequest
from guanghe_companion.character_pack import load_default_character_pack
from guanghe_companion.controller import CompanionController
from guanghe_companion.expression_context import CharacterProfileExpressionContextProvider


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
