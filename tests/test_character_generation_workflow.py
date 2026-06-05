import json

from guanghe_companion.character_generation_workflow import CharacterGenerationWorkflow


def _brief():
    return {
        "character_id": "teal_echo_companion",
        "name": "澄音",
        "title": "桌面回声同伴",
        "description": "一个由抽象灵感生成的原创桌面伴侣。",
        "visual_keywords": ["青绿色点缀", "轻舞台感"],
        "personality_keywords": ["活泼", "清亮"],
        "boundaries": ["不复制来源角色名、立绘、台词或专有设定"],
    }


def test_generation_workflow_writes_draft_pack_without_touching_assets(tmp_path):
    workflow = CharacterGenerationWorkflow(output_root=tmp_path / "generated")

    draft = workflow.create_draft(
        _brief(),
        source_notes=({"title": "profile", "summary": "abstracted traits", "url": "https://example.test"},),
    )

    assert draft.character_id == "teal_echo_companion"
    assert draft.import_ready is False
    assert draft.manual_qa_required is True
    assert draft.pack_dir == tmp_path / "generated" / "teal_echo_companion"
    assert (draft.pack_dir / "character.json").is_file()
    assert (draft.pack_dir / "dialogue_style.json").is_file()
    assert (draft.pack_dir / "shop_items.json").is_file()
    assert (draft.pack_dir / "motion_manifest.json").is_file()
    assert (draft.pack_dir / "art_prompts.json").is_file()
    assert (draft.pack_dir / "provenance.md").is_file()
    assert not (draft.pack_dir / "spritesheet.png").exists()
    assert "No copyrighted characters" in (draft.pack_dir / "art_prompts.json").read_text(encoding="utf-8")

    character = json.loads((draft.pack_dir / "character.json").read_text(encoding="utf-8"))
    assert character["name"] == "澄音"
    assert character["character_id"] == "teal_echo_companion"
    assert character["spritesheet"] == "spritesheet.png"


def test_generation_workflow_writes_local_fanwork_role_card_with_distribution_boundary(tmp_path):
    workflow = CharacterGenerationWorkflow(output_root=tmp_path / "generated")

    draft = workflow.create_draft(
        {
            **_brief(),
            "character_id": "ikaros_local_fanwork",
            "name": "Ikaros Local Draft",
            "title": "Private fanwork companion draft",
            "policy": "local_fanwork",
            "source_character": "Ikaros",
            "boundaries": [
                "Private local fanwork only",
                "Do not bundle or distribute",
                "No official art, logos, copied lines, or exact asset reproduction",
            ],
        },
        source_notes=(
            {
                "title": "Source profile",
                "summary": "Public profile notes used only by the local user.",
                "url": "https://example.test/ikaros",
            },
        ),
    )

    card_text = (draft.pack_dir / "character_card.md").read_text(encoding="utf-8")
    prompts_text = (draft.pack_dir / "art_prompts.json").read_text(encoding="utf-8")
    provenance_text = (draft.pack_dir / "provenance.md").read_text(encoding="utf-8")
    qa_text = (draft.pack_dir / "qa_checklist.md").read_text(encoding="utf-8")

    assert "Policy: local_fanwork" in card_text
    assert "Source character: Ikaros" in card_text
    assert "Private local fanwork only" in card_text
    assert "private local fanwork" in prompts_text
    assert "Do not bundle or distribute" in prompts_text
    assert "Local fanwork" in provenance_text
    assert "Do not commit local fanwork packs" in qa_text


def test_generation_workflow_rejects_unsafe_or_empty_brief(tmp_path):
    workflow = CharacterGenerationWorkflow(output_root=tmp_path / "generated")

    for brief in ({}, {"character_id": "../bad", "name": "Bad"}):
        try:
            workflow.create_draft(brief)
        except ValueError as exc:
            assert "invalid character brief" in str(exc)
        else:
            raise AssertionError("invalid brief should be rejected")


def test_generation_workflow_refuses_to_overwrite_existing_draft_without_force(tmp_path):
    workflow = CharacterGenerationWorkflow(output_root=tmp_path / "generated")
    workflow.create_draft(_brief())

    try:
        workflow.create_draft(_brief())
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing draft should not be overwritten without force")

    replaced = workflow.create_draft({**_brief(), "name": "澄音二号"}, force=True)
    character = json.loads((replaced.pack_dir / "character.json").read_text(encoding="utf-8"))
    assert character["name"] == "澄音二号"
