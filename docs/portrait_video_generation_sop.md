# Portrait AI Video Generation SOP

This workflow prepares one local AI video task folder for each portrait set. It keeps generated videos, exported frames, and temporary candidates under ignored `artifacts/` paths until human QA approves them.

## Folder Contract

Each portrait set gets its own folder:

```text
artifacts/portrait-video-source/<set_id>/
  reference/
    neutral_open.png
  gemini_prompt.md
  provider_prompts.md
  source_pack.json
  video/
    README.md
  frames/
    README.md
```

Use a stable `set_id`, for example:

```text
xingxi-vn-neutral-20260608
xingxi-vn-smile-20260608
```

## Create Source Packs

Recommended batch command for one portrait candidate:

```powershell
python tools\art\create_portrait_video_source_packs_from_candidate.py `
  artifacts\portrait-candidate-xingxi-vn-20260607\portrait_candidate.json `
  --set-id-prefix xingxi-vn `
  --set-id-suffix 20260608 `
  --character-name "Xingxi" `
  --source-label-prefix "VN expression candidate" `
  --report artifacts\portrait-video-source-create-report.json
```

This creates one source folder per expression open/static portrait, for example `xingxi-vn-neutral-20260608` and `xingxi-vn-smile-20260608`. Blink-half and blink-closed frames are not treated as separate Gemini tasks.

Single-image fallback command:

```powershell
python tools\art\create_portrait_video_source_pack.py `
  --source-image artifacts\portrait-candidate-xingxi-vn-20260607\portraits\neutral_open.png `
  --set-id xingxi-vn-neutral-20260608 `
  --character-name "Xingxi" `
  --source-label "VN neutral candidate"
```

Open `provider_prompts.md`, upload the image under `reference/`, and use the matching prompt in Pika, Hailuo, Kling, PixVerse, Runway, Vidu, LivePortrait, or Gemini. `gemini_prompt.md` remains the baseline prompt.

## When Gemini Is Unavailable

Free and trial video quotas change often. Treat provider availability as account-local state, not a project guarantee. Keep every generated video and exported frame under ignored `artifacts/` folders until a candidate survives QA.

Recommended fallback order for this project:

| Route | Use When | Notes |
| --- | --- | --- |
| Pika | Need the most direct free online image-to-video attempt. | Current public pricing shows free monthly video credits and free 480p image-to-video access, so expect low-resolution output and use frame normalization only when aspect ratio matches: <https://pika.art/pricing>. |
| Runway | Need a fast online image-to-video check. | Current public pricing shows one-time free credits and Gen-4 Turbo image-to-video access; confirm account credits and watermark/export limits before batch work: <https://runwayml.com/pricing>. |
| Krea | Need another free-credit online pass. | Current public pricing shows daily compute units and limited video-model access; expect low-resolution output and run the normalizer/preflight gates: <https://www.krea.ai/pricing>. |
| LivePortrait | Need a no-account fallback for subtle portrait motion. | This is not text-to-video; use the portrait as source image and a restrained driving clip/template for blink and breathing: <https://github.com/KwaiVGI/LivePortrait>. |
| Hailuo, Kling, PixVerse, Vidu | Need extra variations after the first routes fail. | Use the same `provider_prompts.md`; verify current account credits and watermark/export rules in the logged-in UI before spending time on batch runs. |
| Wan2.1 or LTX-Video | Need an open-source image-to-video experiment later. | These routes are heavier than LivePortrait and should stay research-only until a separate local/GPU/cloud workflow is approved: <https://github.com/Wan-Video/Wan2.1>, <https://github.com/Lightricks/ltx-video>. |

For blink and breathing, prefer conservative outputs over cinematic motion:

1. Generate 3-4 seconds only.
2. Reject clips with camera movement, pose changes, mouth talking, or expression drift.
3. Export PNG frames back into the matching `frames/` folder.
4. Run the frame preflight before extraction.
5. Keep the runtime manifest unchanged until the promotion gate and human QA pass.

Some free or trial providers only export lower-resolution vertical clips. If the exported PNG frames have the same aspect ratio as the reference image, clone the source pack and resize those frames into a normalized ignored source pack instead of overwriting the originals:

```powershell
python tools\art\normalize_portrait_video_source_frames.py `
  artifacts\portrait-video-source\xingxi-vn-neutral-20260608 `
  --output-pack-dir artifacts\portrait-video-source\xingxi-vn-neutral-20260608-normalized `
  --report artifacts\portrait-video-frame-normalization.json
```

This is only a canvas-size repair step. It rejects aspect-ratio mismatches, preserves the original provider frames, and still requires the normalized source pack to pass frame preflight before extraction.

## Bundle Handoff Zips

To create one zip per source pack for AI video handoff:

```powershell
python tools\art\bundle_portrait_video_source_packs.py `
  artifacts\portrait-video-source `
  --output-dir artifacts\portrait-video-handoff `
  --report artifacts\portrait-video-handoff-report.json
```

Each zip contains `reference/`, `gemini_prompt.md`, `provider_prompts.md`, `source_pack.json`, and `AI_VIDEO_HANDOFF_README.md`. The README repeats the exact required frame size, the frame preflight command, and tells the operator to regenerate video when frames report `ready_with_warnings`. It does not contain generated videos or exported frames.

## Inspect Workflow Status

To see every source pack, frame preflight status, handoff zip, motion candidate, and next action:

```powershell
python tools\art\inspect_portrait_video_workflow.py `
  artifacts\portrait-video-source `
  --handoff-dir artifacts\portrait-video-handoff `
  --candidate-root artifacts `
  --report artifacts\portrait-video-workflow-report.json `
  --markdown artifacts\portrait-video-workflow-report.md
```

Typical `next_action` values are `bundle_handoff`, `generate_ai_video`, `export_more_frames`, `replace_invalid_frames`, `review_frame_warnings`, `process_frames`, `review_motion_candidate`, `regenerate_ai_video`, and `inspect_motion_candidate`.

## AI Video Output Rules

Ask the selected provider for:

- static camera;
- same canvas size and aspect ratio as the reference image;
- same character, outfit, pose, and proportions;
- no crop, zoom-out, resize, reframe, or body recomposition;
- subtle breathing;
- one natural blink;
- hands, feet, shoulders, hips, and silhouette stay fixed;
- only eyelids, tiny chest breathing, and slight hair tips may move;
- no text, logo, watermark, scene change, zoom, hand gesture, or mouth talking.

Download the raw video into `video/`. Export sequential PNG frames into `frames/`:

```text
frame_0001.png
frame_0002.png
frame_0003.png
```

Before processing, preflight the exported PNG frames:

```powershell
python tools\art\inspect_portrait_video_source_frames.py `
  artifacts\portrait-video-source `
  --report artifacts\portrait-video-frame-preflight.json
```

The preflight report opens every PNG frame, rejects unreadable frames as `invalid_frames`, reports `insufficient_frames` below 3 readable PNGs, and flags size mismatches or high body drift as `ready_with_warnings` for manual review before extraction.

If the only blocking issue is lower-resolution same-aspect frames from a free provider, normalize into a sibling source pack and preflight that sibling before processing:

```powershell
python tools\art\normalize_portrait_video_source_frames.py `
  artifacts\portrait-video-source\xingxi-vn-neutral-20260608 `
  --output-pack-dir artifacts\portrait-video-source\xingxi-vn-neutral-20260608-normalized `
  --report artifacts\portrait-video-frame-normalization.json

python tools\art\inspect_portrait_video_source_frames.py `
  artifacts\portrait-video-source `
  --report artifacts\portrait-video-frame-preflight.json
```

Do not use normalization for cropped, reframed, widened, or recomposed output. Those need regeneration, not resizing.

## Extract Blink And Idle Candidates

To check all source folders:

```powershell
python tools\art\batch_process_portrait_video_source_packs.py `
  artifacts\portrait-video-source `
  --report artifacts\portrait-video-source-batch-report.json
```

The batch report shows `ready` only when frame preflight passes without warnings, `ready_with_warnings` when exported frames need review before extraction, `insufficient_frames` for folders with 1-2 PNG frames, and `waiting_for_frames` for folders that still need AI video output.

To process every ready folder:

```powershell
python tools\art\batch_process_portrait_video_source_packs.py `
  artifacts\portrait-video-source `
  --process-ready
```

`--process-ready` skips `ready_with_warnings`. For size mismatches or obvious pose drift, regenerate the AI video or replace frames first instead of forcing a motion candidate.

To process one folder after frame preflight reports `ready`, run:

```powershell
python tools\art\process_portrait_video_source_pack.py `
  artifacts\portrait-video-source\xingxi-vn-neutral-20260608 `
  --output-dir artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion
```

The processor reads `source_pack.json`, uses `gemini_prompt.md` as provenance text, and calls the lower-level frame extractor.

Then run visual QA and the decision brief before any manifest promotion:

```powershell
python tools\art\portrait_candidate_visual_qa.py artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\portrait_candidate.json --preview artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\preview\portrait-visual-qa.png --report artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\portrait-visual-qa-report.json
python tools\art\portrait_candidate_decision_brief.py artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\portrait_candidate.json --report artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\portrait-decision-brief.json --markdown artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\portrait-decision-brief.md
```

Do not update runtime `portrait_manifest.json` until the candidate passes strict promotion review and human visual QA.
