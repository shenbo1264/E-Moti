# Default Character Decision 2026-06

Decision: keep `original_oc` as default.

Reason:

- `original_oc` remains the stable demo baseline.
- `xingxi_pixel_pet` is available as an optional bundled candidate.
- No runtime manifest or default constant change is required.
- The current roadmap does not require a default-character switch to complete P6-P11.

Verification:

- `python -m pytest tests\test_character_pack.py tests\test_character_registry.py tests\test_app.py tests\test_desktop_pet_smoke.py -q` passed with `130 passed`.
- `python tools\validate_character_pack.py assets\companion\original_oc` passed with `ok=true`.
- `python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet` passed with `ok=true`.
- `python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --fail-on-warnings` passed with `status=ready` and `warnings=[]`.
- `python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-20260618\p8-default-decision-emote-mapping.json --markdown artifacts\route-scan-20260618\p8-default-decision-emote-mapping.md` passed with `status=ready` and `missing_motion_ids=[]`.

P8.2 status: not executed. Promoting `xingxi_pixel_pet` to default remains a separate explicit decision package.
