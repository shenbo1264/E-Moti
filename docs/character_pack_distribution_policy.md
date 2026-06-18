# Character Pack Distribution Policy

## Pack Classes

### Default Official Pack

`assets/companion/original_oc` is the runtime default. It is the stable fallback for demos, tests, and packaging.

### Optional Official Candidate

`assets/companion/xingxi_pixel_pet` is a QA-gated optional bundled candidate. It can be selected from the character library, but it does not replace the default pack unless a separate default-promotion package changes `DEFAULT_CHARACTER_ID` and passes release gates.

### Shareable After Review

A pack may use `distribution_boundary: "shareable_after_review"` only when provenance, license, manual QA, renderer assets, and validation reports are present.

### Local UGC Only

`local_ugc_only` packs may be imported locally but are not assumed to be safe for redistribution.

### Private Local Fanwork

`private_local_fanwork` packs are for private workflow testing. They must not be committed into `assets/companion/`.

## Current Fanwork Representatives

- Ikaros: local UGC/fanwork workflow representative only.
- Nairong: local UGC/fanwork workflow representative only.

## Release Rule

No third-party character pack enters bundled assets without explicit rights review and an updated release checklist.
