# Final Release Gate 2026-07

This gate records the current release-readiness state for the course-delivery build after the three-role character-library correction.

## Product State

- Default character: `xingxi_pixel_pet`.
- Visible bundled characters: `xingxi_pixel_pet`, `ikaros_pixel_pet`, `nairong_pixel_pet`.
- All three bundled role packs are listed in the real character library and can be switched in the same runtime.
- `xingxi_pixel_pet` remains the default startup companion.
- `ikaros_pixel_pet` and `nairong_pixel_pet` are included in the course-delivery role set to demonstrate multi-character switching, independent character metadata, independent shop items, role-specific voice profile metadata, profile preview images, and sprite desktop-pet rendering.
- `original_oc` remains in the repository as an older compatibility asset, but it is not the course-delivery role-library focus.
- P16 confused/shy row remains part of the pixel-pet art QA history; this gate also verifies that the current Xingxi pack exposes `ConfusedShy` through the motion manifest and that the character-library detail card uses a profile CG preview instead of a full sprite/contact sheet.
- Live2D, LivePortrait, AI-video, and VN portrait routes remain research or later renderer paths.

## AI Gate

- Live DeepSeek smoke: `ok=true`.
- Provider: `deepseek`.
- Model: `deepseek-v4-flash`.
- Smoke turns: `1/1` passed.
- Failed smoke turns: `0`.
- Fallback count: `0`.
- Speech quality violations: `0`.
- State mutation guard: `changed_fields=[]`.
- Report: ignored DeepSeek smoke artifact from the 2026-06-21 final-acceptance run.

## Character Library Gate

- `assets\companion\xingxi_pixel_pet`: character pack validation `ok=true`; renderer `sprite`; visible in character library.
- `assets\companion\ikaros_pixel_pet`: character pack validation `ok=true`; renderer `sprite`; visible in character library.
- `assets\companion\nairong_pixel_pet`: character pack validation `ok=true`; renderer `sprite`; visible in character library.
- Character library QA has been run for all three ids and produced control-panel plus desktop-pet screenshots.
- Character-library UI copy now uses course-delivery wording such as `默认提交角色`, `课程提交角色`, `角色包信息`, and `交付状态`, instead of exposing internal warning-oriented text.
- Role detail cards use `preview/profile.png` when present; runtime desktop-pet presentation still uses each pack's sprite sheet.

## Pixel-Pet Gate

- `assets\companion\xingxi_pixel_pet`: pixel-pet pack validation `ok=true`.
- `assets\companion\ikaros_pixel_pet`: pixel-pet pack validation `ok=true`.
- `assets\companion\nairong_pixel_pet`: pixel-pet pack validation `ok=true`.
- Xingxi visual QA: `status=ready`, `warnings=[]`.
- Nairong edge cleanup completed before bundling; latest visual QA after cleanup reported `status=ready`, `warnings=[]`.
- Pixel emote mapping remains owned by typed `visual_actions.expression` and `visual_actions.motion`; LLM output still cannot mutate growth state, inventory, relationship, memory, goals, coins, or saves.

## P16 Candidate Evidence

- Candidate source: ignored `$imagegen` output copied under `artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\p16-confused-shy-row-20260618\`.
- Contact sheet: `artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\p16-confused-shy-row-20260618\review\confused-shy-row-contact-sheet.png`.
- Row review report: `artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\p16-confused-shy-row-20260618\review\confused-shy-row-review.json`.
- Row review result: `ok=true`, `actual_frames=6`, `extraction_method=components`, `warnings=[]`.
- Current runtime pack exposes the `ConfusedShy` motion and maps `confused` / `shy` expressions to it.

## Verification Commands

```powershell
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
python -m json.tool assets\companion\xingxi_pixel_pet\shop_items.json
python -m json.tool assets\companion\ikaros_pixel_pet\shop_items.json
python -m json.tool assets\companion\nairong_pixel_pet\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_character_pack.py assets\companion\ikaros_pixel_pet
python tools\validate_character_pack.py assets\companion\nairong_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-202607\final-xingxi-pixel-pack-validation.json
python tools\validate_pixel_pet_pack.py assets\companion\ikaros_pixel_pet --report artifacts\route-scan-202607\final-ikaros-pixel-pack-validation.json
python tools\validate_pixel_pet_pack.py assets\companion\nairong_pixel_pet --report artifacts\route-scan-202607\final-nairong-pixel-pack-validation.json
python tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\submission-three-role-xingxi-finaldoc.json --screenshot-dir artifacts\character-library-qa\submission-three-role-xingxi-finaldoc-screenshots --pet-seconds 0.5
python tools\character_library_qa.py --character-id ikaros_pixel_pet --report artifacts\character-library-qa\submission-three-role-ikaros-finaldoc.json --screenshot-dir artifacts\character-library-qa\submission-three-role-ikaros-finaldoc-screenshots --pet-seconds 0.5
python tools\character_library_qa.py --character-id nairong_pixel_pet --report artifacts\character-library-qa\submission-three-role-nairong-finaldoc.json --screenshot-dir artifacts\character-library-qa\submission-three-role-nairong-finaldoc-screenshots --pet-seconds 0.5
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest tests\test_repository_hygiene.py -q
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\windows-build-validation-submission-20260623.json
git status --short --untracked-files=all
```

## Verification Results

- `python -m pytest`: `927 passed`.
- `python -m pytest tests\test_character_library_view_model.py tests\test_app.py -q`: `105 passed`.
- `python -m pytest tests\test_character_library_qa_tool.py -q`: `6 passed`.
- `python -m pytest tests\test_character_pack.py tests\test_character_registry.py tests\test_character_library_view_model.py tests\test_character_library_qa_tool.py tests\test_app.py tests\test_desktop_pet_smoke.py tests\test_repository_hygiene.py -q`: `166 passed`.
- `assets\companion\ikaros_pixel_pet`: character pack validation `ok=true`.
- `assets\companion\nairong_pixel_pet`: character pack validation `ok=true`.
- Windows app rebuild: `tools\build_windows_app.ps1` completed successfully; output `dist\E-Moti\E-Moti.exe`.
- Windows installer rebuild: `tools\build_windows_installer.ps1 -SkipAppBuild` completed successfully; output `dist\installer\E-Moti_Setup_0.1.0.exe`.
- Windows build validation: `xingxi_pixel_pet`, `ikaros_pixel_pet`, and `nairong_pixel_pet` each `ok=true` in the frozen app.
- Frozen control-panel smoke: `ok`, stopped after 5 seconds.
- Frozen `--pet-mode` smoke: `ok`, stopped after 5 seconds.
- Character library QA: `xingxi_pixel_pet`, `ikaros_pixel_pet`, and `nairong_pixel_pet` each passed in the real control-panel flow and produced screenshots.

## Known Limits

- The demo can run and be played offline as a desktop pet; live AI expression remains provider-dependent and is validated through the DeepSeek smoke path.
- LLM, screen observation, search, ASR, and TTS still cannot own growth state, inventory, relationship, memory, goals, coins, or saves.
- The three-role submission route is visible in the bundled character library; additional imported packs remain supported through the local character-pack workflow.
- Role-card CG quality can still be improved in a separate art package, especially for matching all three role cards to the same final visual standard.
- The Windows app and installer must be rebuilt after role-asset, runtime-manifest, or packaging changes.
