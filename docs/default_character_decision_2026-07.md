# Default Character Decision 2026-07

## Decision

Promote `xingxi_pixel_pet` to the default character in this package.
The course-delivery role library also bundles `ikaros_pixel_pet` and `nairong_pixel_pet` as visible switchable characters.

## Current Runtime Default

- Default character: `xingxi_pixel_pet`.
- Visible course-delivery characters: `xingxi_pixel_pet`, `ikaros_pixel_pet`, `nairong_pixel_pet`.
- Compatibility assets: `original_oc`.
- The default constant and initial runtime state now point at `xingxi_pixel_pet`.
- Packaging scripts and installer paths are unchanged, but the Windows app and installer must be rebuilt so frozen artifacts contain the new default.

## Reasoning

- The course-facing product route is now pixel-pet first, and the older large `original_oc` route no longer matches the desired role-library presentation.
- `xingxi_pixel_pet` is the validated original Xingxi pack that can be distributed in the public repository.
- `ikaros_pixel_pet` and `nairong_pixel_pet` demonstrate that the same runtime can switch role appearance, dialogue style, shop theme, voice profile metadata, and memory namespace.
- `original_oc` remains useful for tests and older renderer coverage, but should not be the visible default role.

## Promotion Verification Gate

Changing the default to `xingxi_pixel_pet` requires:

- an intentional default constant change;
- README and release-doc updates that describe the runtime default;
- source tests and UI smoke tests;
- Windows app and installer rebuilds;
- exact validation results recorded in a dated final gate.

Required commands:

```powershell
python -m pytest tests\test_character_pack.py tests\test_character_registry.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\windows-build-validation-xingxi-pixel-pet.json
python tools\validate_windows_build.py --character-id ikaros_pixel_pet --report artifacts\windows-build-validation-ikaros-pixel-pet.json
python tools\validate_windows_build.py --character-id nairong_pixel_pet --report artifacts\windows-build-validation-nairong-pixel-pet.json
```
