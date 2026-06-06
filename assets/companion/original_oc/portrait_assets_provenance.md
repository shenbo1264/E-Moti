# Xingxi Portrait Assets Provenance

Date: 2026-06-06

## Scope

These files are a temporary portrait renderer smoke baseline for the original E-Moti character Xingxi:

- `portraits/neutral.png`
- `portraits/smile.png`
- `portraits/thinking.png`
- `portraits/surprised.png`
- `portraits/sad.png`
- `portraits/sleepy.png`
- `preview/portrait-contact-sheet.png`
- `portrait_manifest.json`

## Source

The expression sheet was generated with Codex built-in image generation, using the existing original Xingxi alpha reference in this repository as the visual reference:

```text
assets/companion/original_oc/live2d_sources/xingxi_live2d_cutting_reference_alpha.png
```

The generated candidate sheet was saved by Codex in its local `generated_images` store outside this repository. The local absolute path is intentionally omitted from the public asset note.

The source sheet used a flat chroma-key background and was split into six expression images. The background was removed locally with the Codex `imagegen` skill's `remove_chroma_key.py` helper.

## Prompt Summary

The image generation prompt requested a 3x2 expression sheet for the same original anime-style desktop companion girl, preserving Xingxi's white bob hair, blue accents, star hairpin, blue star-themed hoodie outfit, amber eyes, and celestial accessories.

Requested expressions:

- neutral
- smile
- thinking
- surprised
- sad
- sleepy

Negative constraints included no fan art, no existing franchise style copying, no logo, no watermark, and no text.

## QA Notes

- All final portrait files are PNG RGBA.
- All final portrait files have transparent corners.
- Images are 512x512 and within the pack validator size limit.
- The six expressions are suitable only for testing the portrait renderer contract.
- These images are not acceptable as the final Spirit/GalGame art direction because they are square Q-style assets, not tall visual-novel standing portraits.
- Do not treat this set as final release art. Replace it with an approved high-body VN portrait set before public visual promotion.
