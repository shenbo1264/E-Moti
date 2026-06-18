# Final Release Gate 2026-06

## Product State

- Default character: `original_oc`. P8.2 was not executed; no default constant or runtime manifest was changed.
- Optional bundled character: `xingxi_pixel_pet`.
- LLM expression provider status: `artifacts\llm_smoke\deepseek-expression-cue-probe-latest.json`, `ok=true`, 5 cue cases passed, fallback count 0, speech quality violations 0, state mutation guard passed.
- Pixel-pet visual QA status: `ready`; `warnings=[]`; suspicious edge halo ratio `0.008811`.
- Pixel-pet emote mapping status: `ready`; `missing_motion_ids=[]`; supported expression ids include `joy`, `sadness`, `sleepy`, `focused`, `surprised`, `goofy`, and `confused`.
- Release readiness status: `ready`; 5 checks, 5 ready, 0 attention.
- Windows build status: not rebuilt in P11 because P8 did not change default assets and this package did not change packaging behavior. The final readiness check still validated the existing `dist\E-Moti` frozen build as `ready`.
- Installer status: not rebuilt in P11 because P8 did not change default assets and this package did not change installer behavior. The final readiness check still validated the existing installer path as `ready`.

## Verification Commands

```powershell
git status --short --untracked-files=all
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-20260618\final-xingxi-pixel-pack-validation.json
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\route-scan-20260618\final-xingxi-pixel-visual-qa.json --preview artifacts\route-scan-20260618\final-xingxi-pixel-visual-qa-preview.png --fail-on-warnings
python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-20260618\final-xingxi-pixel-emote-mapping.json --markdown artifacts\route-scan-20260618\final-xingxi-pixel-emote-mapping.md
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python tools\release_readiness_report.py --character-pack assets\companion\xingxi_pixel_pet --llm-report artifacts\llm_smoke\deepseek-expression-cue-probe-latest.json --pixel-pet-emote-mapping-report artifacts\route-scan-20260618\final-xingxi-pixel-emote-mapping.json --pixel-pet-visual-qa-report artifacts\route-scan-20260618\final-xingxi-pixel-visual-qa.json --json artifacts\route-scan-20260618\final-release-readiness.json --markdown artifacts\route-scan-20260618\final-release-readiness.md
```

## Verification Results

- `python -m pytest`: `843 passed`.
- `python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q`: `96 passed`.
- `assets\companion\original_oc\shop_items.json`: valid JSON.
- `assets\companion\original_oc`: character pack validation `ok=true`.
- `assets\companion\xingxi_pixel_pet`: character pack validation `ok=true`.
- `assets\companion\xingxi_pixel_pet`: pixel-pet pack validation `ok=true`, `distribution_boundary=official_candidate`.
- Final release readiness: `ok=true`, `status=ready`, `ready_check_count=5`, `attention_check_count=0`.

## Distribution Boundary

- `original_oc`: default bundled original character pack.
- `xingxi_pixel_pet`: QA-gated optional bundled official candidate.
- Ikaros: local UGC/fanwork workflow representative only; not bundled.
- Nairong: local UGC/fanwork workflow representative only; not bundled.

## Known Limits

- LLM does not own growth state, memory, relationship, inventory, goals, coins, or saves.
- Ikaros and Nairong are local UGC workflow representatives only.
- Live2D, LivePortrait, AI-video, and VN portrait routes remain research paths.
- `AGENTS.md` is modified in the working tree but was not part of P6-P11 implementation commits.
