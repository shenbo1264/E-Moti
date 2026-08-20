from __future__ import annotations

import json
from pathlib import Path
from string import Formatter

from guanghe_companion.character_local_copy import load_character_local_copy
from guanghe_companion.focus_companion import FocusCompanionCopy

ASSET_DIR = Path(__file__).parents[1] / "assets" / "companion" / "xingxi_pixel_pet"

AI_SYSTEM_PHRASES = (
    "检测到",
    "根据当前",
    "建议你",
    "当前状态",
    "处理该任务",
    "节奏稳住",
    "作为AI",
    "作为 AI",
    "本次先暂停提醒",
)
MANIPULATIVE_PHRASES = (
    "你都不理我",
    "我会伤心",
    "不许离开",
    "必须陪我",
    "都是因为你",
)
EXPECTED_FIELDS = {
    "dialogue_ack": {"text"},
    "purchase": {"item_name"},
    "feed": {"item_name"},
    "gift": {"item_name"},
    "use": {"item_name"},
    "proactive_context_topic": {"topic"},
}


def _fields(template: str) -> set[str]:
    return {field_name for _, field_name, _, _ in Formatter().parse(template) if field_name}


def test_dialogue_style_is_valid_and_preserves_runtime_placeholders() -> None:
    payload = json.loads((ASSET_DIR / "dialogue_style.json").read_text(encoding="utf-8"))
    local_copy = payload["local_copy"]

    for key, expected in EXPECTED_FIELDS.items():
        assert _fields(local_copy[key]) == expected

    assert 12 <= len(local_copy) <= 40
    assert "口癖" in payload["fallback_style"]
    assert "系统口吻" in payload["fallback_style"]


def test_product_copy_avoids_ai_notification_and_emotional_coercion() -> None:
    payload = json.loads((ASSET_DIR / "dialogue_style.json").read_text(encoding="utf-8"))
    text = "\n".join(payload["local_copy"].values())

    for phrase in AI_SYSTEM_PHRASES + MANIPULATIVE_PHRASES:
        assert phrase not in text


def test_product_copy_has_character_voice_without_overloading_every_line() -> None:
    payload = json.loads((ASSET_DIR / "dialogue_style.json").read_text(encoding="utf-8"))
    lines = tuple(payload["local_copy"].values())
    markers = ("唔", "欸", "哼哼", "……", "锵锵", "～")
    marked = sum(any(marker in line for marker in markers) for line in lines)

    assert marked >= 7
    assert marked < len(lines)  # not every line needs to perform cuteness
    assert all(len(line) <= 80 for line in lines)


def test_current_upstream_character_local_copy_loader_formats_new_templates() -> None:
    copy = load_character_local_copy(ASSET_DIR)

    assert copy.line("feed", item_name="热牛奶") == "热牛奶收到——唔，好吃。能量槽正在偷偷上涨。"
    assert "角色设定" in copy.line("proactive_context_topic", topic="角色设定")
    assert "{item_name}" not in copy.line("purchase", item_name="星形发夹")


def test_focus_copy_is_pet_voice_not_article_or_system_copy() -> None:
    copy = FocusCompanionCopy()
    samples = (
        copy.offer("写代码", 52, 5),
        copy.offer("写作 / 文档处理", 52, 5),
        copy.break_started(5),
        copy.snoozed(),
        copy.muted_today(),
        copy.completed(),
        copy.cancelled(),
    )
    joined = "\n".join(samples)

    assert "陪我" in samples[0]
    assert "检测到" not in joined
    assert "建议" not in joined
    assert all(phrase not in joined for phrase in MANIPULATIVE_PHRASES)


def test_character_tts_direction_explicitly_rejects_assistant_voice() -> None:
    payload = json.loads((ASSET_DIR / "character.json").read_text(encoding="utf-8"))
    instruct = payload["tts_profile"]["instruct"]

    assert "customer-service assistant" in instruct
    assert "productivity coach" in instruct
    assert "tiny celestial desktop pet" in instruct


def test_llm_dialogue_policy_patch_separates_pet_voice_from_assistant_voice() -> None:
    policy_path = Path(__file__).parents[1] / "src" / "guanghe_companion" / "companion_dialogue_policy.py"
    source = policy_path.read_text(encoding="utf-8")

    assert "anime-game character voice" in source
    assert "唔、欸、哼哼" in source
    assert "Avoid assistant-like wording" in source
    assert "Never use guilt" in source
    assert "公众号" not in source


def test_current_upstream_performance_profile_reads_character_voice_contract() -> None:
    from guanghe_companion.character_performance_profile import load_character_performance_profile

    profile = load_character_performance_profile(ASSET_DIR)

    assert profile.character_name == "星汐"
    assert "微害羞" in profile.speech_style
    assert "系统通知" in profile.speech_style
    assert any("关系压力" in claim for claim in profile.forbidden_claims)
    assert "confused" in profile.allowed_expression_ids
    assert "ConfusedShy" in profile.preferred_motion_ids
