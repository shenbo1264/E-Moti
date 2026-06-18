# Open Source Release Checklist

## Required Before Public Push

- `git status --short --untracked-files=all` reviewed.
- `python -m pytest` passes.
- `docs\demo_operator_quickstart.md` describes the current demo flow and limitations.
- `git grep -n "sk-" -- . ":!artifacts" ":!dist"` contains only test placeholders or public documentation examples.
- `data/companion_save.json`, `data/companion_demo_save.json`, and `data/dialogue_history.json` are not tracked.
- `assets/companion/original_oc` remains the default pack unless a default-promotion package says otherwise.
- `assets/companion/xingxi_pixel_pet` is described as an optional bundled candidate.
- P16 row candidates under `artifacts/pixel-pet-sequence-drafts/` are ignored QA evidence until human visual approval and a separate promotion package.
- Ikaros and Nairong are not distributed as bundled assets.
- Third-party reference projects are not copied into this repository.

## Public Asset Boundary

- `original_oc`: default bundled original character pack.
- `xingxi_pixel_pet`: optional bundled official candidate after QA.
- Ikaros: local UGC/fanwork workflow representative only.
- Nairong: local UGC/fanwork workflow representative only.

## Final Commands

```powershell
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-202607\final-xingxi-pixel-pack-validation.json
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --fail-on-warnings
python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-202607\final-xingxi-pixel-emote-mapping.json --markdown artifacts\route-scan-202607\final-xingxi-pixel-emote-mapping.md
python tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\final-deepseek-expression-cue-probe-202607.json
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python tools\release_readiness_report.py --character-pack assets\companion\xingxi_pixel_pet --llm-report artifacts\llm_smoke\final-deepseek-expression-cue-probe-202607.json --pixel-pet-emote-mapping-report artifacts\route-scan-202607\final-xingxi-pixel-emote-mapping.json --pixel-pet-visual-qa-report artifacts\route-scan-202607\final-xingxi-pixel-visual-qa.json --json artifacts\route-scan-202607\final-release-readiness.json --markdown artifacts\route-scan-202607\final-release-readiness.md
python tools\validate_windows_build.py --report artifacts\route-scan-202607\windows-build-validation.json
```
