# Pixel Pet Manual QA And UGC Branching

This document records the P5 branch decision for the current pixel-pet route.

## Xingxi Candidate QA

Current candidate:

```text
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet/character_packs_drafts/xingxi_pixel_pet
```

Status:

- deterministic hatch validation: passed;
- hatch contact-sheet review: passed;
- pixel-pet pack validation: passed;
- runtime character-pack validation: passed;
- local user-pack import smoke: passed;
- default runtime manifest updated: no.

Manual visual decision:

```text
promotion_gate_candidate_after_jumping_failed_row_repair
```

Rows accepted for promotion-gate candidate review:

- `idle`
- `running-right`
- `running-left`
- `waving`
- `jumping`
- `failed`
- `waiting`
- `running`
- `review`

Rows repaired before promotion-gate candidate review:

- `jumping`: regenerated so frames 0 and 4 keep consistent crouch scale/proportions.
- `failed`: regenerated so the row no longer contains the abrupt oversized seated frame.

Conclusion: the current Xingxi pixel-pet pack can proceed to a promotion-gate package review. It is still not bundled, and `assets/companion/original_oc` plus default runtime manifests remain unchanged.

## UGC Branch Policy

The current UGC branches are workflow representatives only:

```text
ikaros_ugc_pixel_pet
nairong_ugc_pixel_pet
```

They must stay local unless rights are cleared. The intended draft boundary is:

```text
distribution_boundary = private_local_fanwork
```

Allowed:

- local prompt planning;
- user-provided local references;
- ignored QA artifacts under `artifacts/pixel-pet-sequence-drafts/`;
- local user-data import smoke.

Forbidden:

- official art, screenshots, logos, copied lines, audio, prompts, or source assets;
- generated final packs in tracked repo paths;
- default runtime manifest references;
- release packaging or open-source distribution.

## Branch Artifacts

Ignored local branch records:

```text
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet/manual_qa/
artifacts/pixel-pet-sequence-drafts/ikaros_ugc_pixel_pet/
artifacts/pixel-pet-sequence-drafts/nairong_ugc_pixel_pet/
```

These records are local evidence only. They must not be required to build or test the public repository.

## Next Gate

Before any bundled promotion:

1. Build a promotion-gate package from the current Xingxi candidate.
2. Re-run pixel-pet pack validation.
3. Re-run runtime character-pack validation.
4. Re-run local import smoke.
5. Run UI smoke tests and full `python -m pytest`.
6. Only then consider a separate package that updates bundled assets.
