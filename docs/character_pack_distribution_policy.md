# Character Pack Sharing Policy

## Pack Classes

### Default Official Pack

`assets/companion/xingxi_pixel_pet` is the runtime default. It is the visible bundled Xingxi pixel-pet pack for demos, tests, and packaging.

### Hidden Official Fallback

`assets/companion/original_oc` is the older original-character pack. It remains bundled as a compatibility fallback, but it is hidden from the visible character library.

### Shareable After Review

A pack may use `distribution_boundary: "shareable_after_review"` when it has provenance notes, basic QA, renderer assets, and a usable runtime manifest.

### Local UGC Only

`local_ugc_only` marks a user-created pack. In the current non-commercial demo route it can still be exported or shared after basic QA, but it should carry provenance/source notes so reviewers know what it is based on.

### Private Local Fanwork

`private_local_fanwork` marks a fanwork or third-party-inspired pack. In the current non-commercial demo route it is not blocked from public upload; keep a source note, generation notes, and QA evidence with the pack.

## Current Fanwork Representatives

- Ikaros: UGC/fanwork workflow representative for character switching, asset generation, and voice-profile testing.
- Nairong: UGC/fanwork workflow representative for pet-style character switching, asset generation, and voice-profile testing.

## Release Rule

For this non-commercial course demo, third-party/fanwork packs may be committed or exported when they pass the same runtime validation, basic QA, and provenance/source-note checks as original packs.
