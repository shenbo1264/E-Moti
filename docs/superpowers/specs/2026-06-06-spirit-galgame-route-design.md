# Spirit / GalGame Companion Route Design

Date: 2026-06-06

Status: historical route design. This document records the earlier Spirit/GalGame direction; the current near-term route is `docs/pixel_pet_sequence_sop.md` plus `docs/current_development_route_2026-06-11.md`.

## Goal

Move E-Moti from a small sprite-first demo toward a large portrait, Spirit/GalGame-like desktop companion route while preserving the existing desktop pet baseline.

The short-term goal is not formal Live2D production. It is a stable presentation layer where the LLM can make Xingxi feel more expressive through typed speech, expression cues, motion cues, and dialogue staging without taking ownership of the pet growth state machine.

## Product Direction

The primary experience should feel like a character companion, not a study tool, productivity coach, mascot, or chatbot shell.

Priority order:

1. Keep the existing sprite renderer as the fallback and smoke-test baseline.
2. Add a portrait/spirit renderer for half-body or full-body character art.
3. Let typed LLM visual actions select presentational expressions and gentle motions.
4. Keep state, inventory, relationship, memories, goals, and saves under local controller ownership.
5. Keep Live2D as a later premium renderer that consumes the same typed presentation actions.

## External Signals

Recent forum and open-source references point to the same product risk:

- Users want continuity, memory, personality consistency, and expressive reactions.
- Users reject companions that feel like generic assistants, unstable roleplay, or a state system that changes unpredictably.
- Mature AI companion projects tend to split LLM, voice, perception, character configuration, and renderer modules instead of mixing them into one loop.

Design implication: LLM should direct performance, but it should not directly mutate progression.

## Non-Goals

- No mouse, keyboard, clipboard, or window control in this package.
- No wake word, background listening, startup persistence, or elevated install.
- No copied source code, art, prompts, audio, or character settings from Shinsekai, VPet, Live2D sample models, Vocaloid, Bandori, or other third-party IP.
- No rewrite of the controller or save schema for this route.
- No dependency on a rigged Live2D model for the first shippable visual improvement.

## Renderer Contract

Add a new renderer backend such as `portrait`.

Expected character pack shape:

```text
assets/companion/<character_id>/
  character.json
  portrait_manifest.json
  portraits/
    neutral.png
    smile.png
    thinking.png
    surprised.png
    sad.png
    sleepy.png
```

`character.json` should keep the existing sprite fields so legacy smoke tests and fallback remain available. The new renderer fields live under `renderer`:

```json
{
  "renderer": {
    "backend": "portrait",
    "portrait_manifest": "portrait_manifest.json",
    "expression_map": {
      "calm": "neutral",
      "joy": "smile",
      "excited": "smile",
      "focused": "thinking",
      "surprised": "surprised",
      "sadness": "sad",
      "sleepy": "sleepy"
    }
  }
}
```

`portrait_manifest.json` defines safe local image paths:

```json
{
  "version": 1,
  "fallback_expression": "neutral",
  "anchor": "bottom_center",
  "default_scale": 1.0,
  "expressions": {
    "neutral": "portraits/neutral.png",
    "smile": "portraits/smile.png",
    "thinking": "portraits/thinking.png",
    "surprised": "portraits/surprised.png",
    "sad": "portraits/sad.png",
    "sleepy": "portraits/sleepy.png"
  }
}
```

Validation requirements:

- `portrait_manifest` must be a safe relative filename.
- Expression image paths must stay inside `portraits/`.
- Required expressions: `neutral`, `smile`, `thinking`, `surprised`, `sad`, `sleepy`.
- Fallback expression must exist in `expressions`.
- Images must be PNG, readable by Pillow, RGBA, and within the configured size limit.

## LLM Presentation Mapping

Typed `visual_actions` map to portrait ids:

| LLM action id | Portrait id |
| --- | --- |
| calm | neutral |
| joy | smile |
| excited | smile |
| focused | thinking |
| surprised | surprised |
| sadness | sad |
| sleepy | sleepy |

The mapping is presentational only. It must not write state, inventory, relationship, memories, goals, or save data.

## UI Surface

The Spirit stage should be a separate PySide6 widget or small module, not a large `app.py` expansion.

Required behavior:

- bottom-aligned portrait scaling;
- stable stage bounds across desktop and panel modes;
- expression crossfade;
- transparent or quiet background;
- dialogue/name layer suitable for repeated interaction;
- fallback to sprite if the portrait pack is invalid or incomplete.

## Asset Pipeline

The first formal art package should include:

- original Xingxi portrait expression PNGs;
- transparent backgrounds;
- consistent face, outfit, palette, and proportions;
- a preview/contact sheet;
- an asset provenance note with prompts, tool source, review status, and rejection notes.

Temporary generated images, API keys, rejected experiments, third-party samples, and runtime saves must stay out of commits.

## Verification

Minimum checks for this route:

```powershell
python -m pytest tests\test_character_pack.py tests\test_character_registry.py -q
python -m pytest tests\test_presentation_renderer.py -q
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
git diff --check
```

If packaging behavior changes, also run the Windows app and installer build scripts.
