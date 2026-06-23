# Character Pack Authoring Runbook

## Goal

Create a complete character pack that can be validated, bundled or imported, selected in the character library, and kept separate from other characters' state.

## Required Pack Shape

```text
character_packs_drafts/xingxi_pixel_pet/
  character.json
  dialogue_style.json
  motion_manifest.json
  shop_items.json
  spritesheet.png
  preview/contact-sheet.png
  provenance.md
  LICENSE.md
  qa_report.json
```

## Source Metadata

The course-delivery build already includes `xingxi_pixel_pet`, `ikaros_pixel_pet`, and `nairong_pixel_pet` as visible bundled packs. Each pack should keep `provenance.md`, `LICENSE.md`, `qa_report.json`, `dialogue_style.json`, `motion_manifest.json`, and voice profile metadata together so reviewers can see how the role was made and how it passed QA.

Additional authored packs can use the same metadata fields so the registry and import report can show their source notes. These metadata fields are for traceability and character independence; they should not be used as a reason to hide validated course-delivery characters from the role library.

Importing a pack copies it into the local user character-pack folder. Import confirmation and JSON reports surface the pack's source-note status while keeping its assets, voice profile metadata, shop theme, and save namespace separate from other characters.

## Validation Commands

```powershell
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet
python tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\xingxi-pixel-pet-latest.json --screenshot-dir artifacts\character-library-qa\xingxi-pixel-pet-latest-screenshots
python tools\validate_character_pack.py assets\companion\ikaros_pixel_pet
python tools\validate_character_pack.py assets\companion\nairong_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\ikaros_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\nairong_pixel_pet
python tools\character_library_qa.py --character-id ikaros_pixel_pet --report artifacts\character-library-qa\ikaros-pixel-pet-latest.json --screenshot-dir artifacts\character-library-qa\ikaros-pixel-pet-latest-screenshots
python tools\character_library_qa.py --character-id nairong_pixel_pet --report artifacts\character-library-qa\nairong-pixel-pet-latest.json --screenshot-dir artifacts\character-library-qa\nairong-pixel-pet-latest-screenshots
python -m pytest tests\test_character_registry.py tests\test_character_session.py tests\test_character_pack_import_tool.py tests\test_app.py -q
```

## Import Rule

Only import complete packs that pass validation. Do not copy ignored draft folders directly into `assets/companion/`; export a validated pack folder with provenance/source notes instead.
