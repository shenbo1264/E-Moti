# Ikaros Local Draft Provenance

Status: formal local art asset draft, not open-source/import-ready.
Policy: local_fanwork.
Local fanwork: user-authorized private draft only; do not commit, bundle, or distribute.

Source character: Ikaros / Sora no Otoshimono

## Source Notes
- Sora No Otoshimono Wiki - Ikaros: Public profile describes Ikaros as a first-generation Angeloid, Alpha type, battle class, with variable wings and Uranus Queen / Sky Queen aliases. - https://soranootoshimono.fandom.com/wiki/Ikaros
- Heaven's Lost Property - Wikipedia: Series synopsis describes Ikaros as a winged female humanoid from Synapse who falls from the sky and declares herself Tomoki's servant. - https://en.wikipedia.org/wiki/Heaven%27s_Lost_Property
- Manga Wiki - Sora no Otoshimono: Public summary notes the Pet-Class Angeloid Type Alpha bond to Tomoki, symbolized by an invisible chain from collar to hand. - https://manga.fandom.com/wiki/Sora_no_Otoshimono

## Generated Asset Run
- Run folder: `.local-notes/hatch_runs/ikaros-local-fanwork`.
- Generation path: `$imagegen` fallback CLI with `gpt-image-2`, using generated base art plus layout guides for row strips.
- Final atlas copied from `final/spritesheet.png` to this draft as `spritesheet.png`.
- Contact sheet copied from `qa/contact-sheet.png` to `preview/contact-sheet.png`.
- QA note: `idle` and `waiting` used slot slicing after visual inspection; all other rows used component extraction.

## Red-Edge Cleanup
- Original cleaned backup: `.local-notes/character_drafts/ikaros_local_fanwork/backup_20260605-rededge-before/`.
- Applied edge-only magenta despill and alpha cleanup to `spritesheet.png` after animated preview revealed chroma-key edge fringing.
- Verification after cleanup: atlas geometry still validates as `1536x1872 RGBA`; magenta-like visible pixels dropped to zero in the atlas metric.
- Neutral preview without red grid: `preview/contact-sheet-neutral.png`.
- GIF previews are convenience QA files only; GIF transparency can still exaggerate hard pixel edges compared with the RGBA atlas used by the app.
