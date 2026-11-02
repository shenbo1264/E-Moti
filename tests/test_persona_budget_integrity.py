"""Actual request/prompt regression tests; no model or user saves are used."""
from copy import deepcopy
from dataclasses import asdict, replace
import json

import pytest

from guanghe_companion.character_pack import load_default_character_pack
from guanghe_companion.engine import create_initial_state
from guanghe_companion.expression_clients import MAX_OPENAI_PROMPT_LENGTH
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_prompt_budget import fit_prompt
from guanghe_companion.expression_refinement import build_refinement_prompt
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.persona import build_persona_payload


CORE_FIELDS = (
    "schema_version", "character_id", "character_name", "title", "description",
    "speech_style", "boundaries", "identity_version", "config_hash",
)


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _persona(tmp_path, char="字"):
    config = {
        "schema_version": 1,
        "identity_version": "author-v2",
        "traits": [f"T{i:02}" + char * 157 for i in range(12)],
        "preferences": [f"P{i:02}" + char * 157 for i in range(12)],
        "interaction_habits": [f"H{i:02}" + char * 157 for i in range(12)],
        "boundaries": [f"B{i:02}" + char * 157 for i in range(12)],
    }
    (tmp_path / "persona.json").write_text(_json(config), encoding="utf-8")
    result = build_persona_payload(load_default_character_pack(), pack_dir=tmp_path)
    assert result["validation_warnings"] == []
    return result


def _request(persona, **context):
    return ExpressionRequest.from_snapshot(
        asdict(create_initial_state()),
        context={"persona": persona, "player_message": "我们聊聊今天的事情。", **context},
    )


@pytest.mark.parametrize("char", ["中", "🙂"])
@pytest.mark.parametrize("reverse_order", [False, True])
def test_legal_max_lists_keep_all_identity_and_boundaries(tmp_path, char, reverse_order):
    persona = _persona(tmp_path, char)
    original = deepcopy(persona)
    if reverse_order:
        persona = dict(reversed(list(persona.items())))

    request = _request(persona)

    assert len(_json(request.persona)) <= 5000
    for field in CORE_FIELDS:
        assert request.persona[field] == original[field]
    # The hash still identifies the full authored configuration, not a newly
    # invented identity based on whichever optional list items fit this turn.
    assert request.persona["config_hash"] == original["config_hash"]
    assert any(len(request.persona[key]) < 12 for key in ("traits", "preferences", "interaction_habits"))
    assert persona == original


def test_soft_field_trimming_is_independent_of_payload_key_order(tmp_path):
    persona = _persona(tmp_path)

    forward = _request(persona).persona
    reverse = _request(dict(reversed(list(persona.items())))).persona

    assert forward == reverse


def test_short_existing_persona_is_unchanged():
    persona = build_persona_payload(load_default_character_pack())

    assert _request(persona).persona == persona


def test_legal_escaped_core_over_budget_fails_instead_of_removing_boundaries(tmp_path):
    # These fields satisfy PersonaProfile's length and file-size limits.
    # JSON escaping can still make the required identity exceed 5000 chars.
    config = {
        "schema_version": 1,
        "identity_version": "quoted-v1",
        "speech_style": '"' * 500,
        "boundaries": [f"{i:02}" + '"' * 158 for i in range(12)],
    }
    (tmp_path / "persona.json").write_text(_json(config), encoding="utf-8")
    pack = replace(load_default_character_pack(), description="\\" * 500)
    persona = build_persona_payload(pack, pack_dir=tmp_path)
    assert persona["validation_warnings"] == []
    assert len(_json({key: persona[key] for key in CORE_FIELDS})) > 5000

    with pytest.raises(ValueError, match="persona.*budget"):
        _request(persona)


def test_provider_budget_drops_optional_context_before_author_boundaries():
    persona = {
        "character_id": "test_pet", "identity_version": "author-v3",
        "config_hash": "a" * 64, "boundaries": ["不能编造共同经历。" * 30],
        "traits": ["轻松自然" * 80],
    }
    fact = {"memory_id": "fact-1", "summary": "当前有效事实" * 40}
    lines = [
        "player_message: 今天聊什么？",
        "persona: " + _json(persona),
        "emotional_memory: " + _json({"shared_memories": [fact]}),
        "recent_dialogue: " + "旧对话" * 200,
    ]
    minimal_persona = {**persona, "traits": []}
    required = "\n".join([
        lines[0], "persona: " + _json(minimal_persona),
        "emotional_memory: " + _json({"shared_memories": []}), "",
    ])

    actual = fit_prompt(lines, limit=len(required) + 5)
    delivered = json.loads(next(line.removeprefix("persona: ") for line in actual.splitlines()
                                if line.startswith("persona: ")))

    assert len(actual) <= len(required) + 5
    assert delivered == minimal_persona
    assert "fact-1" not in actual
    assert "旧对话" not in actual


def test_provider_budget_fails_when_required_persona_itself_cannot_fit():
    persona = {"character_id": "test_pet", "boundaries": ["核心边界" * 80]}
    lines = ["fixed policy", "persona: " + _json(persona), "emotional_memory: {}"]

    with pytest.raises(ValueError, match="budget"):
        fit_prompt(lines, limit=100)


def test_real_draft_and_refinement_keep_the_same_core_identity(tmp_path):
    persona = _persona(tmp_path)
    request = _request(persona, emotional_memory={
        "context_epoch": 3,
        "shared_memories": [{"memory_id": "valid-1", "summary": "用户喜欢绿茶"}],
    })
    before = deepcopy(request.to_prompt_dict())

    with ShinsekaiAIExpressor(enabled=False) as expressor:
        draft_prompt = expressor.build_prompt(request)
    draft_persona = json.loads(next(line.removeprefix("persona: ") for line in draft_prompt.splitlines()
                                   if line.startswith("persona: ")))
    review_prompt = build_refinement_prompt(request, {
        "type": "speech", "speech": "今天有什么想聊的？", "effect": "ATTENTION",
    })
    review_persona = json.loads(review_prompt)["evidence"]["persona"]

    assert len(draft_prompt) <= MAX_OPENAI_PROMPT_LENGTH
    assert len(review_prompt) <= MAX_OPENAI_PROMPT_LENGTH
    for field in CORE_FIELDS:
        assert draft_persona[field] == review_persona[field] == persona[field]
    assert request.to_prompt_dict() == before
