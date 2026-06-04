from guanghe_companion.capability_settings import WebSearchSettings
from guanghe_companion.character_inspiration import (
    CharacterInspirationService,
    FanworkPolicy,
)
from guanghe_companion.web_search import WebSearchService


def test_character_inspiration_builds_cited_original_brief_without_copying_source_name():
    prompts = []

    def fake_adapter(query, max_results, timeout):
        assert "Hatsune Miku" in query
        return [
            {
                "title": "Hatsune Miku profile",
                "body": "Known for teal twin tails, virtual idol concerts, and energetic songs.",
                "href": "https://example.test/miku",
            }
        ]

    def fake_llm(prompt):
        prompts.append(prompt)
        assert "只抽象特征" in prompt
        assert "不要复制角色名" in prompt
        return (
            '{"character_id":"teal_echo_companion","name":"Hatsune Miku",'
            '"title":"桌面回声同伴","description":"一个受虚拟舞台氛围启发的原创桌面伴侣。",'
            '"visual_keywords":["青绿色点缀","轻舞台感"],'
            '"personality_keywords":["活泼","清亮"],'
            '"boundaries":["不复制原角色名、发型、服装、台词或标志设定"]}'
        )

    service = CharacterInspirationService(
        search_service=WebSearchService(adapter=fake_adapter),
        settings=WebSearchSettings(enabled=True, max_results=1),
        brief_client=fake_llm,
    )

    result = service.build_original_inspiration("Hatsune Miku")

    assert result.ok is True
    assert result.source_notes[0]["url"] == "https://example.test/miku"
    assert result.brief["character_id"] == "teal_echo_companion"
    assert result.brief["name"] == "原创桌面同伴"
    assert "Hatsune Miku" not in result.brief["description"]
    assert result.policy == FanworkPolicy.ORIGINAL_INSPIRATION
    assert prompts


def test_character_inspiration_falls_back_to_rule_brief_when_llm_unavailable():
    service = CharacterInspirationService(
        search_service=WebSearchService(adapter=lambda query, max_results, timeout: []),
        settings=WebSearchSettings(enabled=True, max_results=1),
        brief_client=None,
    )

    result = service.build_original_inspiration("  ")

    assert result.ok is False
    assert result.brief == {}
    assert "搜索词为空" in result.message


def test_local_fanwork_policy_requires_user_authorization_without_searching():
    called = False

    def adapter(query, max_results, timeout):
        nonlocal called
        called = True
        return []

    service = CharacterInspirationService(
        search_service=WebSearchService(adapter=adapter),
        settings=WebSearchSettings(enabled=True),
    )

    result = service.describe_local_fanwork_policy("Hatsune Miku")

    assert result.ok is True
    assert result.policy == FanworkPolicy.LOCAL_FANWORK
    assert result.requires_user_authorization is True
    assert result.source_notes == ()
    assert called is False
