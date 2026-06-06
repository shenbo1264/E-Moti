# Live2D Web Spike

This directory is a developer-only spike for proving that E-Moti can render a real Live2D `.model3.json` model and route validated presentation actions into a renderer surface.

It intentionally does not commit Live2D model files or `live2dcubismcore.min.js`.

## Local Verification Assets

The smoke test expects:

- `tmp/live2d_research/CubismWebSamples/Samples/Resources/Haru/Haru.model3.json`
- `tmp/live2d_research/live2dcubismcore.min.js`

`CubismWebSamples` models are covered by Live2D's Free Material License. Cubism Core is covered by Live2D's proprietary runtime license. Keep both out of the public repository unless the distribution path is explicitly reviewed.

## Run

```powershell
python tools\live2d_spike\smoke_live2d_web.py
python tools\live2d_spike\smoke_app_surface.py
python tools\live2d_spike\smoke_character_pack_window.py
```

Expected result:

- the model loads in `QWebEngineView`,
- the configured expression is applied,
- the configured motion group is requested,
- E-Moti-shaped `visual_actions` are mapped and applied,
- a nonblank screenshot is written to `artifacts\simulation\live2d_spike.png`.
- the production `Live2DWebSurface` writes `artifacts\simulation\live2d_app_surface.png`.
- a temporary E-Moti character pack drives a real desktop `CompanionWindow` and writes `artifacts\simulation\live2d_character_pack_window.png`.

This spike is not yet the production desktop-pet renderer. Production integration should keep the same boundary:

```text
LLM -> typed speech/visual_actions events -> renderer adapter -> Live2D surface
```
