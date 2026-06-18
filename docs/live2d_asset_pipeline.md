# Live2D Asset Pipeline and Spike Verification

Date: 2026-06-06

Status: research path only. The near-term production route is `docs/pixel_pet_sequence_sop.md`; Live2D remains a later premium renderer option and must not block pixel-pet sequence work.

This document records the practical Live2D route for E-Moti. It separates three different things that must not be confused:

- Concept art: a bitmap reference for the character.
- Live2D source asset: a layered PSD imported into Cubism Editor.
- Live2D runtime asset: exported `.moc3`, `.model3.json`, textures, expressions, motions, pose, and physics files.

## Sources Checked

- Live2D Cubism Editor manual, PSD import: https://docs.live2d.com/en/cubism-editor-manual/psd-import/
- Live2D Cubism Editor manual, PSD creation notes: https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/
- Live2D Cubism Editor manual, embedded export data: https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/
- Live2D Cubism Web Samples license: https://github.com/Live2D/CubismWebSamples/blob/develop/LICENSE.md
- pixi-live2d-display: https://github.com/guansss/pixi-live2d-display
- Open-LLM-VTuber architecture reference: https://github.com/Open-LLM-VTuber/Open-LLM-VTuber

## Confirmed Asset Reality

`imagegen` can create a useful character reference, but it does not create a rigged Live2D model.

A real Live2D asset still needs:

1. A layered PSD with separated drawable parts.
2. Import and rigging inside Live2D Cubism Editor.
3. ArtMesh/deformer setup.
4. Parameter setup for face, body, breathing, hair, eyes, mouth, clothing, and accessories.
5. Expression and motion authoring.
6. Export as runtime data: `.moc3`, `.model3.json`, textures, expressions, motions, pose, and physics.

The generated Xingxi reference is saved at:

- `assets/companion/original_oc/live2d_sources/xingxi_live2d_cutting_reference.png`
- `assets/companion/original_oc/live2d_sources/xingxi_live2d_cutting_reference_alpha.png`

## Xingxi PSD Layer Checklist

The next real asset task is to redraw or separate the reference into a PSD with stable part names. Minimum layers:

- Head base, neck, blush, face shadow.
- Back hair, side hair left/right, front bangs, ahoge, individual blue highlight strands.
- Eye white left/right, iris left/right, pupil left/right, eye highlights, upper lashes, lower lashes.
- Eyebrows left/right.
- Mouth closed, mouth open interior, tongue/teeth if needed.
- Hoodie torso, left sleeve, right sleeve, jacket front left/right, collar, hood back, drawstrings, pocket ornaments.
- Inner shirt, skirt front/back, belt, pendant, bell/star accessory.
- Upper arms, forearms, hands/fingers separated enough for small motion.
- Thighs, socks, shoes, shoe bows, shoe star accessories.

Use stable English layer/group names so Cubism export review can be repeated. Recommended naming pattern:

```text
head/base
head/blush
hair/back
hair/front_bangs
hair/side_left
hair/side_right
eye_left/white
eye_left/iris
eye_left/pupil
eye_left/highlight
eye_right/white
eye_right/iris
eye_right/pupil
eye_right/highlight
mouth/closed
mouth/open
body/torso
body/neck
arm_left/upper
arm_left/forearm
arm_left/hand
arm_right/upper
arm_right/forearm
arm_right/hand
outfit/hoodie_body
outfit/hoodie_sleeve_left
outfit/hoodie_sleeve_right
outfit/skirt_front
accessory/star_pin
accessory/drawstring_left
accessory/drawstring_right
```

Recommended first rig scope:

- Idle breathing.
- Eye blink.
- Mouth open for lip-sync.
- Head X/Y/Z.
- Body X/Y/Z.
- Hair sway.
- Hoodie and accessory secondary motion.
- Expressions: calm, joy/excited, surprised, sleepy, sadness, focused.
- Motions: Idle, Play/TapBody, Raised/Surprised, TouchHead, Sleep.

## Cubism Export Acceptance

The first usable Xingxi Live2D character pack should place exported runtime files under:

```text
character_packs/xingxi_live2d/
  character.json
  dialogue_style.json
  motion_manifest.json
  shop_items.json
  spritesheet.png
  item_icons/
  live2d/
    Xingxi.model3.json
    Xingxi.moc3
    textures/
    expressions/
    motions/
```

The sprite files remain required as fallback/registry compatibility. They are not the primary renderer for a complete Live2D pack.

## Runtime Mapping Contract

E-Moti should keep the current typed boundary:

```text
LLM -> validated speech/visual_actions events -> renderer map -> Live2D model-specific expression/motion
```

Example project action payload:

```json
[
  {"type": "expression", "id": "excited", "ttl_ms": 3000, "priority": 70, "source": "llm"},
  {"type": "motion", "id": "Play", "ttl_ms": 1800, "priority": 60, "source": "llm"}
]
```

Example per-character Live2D map:

```json
{
  "renderer": {
    "backend": "live2d_web",
    "model": "live2d/Xingxi.model3.json",
    "expression_map": {
      "calm": "F01",
      "excited": "F02",
      "surprised": "F03",
      "sleepy": "F05",
      "sadness": "F04",
      "focused": "F06"
    },
    "motion_map": {
      "Default": "Idle",
      "Play": "TapBody",
      "Raised": "TapBody",
      "TouchHead": "TapHead",
      "Sleep": "Sleep"
    }
  }
}
```

The registry validation now requires a Live2D pack to include:

- Existing safe relative `.model3.json` path.
- Expression mappings for `calm`, `excited`, `surprised`, `sleepy`, `sadness`, and `focused`.
- Motion mappings for `Default`, `Play`, `Raised`, `TouchHead`, and `Sleep`.

Run this before trying the asset in the app:

```powershell
python tools\validate_character_pack.py character_packs\xingxi_live2d
```

Expected result for an accepted pack:

```json
{
  "ok": true,
  "character_id": "xingxi_live2d",
  "errors": []
}
```

## Verified Spike

Developer-only spike files:

- `tools/live2d_spike/index.html`
- `tools/live2d_spike/live2d_spike.js`
- `tools/live2d_spike/smoke_live2d_web.py`

Local-only verification dependencies:

- `tmp/live2d_research/CubismWebSamples/Samples/Resources/Haru/Haru.model3.json`
- `tmp/live2d_research/live2dcubismcore.min.js`

These are intentionally ignored and must not be committed without a license/distribution review.

Verified command:

```powershell
python tools\live2d_spike\smoke_live2d_web.py --timeout-seconds 45
python tools\live2d_spike\smoke_app_surface.py
python tools\live2d_spike\smoke_character_pack_window.py
```

Verified result on 2026-06-06:

- QWebEngine loaded a real `.model3.json` Live2D model.
- The page applied direct expression `F01`.
- The page applied direct motion group `TapBody`.
- E-Moti-shaped `visual_actions` were mapped and applied:
  - `expression: excited -> F02`
  - `motion: Play -> TapBody`
- Screenshot nonblank check passed:
  - `artifacts/simulation/live2d_spike.png`
  - `unique_colors` above 15,000.
- `npm audit --json` for `tools/live2d_spike` reports `0` vulnerabilities after overriding `gh-pages` to a fixed version.
- The production `Live2DWebSurface` smoke loaded the same model through a scoped localhost server and wrote `artifacts/simulation/live2d_app_surface.png`.
- A temporary E-Moti character pack drove a real desktop `CompanionWindow` and wrote `artifacts/simulation/live2d_character_pack_window.png`.

These screenshots use the ignored local Haru sample only to verify the runtime path. They are not Xingxi's formal Live2D asset.

## Licensing Boundary

Do not commit Live2D sample models, Cubism Core, or third-party Live2D models into the public repository by default.

The current safe route is:

1. Commit the spike code and scripts.
2. Keep official sample models and Cubism Core in ignored local `tmp/live2d_research`.
3. Commit only original Xingxi concept/reference images generated for this project.
4. For release, replace sample assets with a properly created Xingxi Live2D model and review Live2D SDK/runtime distribution requirements.
