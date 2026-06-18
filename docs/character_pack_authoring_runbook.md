# Character Pack Authoring Runbook

## Goal

Create a complete local character pack that can be validated, imported, selected in the character library, and kept separate from other characters' state.

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

## Distribution Boundary

Use one of:

- `shareable_after_review`
- `local_ugc_only`
- `private_local_fanwork`

Use `private_local_fanwork` for Ikaros or Nairong experiments unless rights are cleared.

## Validation Commands

```powershell
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet
python tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\xingxi-pixel-pet-latest.json --screenshot-dir artifacts\character-library-qa\xingxi-pixel-pet-latest-screenshots
python -m pytest tests\test_character_registry.py tests\test_character_session.py tests\test_character_pack_import_tool.py tests\test_app.py -q
```

## Import Rule

Only import complete packs that pass validation. Do not copy ignored draft folders directly into `assets/companion/`.
