# Default Character Decision 2026-07

## Decision

Do not promote `xingxi_pixel_pet` to the default character in this package.

## Current Runtime Default

- Default character: `original_oc`.
- Optional bundled character: `xingxi_pixel_pet`.
- No default constant, runtime manifest, packaging script, installer behavior, or install path was changed.

## Reasoning

- `original_oc` is still the stable default presentation route for the open-source demo.
- `xingxi_pixel_pet` is validated and useful as an optional sprite candidate, but default promotion is a separate product decision.
- The P16 confused/shy row candidate exists only under ignored artifacts and has not received human visual approval for runtime promotion.
- Ikaros and Nairong remain local UGC/fanwork workflow representatives only and cannot be bundled without rights clearance.

## Promotion Gate For A Future Package

Before changing the default to `xingxi_pixel_pet`, run a separate default-promotion package that:

- updates the default character constant intentionally;
- updates README and release docs that describe the runtime default;
- reruns source tests and UI smoke tests;
- rebuilds the Windows app and installer if default assets or packaging contents change;
- records exact validation results in a new dated final gate.

Required commands for that future package:

```powershell
python -m pytest tests\test_character_pack.py tests\test_character_registry.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --character-id xingxi_pixel_pet --report artifacts\windows-build-validation-xingxi-pixel-pet.json
```
