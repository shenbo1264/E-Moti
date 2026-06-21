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

Use `private_local_fanwork` for Ikaros, Nairong, or other fanwork packs when the pack intentionally follows a known third-party character.

## Local UGC Import Boundary

- `shareable_after_review`: original, remix, or fanwork pack that has basic QA, provenance/source notes, and runtime validation.
- `local_ugc_only`: user-created pack; can still be shared in the non-commercial demo route after basic QA.
- `private_local_fanwork`: fanwork or third-party-inspired pack; can be published for the non-commercial demo route when source notes and QA evidence are included.

Importing a pack copies it into the local user character-pack folder. Import confirmation and JSON reports surface the pack's source-note status, but they do not block local UGC or fanwork packs from later export.

## Validation Commands

```powershell
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet
python tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\xingxi-pixel-pet-latest.json --screenshot-dir artifacts\character-library-qa\xingxi-pixel-pet-latest-screenshots
python -m pytest tests\test_character_registry.py tests\test_character_session.py tests\test_character_pack_import_tool.py tests\test_app.py -q
```

## Import Rule

Only import complete packs that pass validation. Do not copy ignored draft folders directly into `assets/companion/`; export a validated pack folder with provenance/source notes instead.
