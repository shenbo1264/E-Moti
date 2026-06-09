# Spirit Sequence Frame SOP

This is the current preferred art route for E-Moti's Spirit/GalGame presentation.
It supersedes the AI-video-first route as the near-term default because the video route has shown body drift and motion extraction instability.

The goal is not to build a new renderer contract. The goal is to create better portrait inputs for the existing `portrait` backend and its `motion_frames` support.

## Working Principle

Use the same discipline as the `hatch-pet` workflow, but adapt it to large Spirit/VN portraits:

1. Create one canonical base portrait first.
2. Treat that base as the visual source of truth.
3. Generate grounded sequence strips per state.
4. Keep every state in a separate prompt and candidate folder.
5. Run QA on each state before promotion.
6. Repair only the failing state or frame set.

Do not generate independent full-body images for every expression without the canonical base reference. That creates identity drift.

## Local Draft Location

Local generated drafts stay ignored under:

```text
artifacts/spirit-sequence-drafts/<character_id>/
```

The current draft packs are:

```text
artifacts/spirit-sequence-drafts/xingxi_spirit_rebuild/
artifacts/spirit-sequence-drafts/skyfeather_original_companion/
artifacts/spirit-sequence-drafts/cloudpuff_dragon_original/
```

These folders are not runtime packs and must not be referenced from `assets/companion/original_oc/portrait_manifest.json`.

## Pack Shape

Each local draft pack should contain:

```text
character.json
dialogue_style.json
character_card.md
provenance.md
qa_checklist.md
art_prompts.json
spirit_sequence_plan.json
imagegen_prompts/
  00_canonical_base.md
  idle_breath.md
  blink.md
  smile_micro.md
  thinking_micro.md
  surprised_micro.md
  sleepy_micro.md
generated/
  base_source.png
portraits/
  neutral_open.png
review/
  base-contact-sheet.png
```

`portrait_candidate.json` may describe the eventual complete expression target.
`base_portrait_candidate.json` is allowed for base-only QA before expression and blink frames exist.

## Frame Sets

Recommended near-term frame sets:

| State | Frames | FPS | Purpose |
| --- | ---: | ---: | --- |
| `idle_breath` | 8 | 8 | subtle breathing loop |
| `blink` | 5 | 12 | open, quarter, half, closed, open |
| `smile_micro` | 6 | 8 | small emotional response |
| `thinking_micro` | 6 | 8 | eyes shift or slight head impression |
| `surprised_micro` | 6 | 10 | eyes widen and tiny shoulder lift |
| `sleepy_micro` | 6 | 6 | slow eyelid lowering and soft breathing |

More frames are allowed when the sequence stays stable. More frames are not useful if the character identity drifts.

## Image Generation Rules

Use `$imagegen` for actual bitmap generation.

For each canonical base prompt:

- request an original Spirit/VN portrait;
- use a flat `#00ff00` chroma-key background;
- keep the subject bottom-centered with generous padding;
- forbid text, watermark, floor shadows, glow edges, red halo, camera drift, and franchise copying.

For each sequence prompt:

- attach the canonical base as the identity reference when the tool path supports image inputs;
- generate one state strip at a time;
- keep the same canvas, anchor, outfit, face, palette, proportions, and silhouette;
- animate only the state-specific micro-motion.

## QA Gates

A candidate can move forward only if:

- `python tools\art\validate_portrait_candidates.py <candidate.json> --contact-sheet <sheet.png>` passes;
- the alpha cutout has transparent corners and visible opaque pixels;
- the contact sheet shows no identity drift;
- the character stays bottom-aligned across frames;
- no frame has camera zoom, crop shift, body recomposition, changed outfit, or changed proportions;
- human visual QA approves the art.

Final runtime promotion still requires:

```powershell
python tools\portrait_promotion_gate.py path\to\complete_pack --report artifacts\portrait-promotion-report.json
python tools\portrait_pack_smoke.py path\to\complete_pack --report artifacts\portrait-pack-smoke-report.json --screenshot artifacts\portrait-pack-smoke-window.png
```

## IP Boundary

Only original or properly licensed character packs can be committed or distributed.

Requests based on existing characters must be transformed into original alternatives before they enter an open-source repository. Direct Ikaros, Nairong, or other third-party character replicas, names, official costumes, official lines, logos, or protected visual signatures must remain out of distributable assets unless explicit rights are available.

The current local alternatives are:

- `xingxi_spirit_rebuild`: original Xingxi rebuild candidate.
- `skyfeather_original_companion`: original sky/wing sci-fi companion alternative.
- `cloudpuff_dragon_original`: original soft dragon companion alternative.

