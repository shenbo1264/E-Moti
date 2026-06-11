# Pseudo-Live2D VN Portrait Animation Plan

Date: 2026-06-06

Status: historical / research plan. The AI-video-first VN portrait path is paused for near-term production because current readiness evidence shows body drift and incomplete promotion gates. Use `docs/pixel_pet_sequence_sop.md` for active sequence-frame work.

## Context

The first portrait renderer package proved that the code path can select a portrait backend, validate a portrait manifest, and keep LLM visual actions separated from the pet state machine.

Its bundled generated portrait assets are not acceptable as the final GalGame / Spirit route art direction. They are Q-style square placeholder assets, not Shinsekai-like VN standing portraits. Keep them only as a temporary renderer smoke baseline until a better tall portrait set is approved.

## Target Experience

The route should feel like a visual novel character sprite living on the desktop:

- tall standing portrait, not chibi sticker;
- bottom-aligned stage;
- subtle breathing motion;
- randomized blinking;
- expression switching through typed LLM visual actions;
- sprite fallback preserved for tray and regression safety.

## Why Not Full Live2D Yet

Full Live2D still needs formal layered artwork, Cubism rigging, expression parameters, motion export, and runtime tuning. The near-term route is a stable pseudo-Live2D layer:

```text
AI creates consistent portrait variants.
Renderer adds breathing, blink timing, and crossfade.
LLM selects expression only.
Controller keeps growth state.
```

## Asset Strategy

Use one approved high-quality base portrait as the identity anchor. Do not generate every animation frame from scratch.

Minimum first usable asset set:

```text
portraits/
  neutral_open.png
  neutral_half.png
  neutral_closed.png
```

Recommended expression expansion:

```text
portraits/
  smile_open.png
  smile_half.png
  smile_closed.png
  thinking_open.png
  surprised_open.png
  sad_open.png
  sleepy_open.png
```

The three blink frames are enough for the desktop scale when combined with short crossfade timing. If close-up rendering exposes stepping, add five-eye-frame variants later:

```text
open -> quarter -> half -> three_quarter -> closed
```

Do not expand frame count before the base identity is stable.

## Manifest Contract

The portrait manifest keeps backward compatibility with simple string paths, but supports structured expression entries:

```json
{
  "version": 2,
  "fallback_expression": "neutral",
  "anchor": "bottom_center",
  "default_scale": 1.0,
  "expressions": {
    "neutral": {
      "open": "portraits/neutral_open.png",
      "blink_half": "portraits/neutral_half.png",
      "blink_closed": "portraits/neutral_closed.png"
    },
    "smile": "portraits/smile_open.png"
  },
  "animation": {
    "breathing": {
      "enabled": true,
      "amplitude_px": 3,
      "scale_delta": 0.012,
      "cycle_ms": 4200
    },
    "blink": {
      "enabled": true,
      "min_interval_ms": 3000,
      "max_interval_ms": 7000,
      "half_ms": 45,
      "closed_ms": 90
    }
  }
}
```

Validation requirements:

- all frame paths stay under `portraits/`;
- all frame files are PNG RGBA;
- `open` is required for structured entries;
- `blink_half` and `blink_closed` are optional individually, but blink is disabled for an expression until both exist;
- breathing values are clamped to conservative desktop ranges;
- blink timing must stay short and randomized.

## Animation Rules

Breathing:

- use a renderer-owned timer;
- scale delta between `0.0` and `0.03`;
- vertical offset between `0` and `8 px`;
- cycle between `2500` and `7000 ms`;
- do not move window, mouse, keyboard, clipboard, or OS state.

Blink:

- random interval, default `3000-7000 ms`;
- sequence: `open -> half -> closed -> half -> open`;
- normal blink should complete in about `150-240 ms`;
- sleepy expression may later hold closed eyes longer;
- LLM does not schedule individual blink frames.

## LLM Boundary

Allowed:

- choose expression id through typed `visual_actions.expression`;
- choose speech and tone through existing event validation;
- produce read-only interaction intents.

Forbidden:

- mutate save data;
- mutate inventory, relationship, goals, memories, coins, or state machine;
- schedule raw animation frames;
- bypass typed events.

## Next Implementation Package

1. Add manifest parser support for structured blink frames and animation config.
2. Add `SpiritStageSurface` breathing and blink timers.
3. Keep current placeholder assets marked as not final.
4. Generate a high-body VN candidate as an artifact for human QA.
5. Only after QA, replace default portrait assets with approved tall variants.

## Acceptance

Minimum verification:

```powershell
python -m pytest tests\test_spirit_stage.py tests\test_character_registry.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
```

Visual QA:

- desktop screenshot shows tall VN-style portrait, not square chibi;
- breathing is subtle and does not resize the window;
- blinking is irregular and not mechanical;
- expression switching still follows typed LLM actions.
