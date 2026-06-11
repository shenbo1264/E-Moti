# Live2D Renderer Spike

Date: 2026-06-06

Status: renderer research path only. The current near-term production route is `docs/pixel_pet_sequence_sop.md`; Live2D should consume the same typed presentation actions later, not replace the pixel-pet sequence plan now.

This note evaluates whether E-Moti should move from sprite sheets to a Live2D-style renderer while keeping the current rule: LLM output may control presentation, but it must not own companion state, inventory, relationship, memory, goals, or saves.

## Current Baseline

- LLM output is normalized into speech events and `visual_actions`.
- `VisualAction` currently supports `expression` and `motion`.
- `SpritePresentationAdapter` converts `visual_actions` into the current sprite motion override.
- This means the future path is already:

```text
LLM output -> expression parser -> typed event validation -> visual_actions -> presentation renderer
```

Live2D should plug in at the final renderer step only.

## Reference Findings

### Open-LLM-VTuber

Source: https://github.com/Open-LLM-VTuber/Open-LLM-VTuber

Open-LLM-VTuber is the closest architecture reference found for an AI companion with voice interaction, perception, and a Live2D avatar. Its public README describes Live2D expressions and backend emotion mapping as first-class features.

Usable lesson:

- Backend should output a small emotion/action vocabulary.
- Renderer maps that vocabulary to model-specific expression and motion names.
- The model-specific mapping should be config, not hardcoded inside the LLM prompt.

Do not copy:

- Source code, prompts, assets, model files, character setup, or bundled UI.

### pixi-live2d-display

Source: https://github.com/guansss/pixi-live2d-display

This is the most practical route for a PySide desktop app because it runs in the browser/WebGL stack. The README positions it as a PixiJS framework for Live2D on the web platform, with high-level controls for transforms, interactions, motion, and expression.

Candidate integration:

- Use `QWebEngineView` as a Live2D surface.
- Load a local HTML/JS renderer that uses PixiJS plus `pixi-live2d-display`.
- Python sends sanitized presentation messages through a narrow bridge:

```json
{
  "type": "visual_actions",
  "actions": [
    {"type": "expression", "id": "joy", "ttl_ms": 3000, "priority": 70, "source": "llm"},
    {"type": "motion", "id": "Play", "ttl_ms": 1800, "priority": 60, "source": "llm"}
  ]
}
```

Advantages:

- Better ecosystem for Live2D than pure Python.
- Keeps Live2D code isolated from the Python state machine.
- Can be prototyped without changing the existing sprite renderer.

Risks:

- Adds WebEngine and frontend asset packaging complexity.
- Requires careful local-file loading and path validation.
- Requires separate UI smoke tests for WebGL nonblank rendering.

### Live2D Cubism SDK License

Source: https://www.live2d.com/en/sdk/license/

Live2D's SDK release license page explicitly lists AI / Chatbot as a usage type and explains that release licensing is separate from development verification. This means a prototype can be evaluated, but distribution cannot be treated like a normal MIT dependency decision.

Decision for now:

- Do not bundle Cubism Core or Live2D SDK files in the repository.
- Do not ship a Live2D build until the release/license path is confirmed.
- Keep the first spike behind a local developer-only asset path.

### Inochi2D

Sources:

- https://inochi2d.com/
- https://docs.inochi2d.com/en/latest/inochi2d/faq.html

Inochi2D is an open-source 2D puppet framework and is attractive from a licensing perspective. Its FAQ says it is an entirely new format and fundamentally incompatible with Live2D.

Decision for now:

- Track it as an alternative renderer backend, not as a Live2D replacement.
- Do not route the first Live2D spike through Inochi2D unless the goal changes from Live2D compatibility to open puppet format support.

## Recommended Architecture

Keep the Python boundary as:

```text
ExpressionEventPipeline
  -> snapshot.visual_actions
  -> PresentationRendererAdapter
      -> SpritePresentationAdapter
      -> FutureLive2DWebAdapter
```

The Live2D adapter should accept only:

- Character asset root.
- Model config path, such as `.model3.json`.
- A character-specific mapping file.
- Validated `visual_actions`.

The Live2D adapter must not accept:

- Raw LLM text.
- State mutation requests.
- Keyboard/mouse/window control requests.
- Arbitrary script strings.
- Remote model URLs by default.

## Character Pack Extension

Add optional renderer metadata later:

```json
{
  "renderer": {
    "backend": "live2d_web",
    "model": "live2d/model.model3.json",
    "motion_map": {
      "Default": "Idle",
      "TouchHead": "TapHead",
      "Play": "Playful",
      "SwitchDown": "Sad",
      "Sleep": "Sleep",
      "Raised": "Surprised",
      "Study": "Focus"
    },
    "expression_map": {
      "joy": "exp_joy.exp3.json",
      "sadness": "exp_sad.exp3.json",
      "sleepy": "exp_sleepy.exp3.json",
      "focused": "exp_focus.exp3.json",
      "surprised": "exp_surprised.exp3.json",
      "calm": "exp_calm.exp3.json"
    }
  }
}
```

This keeps `VisualAction.action_id` stable while each character decides how that action maps to its assets.

## Prototype Plan

1. Add a disabled-by-default `Live2DWebPresentationAdapter` interface in Python.
2. Add a local-only WebEngine smoke harness with a minimal test page.
3. Load one developer-supplied `.model3.json` outside the public repo.
4. Send existing `visual_actions` to the page.
5. Verify:
   - model canvas is nonblank,
   - motion action changes model state,
   - expression action changes expression,
   - invalid action IDs are ignored,
   - no state fields mutate,
   - no remote URL loads by default.

## Historical Recommendation

At the start of the spike, the recommendation was to proceed with Live2D as a spike, not a mainline dependency yet.

That recommendation has been partially executed: the renderer backend contract exists, a local WebEngine prototype exists, and the main application can route a Live2D character pack through `Live2DWebSurface`. The remaining gap is not the renderer path; it is a properly rigged Xingxi Live2D asset and a reviewed distribution path for Live2D runtime files.

## 2026-06-06 Spike Result

The first developer-only WebEngine spike now exists under `tools/live2d_spike`.

Verified command:

```powershell
python tools\live2d_spike\smoke_live2d_web.py --timeout-seconds 45
```

Verified result:

- `QWebEngineView` loaded an official sample `.model3.json` from ignored local `tmp/live2d_research`.
- `pixi.js` plus `pixi-live2d-display` rendered the model.
- `visual_actions` using E-Moti's existing payload shape were mapped to Live2D expression and motion IDs.
- Screenshot validation wrote `artifacts/simulation/live2d_spike.png` and passed a nonblank image check.

This first spike was not the production desktop-pet renderer and did not include a rigged Xingxi model. It proved the Live2D runtime route and the LLM-to-renderer presentation boundary.

## 2026-06-06 Production Surface Step

The main application now has a production `Live2DWebSurface` entry point under `src/guanghe_companion/live2d_web.py`.

Verified command:

```powershell
python tools\live2d_spike\smoke_app_surface.py
```

Verified result:

- The production surface created a `QWebEngineView`.
- It started a localhost static server scoped to renderer files, Cubism Core, and the active character asset directory.
- It loaded a sample `.model3.json` through `/character-assets/...`.
- It sent already-mapped E-Moti `live2d_actions` to the Web page.
- The Web page applied `excited -> F02` and `Play -> TapBody`.
- Screenshot validation wrote `artifacts/simulation/live2d_app_surface.png` and passed a nonblank image check.

Sprite rendering is now fallback behavior when a character pack does not provide a safe existing Live2D `.model3.json`.

## 2026-06-06 Character Pack Window Step

The desktop window can now be driven by a temporary E-Moti character pack that declares `renderer.backend = "live2d_web"`.

Verified command:

```powershell
python tools\live2d_spike\smoke_character_pack_window.py
```

Verified result:

- The app selected `live2d_web` from character pack metadata.
- A real `CompanionWindow` loaded a sample `.model3.json` through the scoped local server.
- Mapped LLM visual actions were applied:
  - `excited -> F02`
  - `Play -> TapBody`
- Screenshot validation wrote `artifacts/simulation/live2d_character_pack_window.png` and passed a nonblank image check.
- Client disconnects during shutdown no longer print server tracebacks.

This still uses an ignored local Haru sample model. It is runtime verification, not the formal Xingxi Live2D asset.
