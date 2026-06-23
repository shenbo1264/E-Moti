# Demo Operator Quickstart

This guide is for a reviewer or operator who wants to run the current E-Moti demo without reading development chat context.

## What This Demo Shows

- A Windows desktop companion pet with local deterministic growth state.
- A control panel for status, actions, shop, inventory, relationship, memory, dialogue, settings, and character library.
- A transparent desktop pet mode with tray-friendly hiding, restoring, pet-mode entry, and exit paths.
- Optional AI expression that can produce speech, expression cues, motion cues, and read-only interaction intents through typed events.
- Character switching between the three bundled course-delivery packs plus any additional local packs.

## What This Demo Does Not Do

- It is not a productivity supervisor, course monitor, or mascot-only skin.
- It does not let LLMs mutate saves, inventory, memory, relationship, goals, coins, or growth state.
- It does not use background listening, wake words, mouse control, keyboard control, clipboard control, or window control.
- The course-delivery build includes `xingxi_pixel_pet`, `ikaros_pixel_pet`, and `nairong_pixel_pet` directly in the character library.

## Five-Minute Demo Flow

1. Run `python -m guanghe_companion.app`.
2. Check the status, action, shop, inventory, memory, dialogue, settings, and character library views.
3. Switch to desktop pet mode.
4. Hide and restore from the system tray.
5. Open the character library and confirm all three visible packs are present: `xingxi_pixel_pet`, `ikaros_pixel_pet`, and `nairong_pixel_pet`; switch between them once.
6. If a valid provider key or local OpenAI-compatible provider is available, run the LLM provider test and one dialogue turn.

## Verification Commands

Run the focused UI smoke first:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
```

Run the full source suite:

```powershell
python -m pytest
```

Validate bundled character packs:

```powershell
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_character_pack.py assets\companion\ikaros_pixel_pet
python tools\validate_character_pack.py assets\companion\nairong_pixel_pet
```

Check LLM provider configuration without making provider calls:

```powershell
python tools\llm_provider_matrix.py --dry-run --report artifacts\llm_smoke\provider-matrix-dry-run.json --markdown artifacts\llm_smoke\provider-matrix-dry-run.md
```

Run a live LLM cue probe only when a current provider or local server is configured:

```powershell
python tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\deepseek-expression-cue-probe.json
```

## Expected Current State

- `xingxi_pixel_pet` is the default visible bundled pack.
- `ikaros_pixel_pet` and `nairong_pixel_pet` are visible bundled course-delivery packs for character-switching demonstration.
- `original_oc` remains as older compatibility assets for historical renderer coverage.
- Live AI expression depends on a configured provider or local OpenAI-compatible server.
- The pixel pack includes a `ConfusedShy` motion row and maps `confused` / `shy` expression cues to it.
- Runtime saves, API keys, and ignored smoke artifacts are not committed.

## Demo Talking Points

- E-Moti is a companion pet with local gameplay state, not an LLM-owned agent loop.
- AI is used for expressive speech and presentation cues while typed event validation protects the pet state machine.
- The active art-production route is a hatch-pet-style pixel-pet sequence workflow: one base, one row, contact-sheet QA, repair, then promotion.
- Character packs keep assets, style, provenance/source notes, QA notes, voice profile metadata, and save namespace separate.
