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
| Runway | Need a fast online image-to-video check. | Use the official pricing/account page to confirm current free credits or watermarks before batch work: <https://runwayml.com/pricing>. |
| Hailuo | Need another online image-to-video pass with simple prompt control. | Use the image-to-video tool and confirm account limits in the current UI: <https://hailuoai.video/tools/image-to-video>. |
| Vidu | Need an anime-friendly online reference/image-to-video attempt. | Confirm current free or trial allowance before use: <https://www.vidu.com/pricing>. |
| LivePortrait | Need a no-account fallback for subtle portrait motion. | This is not text-to-video; use the portrait as source image and a restrained driving clip/template for blink and breathing: <https://github.com/KwaiVGI/LivePortrait>. |
| Pika, Kling, PixVerse, Krea | Need extra variations after the first three routes fail. | Use the same `provider_prompts.md`; verify current account credits and watermark/export rules before spending time on batch runs. |
| Wan2.1 or LTX-Video | Need an open-source image-to-video experiment later. | These routes are heavier than LivePortrait and should stay research-only until a separate local/GPU/cloud workflow is approved: <https://github.com/Wan-Video/Wan2.1>, <https://github.com/Lightricks/ltx-video>. |

For blink and breathing, prefer conservative outputs over cinematic motion:

1. Generate 3-4 seconds only.
2. Reject clips with camera movement, pose changes, mouth talking, or expression drift.
3. Export PNG frames back into the matching `frames/` folder.
4. Run the frame preflight before extraction.
5. Keep the runtime manifest unchanged until the promotion gate and human QA pass.

## Bundle Handoff Zips

To create one zip per source pack for AI video handoff:

```powershell
python tools\art\bundle_portrait_video_source_packs.py `
  artifacts\portrait-video-source `
  --output-dir artifacts\portrait-video-handoff `
  --report artifacts\portrait-video-handoff-report.json
```

Each zip contains `reference/`, `gemini_prompt.md`, `provider_prompts.md`, `source_pack.json`, and `AI_VIDEO_HANDOFF_README.md`. It does not contain generated videos or exported frames.

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

Typical `next_action` values are `bundle_handoff`, `generate_ai_video`, `export_more_frames`, `replace_invalid_frames`, `review_frame_warnings`, `process_frames`, and `review_motion_candidate`.

## AI Video Output Rules

Ask the selected provider for:

- static camera;
- same character, outfit, pose, and proportions;
- subtle breathing;
- one natural blink;
- slight hair sway only;
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

The preflight report opens every PNG frame, rejects unreadable frames as `invalid_frames`, reports `insufficient_frames` below 3 readable PNGs, and flags size mismatches as `ready_with_warnings` for manual review before extraction.

## Extract Blink And Idle Candidates

To check all source folders:

```powershell
python tools\art\batch_process_portrait_video_source_packs.py `
  artifacts\portrait-video-source `
  --report artifacts\portrait-video-source-batch-report.json
```

The batch report shows `ready` for folders with at least 3 exported PNG frames, `insufficient_frames` for folders with 1-2 PNG frames, and `waiting_for_frames` for folders that still need AI video output.

To process every ready folder:

```powershell
python tools\art\batch_process_portrait_video_source_packs.py `
  artifacts\portrait-video-source `
  --process-ready
```

To process one folder after frames are present, run:

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
