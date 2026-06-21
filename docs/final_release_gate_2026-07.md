# Final Release Gate 2026-07

This gate records the current release-readiness state after the pixel Xingxi default-promotion and character-library profile-preview package.

## Product State

- Default character: `xingxi_pixel_pet`.
- Hidden fallback character: `original_oc`.
- `xingxi_pixel_pet` is the visible bundled Xingxi pack in the character library and runtime default.
- `original_oc` is kept in bundled assets only as a compatibility fallback and is hidden from the visible character library.
- Default decision record: `docs\default_character_decision_2026-07.md`.
- P16 confused/shy row remains part of the pixel-pet art QA history; this gate also verifies that the current pack exposes `ConfusedShy` through the motion manifest and that the character-library detail card now uses a profile CG preview instead of a full sprite/contact sheet.
- Ikaros and Nairong remain local UGC/fanwork workflow representatives only. They are not committed as public bundled assets, but can be placed under a private preview user's `character_packs` root for local switching QA.
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
- Report: `artifacts\final-acceptance-20260621\private-preview-deepseek-single-prompt-connectivity.json`.

## Pixel-Pet Gate

- `assets\companion\xingxi_pixel_pet`: pixel-pet pack validation `ok=true`.
- Distribution boundary: `official_candidate`.
- Character-library preview: `preview/profile.png` profile CG preview.
- Pixel visual QA: `status=ready`, `warnings=[]`.
- Suspicious edge halo ratio: `0.008154`.
- Pixel emote mapping: `status=ready`, `missing_motion_ids=[]`.
- Supported expression ids include `confused`, `focused`, `goofy`, `joy`, `sadness`, `sleepy`, and `surprised`.

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
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-202607\final-xingxi-pixel-pack-validation.json
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\route-scan-202607\final-xingxi-pixel-visual-qa.json --preview artifacts\route-scan-202607\final-xingxi-pixel-visual-qa-preview.png --fail-on-warnings
python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-202607\final-xingxi-pixel-emote-mapping.json --markdown artifacts\route-scan-202607\final-xingxi-pixel-emote-mapping.md
python tools\llm_dialogue_smoke.py --provider deepseek --timeout-seconds 45 --prompt "导师预览包 live LLM 自检：请用一句中文回应，并给出一个表情和一个动作提示。" --min-expression-actions 1 --min-motion-actions 1 --min-speech-chars 1 --max-speech-chars 80 --report artifacts\final-acceptance-20260621\private-preview-deepseek-single-prompt-connectivity.json
python tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\default-xingxi-profile-qa.json --screenshot-dir artifacts\character-library-qa\default-xingxi-profile-screenshots --pet-seconds 0.5
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python tools\release_readiness_report.py --character-pack assets\companion\xingxi_pixel_pet --app-dir dist\E-Moti --installer dist\installer\E-Moti_Setup_0.1.0.exe --llm-report artifacts\final-acceptance-20260621\private-preview-deepseek-single-prompt-connectivity.json --pixel-pet-emote-mapping-report artifacts\final-acceptance-20260621\xingxi-pixel-emote-mapping.json --pixel-pet-visual-qa-report artifacts\final-acceptance-20260621\xingxi-pixel-visual-qa.json --json artifacts\final-acceptance-20260621\release-readiness-default-xingxi-private-preview.json --markdown artifacts\final-acceptance-20260621\release-readiness-default-xingxi-private-preview.md
python tools\validate_windows_build.py --report artifacts\final-acceptance-20260621\windows-build-validation-default-xingxi.json
git status --short --untracked-files=all
git grep -n -E "sk-[A-Za-z0-9_-]{16,}|api[_-]?key" -- . ":!artifacts" ":!dist"
python -m pytest tests\test_repository_hygiene.py -q
```

## Verification Results

- `python -m pytest`: `891 passed`.
- `python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q`: `101 passed`.
- `python -m pytest tests\test_character_pack.py tests\test_character_registry.py tests\test_character_library_view_model.py tests\test_character_library_qa_tool.py tests\test_windows_build_validator.py tests\test_snapshot.py tests\test_repository_hygiene.py -q`: `71 passed`.
- `python -m pytest tests\test_repository_hygiene.py -q`: `5 passed`.
- `assets\companion\original_oc\shop_items.json`: valid JSON.
- `assets\companion\original_oc`: character pack validation `ok=true`.
- `assets\companion\xingxi_pixel_pet`: character pack validation `ok=true`.
- `assets\companion\xingxi_pixel_pet`: pixel-pet pack validation `ok=true`.
- Character library QA: `xingxi_pixel_pet`, `ikaros_ugc_pixel_pet`, and `nairong_ugc_pixel_pet` each passed; all three summaries use `preview/profile.png`.
- Release readiness: `ok=true`, `status=ready`, `ready_check_count=5`, `attention_check_count=0`.
- Windows build validation: `ok=true`; frozen app default character is `xingxi_pixel_pet`.
- Private preview zip: `dist\private-preview\E-Moti_Tutor_Private_Preview_20260621.zip`, `269,749,180` bytes, includes rebuilt app, private DeepSeek settings, and local Ikaros/Nairong UGC packs.
- Frozen control panel smoke: `ok`, stopped after 5 seconds.
- Frozen `--pet-mode` smoke: `ok`, stopped after 5 seconds.
- `git status --short --untracked-files=all`: review required before commit; ignored `dist\private-preview`, `dist`, and `artifacts` are delivery outputs, not source commits.
- Secret grep listed code fields, test placeholders, and documentation examples, but no live provider key was present in tracked files.

## Known Limits

- The demo can run and be played offline as a desktop pet; live AI expression is provider-dependent and currently validated with DeepSeek for the cue probe only.
- LLM, screen observation, search, ASR, and TTS still cannot own growth state, inventory, relationship, memory, goals, coins, or saves.
- Public repository artifacts include only the original Xingxi assets. Ikaros and Nairong are private/local UGC examples unless rights are cleared.
- The Windows app and installer must be rebuilt after default-promotion or private-preview packaging changes.
