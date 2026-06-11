# Pixel Pet Sequence SOP

This is the corrected near-term art route for E-Moti's sequence-frame work.

The route follows the `hatch-pet` workflow idea: compact pixel-adjacent pet art, one canonical base, grounded animation rows, contact-sheet QA, and repair only the failed state. It is not the refined VN portrait route.

## Route

Use small-pet, pixel-adjacent presentation for sequence-frame production:

- compact mascot proportions;
- readable silhouette at small desktop size;
- thick 1-2 px dark outline;
- flat cel shading and limited palette;
- simple expressive face;
- short limbs or simple appendages;
- no painterly key art, high-detail VN illustration, glossy 3D, soft gradients, or complex hair/cloth strands.

This style is chosen because it is practical for consistent multi-frame generation.

## Local Draft Location

All generated drafts stay ignored:

```text
artifacts/pixel-pet-sequence-drafts/<character_id>/
```

Do not reference these drafts from runtime manifests until final QA and promotion are complete.

## Character Tracks

The current three local tracks are:

```text
xingxi_pixel_pet
ikaros_ugc_pixel_pet
nairong_ugc_pixel_pet
```

Track policy:

- `xingxi_pixel_pet`: original Xingxi redesign, eligible for future open-source promotion after QA.
- `ikaros_ugc_pixel_pet`: local UGC fanwork representative for Ikaros from Heaven's Lost Property. Not distributable without rights.
- `nairong_ugc_pixel_pet`: local UGC pet-style representative for Nairong. Not distributable without rights.

UGC tracks are for local workflow validation only. Their pixel-pet draft boundary may be `local_ugc_only` or the stricter `private_local_fanwork`. Do not commit their generated images, final packs, official names in release assets, copied visual signatures, official lines, logos, screenshots, or source art.

## Workflow

1. Run `hatch-pet` preparation for each track.
2. Generate the base job with `$imagegen`.
3. Record the selected base using `record_imagegen_result.py`.
4. Generate rows using the canonical base and layout guide as references.
5. Start with `idle` and `running-right` or another minimal loop used as the identity check.
6. Only mirror or derive rows when visual semantics remain correct.
7. Finalize through the deterministic hatch-pet scripts.
8. Inspect contact sheet, validation JSON, and preview videos.

Do not hand-draw missing rows with local scripts. Deterministic scripts may assemble, validate, crop, preview, or package generated rows, but the actual visuals come from `$imagegen`.

## Prompt Rules

Base prompts must say:

- small pixel-adjacent desktop pet;
- compact chibi/mascot proportions;
- thick readable outline;
- flat cel shading;
- clean solid chroma-key background;
- transparent-cleanup friendly;
- no text, watermark, shadow, glow, detached effects, or frame labels.

Row prompts must preserve:

- same head shape;
- same face;
- same palette;
- same outfit/markings;
- same proportions;
- same silhouette;
- same outline weight.

## Minimum QA

A candidate is not usable until:

```powershell
python tools\art\review_pixel_pet_base.py artifacts\pixel-pet-sequence-drafts\<character_id>\hatch_run\decoded\base.png --character-id <character_id> --prompt artifacts\pixel-pet-sequence-drafts\<character_id>\hatch_run\prompts\base-pet.md --character-definition artifacts\pixel-pet-sequence-drafts\<character_id>\character_definition.json --decision accepted_for_row_testing --output-dir artifacts\pixel-pet-sequence-drafts\<character_id>\review\base-review
python tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\<character_id>\review\<state>-frames --state <state> --expected-frames <count> --require-components --output-dir artifacts\pixel-pet-sequence-drafts\<character_id>\review\<state>-row-review
python <hatch-pet>\scripts\finalize_pet_run.py --run-dir artifacts\pixel-pet-sequence-drafts\<character_id>\hatch_run
python tools\validate_pixel_pet_pack.py path\to\character_packs_drafts\<character_id>
```

produces:

```text
review/base-review/base-review.json
review/base-review/base-review.md
review/base-review/base-review.png
review/<state>-row-review/<state>-row-review.json
review/<state>-row-review/<state>-row-review.md
review/<state>-row-review/<state>-row-review.png
final/spritesheet.png
final/spritesheet.webp
final/validation.json
qa/contact-sheet.png
qa/review.json
qa/videos/
```

The base review is ignored evidence only. A warning about a near but non-flat `#FF00FF` background means the candidate may continue to row testing, but the background must be cleaned before slicing or promotion.
The row review is also ignored evidence only. It must not edit `decoded/`, `imagegen-jobs.json`, runtime manifests, or character packs. A row that falls back to slot extraction should be repaired or regenerated before full-sheet production unless a human explicitly accepts the risk.

Human QA must reject rows with:

- changed character identity;
- changed costume or species;
- painterly non-pixel style drift;
- cropped body parts;
- repeated static tiles pretending to animate;
- white backgrounds or visible guide boxes;
- detached effects, motion lines, dust, glow, or shadows;
- UGC characters becoming too close for open-source distribution.

## Runtime Boundary

The existing sprite fallback and portrait renderer stay untouched during draft work.

Do not update:

- `assets/companion/original_oc/portrait_manifest.json`;
- runtime character manifests;
- save files;
- LLM expression contracts;
- packaging scripts.

Promotion is a separate package after a full candidate passes QA.

## Promotion Gate

After a pixel-pet candidate passes row repair, manual QA, pack validation, and local import smoke, run the strict promotion-gate report before any bundled asset change:

```powershell
python tools\pixel_pet_promotion_gate.py path\to\character_packs_drafts\<character_id> --manual-qa path\to\manual_qa.json --report artifacts\pixel-pet-sequence-drafts\<character_id>\promotion_gate\pixel_pet_promotion_gate_report.json
```

The gate is still read-only. A passing report means the candidate can enter a separate bundled-asset promotion package; it does not update `assets/companion/`, runtime manifests, saves, packaging scripts, or LLM behavior.
