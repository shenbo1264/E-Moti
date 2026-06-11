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
keep_as_local_import_candidate_do_not_promote_default_assets
```

Rows accepted for local import smoke:

- `idle`
- `running-right`
- `running-left`
- `waving`
- `waiting`
- `running`
- `review`

Rows requiring attention before bundled promotion:

- `jumping`: frames 0 and 4 have a visible body scale/proportion jump.
- `failed`: frame 4 changes silhouette and scale more than neighboring frames.

Conclusion: the current Xingxi pixel-pet pack is good enough for ignored local import testing, but it is not promotion-ready for `assets/companion/original_oc` or any default runtime manifest.

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

1. Repair or explicitly accept the Xingxi `jumping` and `failed` rows.
2. Re-run pixel-pet pack validation.
3. Re-run runtime character-pack validation.
4. Re-run local import smoke.
5. Run UI smoke tests and full `python -m pytest`.
6. Only then consider a promotion package that updates bundled assets.
