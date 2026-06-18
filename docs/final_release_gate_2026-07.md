# Final Release Gate 2026-07

This gate records the P12-P17 continuation result. It is a source and artifact readiness gate, not a default-promotion package.

## Product State

- Default character: `original_oc`.
- Optional bundled character: `xingxi_pixel_pet`.
- `xingxi_pixel_pet` remains an optional sprite candidate; no default constant, installer behavior, or runtime manifest was changed in P12-P17.
- Default decision record: `docs\default_character_decision_2026-07.md`.
- P16 confused/shy row candidate was generated under ignored artifacts and passed row review, but it was not promoted into runtime assets because visual approval is still required before changing `assets/companion/xingxi_pixel_pet`.
- Ikaros and Nairong remain local UGC/fanwork workflow representatives only and are not bundled.
- Live2D, LivePortrait, AI-video, and VN portrait routes remain research or later renderer paths.

## AI Gate

- Live DeepSeek cue probe: `ok=true`.
- Provider: `deepseek`.
- Model: `deepseek-v4-flash`.
- Cue cases: `5/5` passed.
- Failed cue cases: `0`.
- Fallback count: `0`.
- Speech quality violations: `0`.
- State mutation guard: `changed_fields=[]`.
- Report: `artifacts\llm_smoke\final-deepseek-expression-cue-probe-202607.json`.

## Pixel-Pet Gate

- `assets\companion\xingxi_pixel_pet`: pixel-pet pack validation `ok=true`.
- Distribution boundary: `official_candidate`.
- Pixel visual QA: `status=ready`, `warnings=[]`.
- Suspicious edge halo ratio: `0.008811`.
- Pixel emote mapping: `status=ready`, `missing_motion_ids=[]`.
- Supported expression ids include `confused`, `focused`, `goofy`, `joy`, `sadness`, `sleepy`, and `surprised`.

## P16 Candidate Evidence

- Candidate source: ignored `$imagegen` output copied under `artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\p16-confused-shy-row-20260618\`.
- Contact sheet: `artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\p16-confused-shy-row-20260618\review\confused-shy-row-contact-sheet.png`.
- Row review report: `artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\p16-confused-shy-row-20260618\review\confused-shy-row-review.json`.
- Row review result: `ok=true`, `actual_frames=6`, `extraction_method=components`, `warnings=[]`, `runtime_manifest_updated=false`.
- The row is suitable for human visual approval review, but it has not been committed or promoted.

## Verification Commands

```powershell
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-202607\final-xingxi-pixel-pack-validation.json
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\route-scan-202607\final-xingxi-pixel-visual-qa.json --preview artifacts\route-scan-202607\final-xingxi-pixel-visual-qa-preview.png --fail-on-warnings
python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-202607\final-xingxi-pixel-emote-mapping.json --markdown artifacts\route-scan-202607\final-xingxi-pixel-emote-mapping.md
python tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\final-deepseek-expression-cue-probe-202607.json
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python tools\release_readiness_report.py --character-pack assets\companion\xingxi_pixel_pet --llm-report artifacts\llm_smoke\final-deepseek-expression-cue-probe-202607.json --pixel-pet-emote-mapping-report artifacts\route-scan-202607\final-xingxi-pixel-emote-mapping.json --pixel-pet-visual-qa-report artifacts\route-scan-202607\final-xingxi-pixel-visual-qa.json --json artifacts\route-scan-202607\final-release-readiness.json --markdown artifacts\route-scan-202607\final-release-readiness.md
python tools\validate_windows_build.py --report artifacts\route-scan-202607\windows-build-validation.json
git status --short --untracked-files=all
git grep -n -E "sk-[A-Za-z0-9_-]{16,}|api[_-]?key" -- . ":!artifacts" ":!dist"
python -m pytest tests\test_repository_hygiene.py -q
```

## Verification Results

- `python -m pytest`: `869 passed`.
- `python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q`: `97 passed`.
- `python -m pytest tests\test_pixel_pet_row_review.py tests\test_art_tools.py tests\test_motion.py -q`: `32 passed`.
- `python -m pytest tests\test_repository_hygiene.py -q`: `3 passed` before this document test was added; rerun after this document must pass `4 passed`.
- `assets\companion\original_oc\shop_items.json`: valid JSON.
- `assets\companion\original_oc`: character pack validation `ok=true`.
- `assets\companion\xingxi_pixel_pet`: character pack validation `ok=true`.
- `assets\companion\xingxi_pixel_pet`: pixel-pet pack validation `ok=true`.
- Release readiness: `ok=true`, `status=ready`, `ready_check_count=5`, `attention_check_count=0`.
- Windows build validation: `ok=true`; existing frozen app and installer paths were found.
- `git status --short --untracked-files=all`: `M AGENTS.md` only at the time of the gate. `AGENTS.md` was intentionally not staged by this package.
- Secret grep listed code fields, test placeholders, and documentation examples, but no live provider key was present in tracked files.

## Known Limits

- The demo can run and be played offline as a desktop pet; live AI expression is provider-dependent and currently validated with DeepSeek for the cue probe only.
- LLM, screen observation, search, ASR, and TTS still cannot own growth state, inventory, relationship, memory, goals, coins, or saves.
- The P16 confused/shy row is not visible in runtime until it receives visual approval and a separate asset-promotion package updates the atlas and manifest.
- The Windows app and installer were validated but not rebuilt in P17 because no default assets, dependencies, packaging scripts, or installer behavior changed.
