# Character Pack Distribution Policy

## Pack Classes

### Default Official Pack

`assets/companion/xingxi_pixel_pet` is the runtime default. It is the visible bundled Xingxi pixel-pet pack for demos, tests, and packaging.

### Hidden Official Fallback

`assets/companion/original_oc` is the older original-character pack. It remains bundled as a compatibility fallback, but it is hidden from the visible character library.

### Shareable After Review

A pack may use `distribution_boundary: "shareable_after_review"` only when provenance, license, manual QA, renderer assets, and validation reports are present.

### Local UGC Only

`local_ugc_only` packs may be imported locally but are not assumed to be safe for redistribution.

### Private Local Fanwork

`private_local_fanwork` packs are for private workflow testing. They must not be committed into `assets/companion/`.

## Current Fanwork Representatives

- Ikaros: local UGC/fanwork workflow representative only; private preview package only unless rights are cleared.
- Nairong: local UGC/fanwork workflow representative only; private preview package only unless rights are cleared.

## Release Rule

No third-party character pack enters bundled assets without explicit rights review and an updated release checklist.
