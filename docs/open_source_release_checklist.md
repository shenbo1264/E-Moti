# Open Source Release Checklist

## Required Before Public Push

- `git status --short --untracked-files=all` reviewed.
- `python -m pytest` passes.
- `git grep -n "sk-" -- . ":!artifacts" ":!dist"` contains only test placeholders or public documentation examples.
- `data/companion_save.json`, `data/companion_demo_save.json`, and `data/dialogue_history.json` are not tracked.
- `assets/companion/original_oc` remains the default pack unless a default-promotion package says otherwise.
- `assets/companion/xingxi_pixel_pet` is described as an optional bundled candidate.
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
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --fail-on-warnings
```
