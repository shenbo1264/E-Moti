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

Provider snapshot checked on 2026-06-09:

| Route | Current free or low-friction signal | Project judgment |
| --- | --- | --- |
| Pika | Public pricing shows a free Basic plan with monthly video credits, 480p-only Pika 2.5 access, and 5s Text-to-Video / Image-to-Video free-tier credit options. | Best first retry when Gemini is blocked. Expect lower-resolution frames; normalize only if aspect ratio matches, then still run preflight. |
| Runway | Public pricing shows a free plan with one-time credits and Gen-4 Turbo image-to-video access. | Good second retry for a fast quality check. Use for a few neutral/blink attempts, not batch production. |
| Krea | Public pricing shows 100 free compute units per day; actual video-model access is account- and provider-dependent. | Useful as an extra daily attempt, but model access and export quality may vary by account. |
| LivePortrait | Open-source portrait animation route that uses a source portrait plus a restrained driving clip/template. | Best free technical fallback for subtle blink/breathing if online generators keep recomposing the body. It is not a text-to-video model. |
| Wan2.1 | Open-source repo supports image-to-video, ComfyUI/Diffusers/Gradio paths, and 480p/720p model variants. | Research-only for now. The I2V route is heavier than this project needs for a few blink frames. Prefer cloud/ComfyUI experiments, not local production on low-VRAM machines. |
| LTX-Video | Open-source repo supports image-to-video and has smaller/distilled model paths plus online demo links. | Research-only fallback after LivePortrait; useful if we later build a separate ComfyUI/cloud pipeline. |

Recommended fallback order for this project:

| Route | Use When | Notes |
| --- | --- | --- |
| Pika | Need the most direct free online image-to-video attempt. | Current public pricing shows free monthly video credits and free 480p image-to-video access, so expect low-resolution output and use frame normalization only when aspect ratio matches: <https://pika.art/pricing>. |
| Runway | Need a fast online image-to-video check. | Current public pricing shows one-time free credits and Gen-4 Turbo image-to-video access; confirm account credits and watermark/export limits before batch work: <https://runwayml.com/pricing>. |
| Krea | Need another free-credit online pass. | Current public pricing shows daily compute units and limited video-model access; expect low-resolution output and run the normalizer/preflight gates: <https://www.krea.ai/pricing>. |
| LivePortrait | Need a no-account fallback for subtle portrait motion. | This is not text-to-video; use the portrait as source image and a restrained driving clip/template for blink and breathing: <https://github.com/KwaiVGI/LivePortrait>. |
| Hailuo, Kling, PixVerse, Vidu | Need extra variations after the first routes fail. | Use the same `provider_prompts.md`; verify current account credits and watermark/export rules in the logged-in UI before spending time on batch runs. |
| Wan2.1 or LTX-Video | Need an open-source image-to-video experiment later. | These routes are heavier than LivePortrait and should stay research-only until a separate local/GPU/cloud workflow is approved: <https://github.com/Wan-Video/Wan2.1>, <https://github.com/Lightricks/ltx-video>. |

## Local LivePortrait Preflight

LivePortrait is an external open-source portrait-animation route, not a project dependency. Keep its checkout, weights, driving clips, videos, and generated frames under ignored local folders until a candidate survives QA.

Recommended local layout:

```text
tmp/liveportrait_research/LivePortrait/
tmp/liveportrait_research/drivers/blink_driver.mp4
artifacts/portrait-video-source/<set_id>/
```

Before running LivePortrait manually, check the source pack and local external setup:

```powershell
python tools\art\inspect_liveportrait_preflight.py `
  artifacts\portrait-video-source\xingxi-vn-neutral-20260608 `
  --liveportrait-root tmp\liveportrait_research\LivePortrait `
  --driving tmp\liveportrait_research\drivers\blink_driver.mp4 `
  --report artifacts\liveportrait-preflight-xingxi-vn-neutral.json `
  --markdown artifacts\liveportrait-preflight-xingxi-vn-neutral.md
```

The preflight only reads files. It does not clone LivePortrait, install packages, download weights, run inference, export frames, create a portrait candidate, or update runtime manifests. When blockers are found, the JSON and Markdown reports include `suggested_commands` such as weight download, driver-folder preparation, preflight rerun, FFmpeg install, or final inference commands. Treat those as manual next steps, not automation.

To include that ignored preflight result in a release/readiness review without rerunning inference:

```powershell
python tools\release_readiness_report.py `
  --liveportrait-preflight-report artifacts\liveportrait-preflight-xingxi-vn-neutral.json `
  --json artifacts\release-readiness-with-liveportrait-preflight.json `
  --markdown artifacts\release-readiness-with-liveportrait-preflight.md
```

For the external LivePortrait checkout, the official repository currently documents this HuggingFace weight download command:

```powershell
Push-Location tmp\liveportrait_research\LivePortrait
huggingface-cli download KlingTeam/LivePortrait --local-dir pretrained_weights --exclude "*.git*" "README.md" "docs"
Pop-Location
```

The project preflight checks the human-mode files listed by LivePortrait's official directory structure: `liveportrait/base_models/*.pth`, `liveportrait/retargeting_models/stitching_retargeting_module.pth`, `liveportrait/landmark.onnx`, and the two `insightface/models/buffalo_l/*.onnx` detectors. A checkout with only `pretrained_weights/.gitkeep` is not considered ready.

The driving input is also checked before inference. Empty files and obvious fake video files are rejected. MP4/MOV, WebM/MKV, AVI, and `.pkl` motion templates are accepted only when they pass a lightweight file-signature check.

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

Typical `next_action` values are `bundle_handoff`, `generate_ai_video`, `export_more_frames`, `replace_invalid_frames`, `normalize_frames`, `review_frame_warnings`, `process_frames`, `review_motion_candidate`, `regenerate_ai_video`, and `inspect_motion_candidate`.

The JSON and Markdown reports keep `next_action` for compatibility, and also include split `source_next_action` and `motion_next_action` values when source-frame cleanup and a stale motion-candidate failure both need attention. The Markdown report also includes an `Attention` section when a pack needs operator action. Common reasons are `normalizable_size_mismatch`, `size_mismatch`, `body_drift_warnings`, `failed_motion_extraction`, `missing_handoff`, `waiting_for_frames`, and `insufficient_frames`. When the next step is local tooling, the report also emits `suggested_commands` so the operator can rerun normalization, LivePortrait preflight, frame preflight, processing, or workflow inspection without reconstructing paths by hand.

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

The preflight report opens every PNG frame, rejects unreadable frames as `invalid_frames`, reports `insufficient_frames` below 3 readable PNGs, and flags size mismatches or high body drift as `ready_with_warnings` before extraction. Same-aspect lower-resolution frames report `next_action=normalize_frames`; non-normalizable size mismatch, crop, reframe, or body drift reports `next_action=review_frame_warnings`.

When preflight reports warnings, build a visual QA sheet for the specific source pack before deciding whether to normalize, regenerate, or process:

```powershell
python tools\art\portrait_video_frame_visual_qa.py `
  artifacts\portrait-video-source\xingxi-vn-neutral-20260608-normalized `
  --preview artifacts\portrait-video-frame-qa-xingxi-vn-neutral-normalized.png `
  --report artifacts\portrait-video-frame-qa-xingxi-vn-neutral-normalized.json
```

The sheet samples the reference and exported frames, and the JSON report records frame sizes plus body-drift values when the frame size matches the reference. It is a human QA aid only; it does not edit frames, create motion candidates, or approve assets.

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

If the visual QA report flags `light_edge_halo_risk`, create a sibling cleanup clone and review that clone instead of overwriting the original candidate:

```powershell
python tools\art\clean_portrait_candidate_edges.py artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\portrait_candidate.json --output artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion-edge-cleaned --report artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion-edge-cleaned\edge-cleanup-report.json
python tools\art\portrait_candidate_visual_qa.py artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion-edge-cleaned\portrait_candidate.json --preview artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion-edge-cleaned\preview\portrait-visual-qa.png --report artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion-edge-cleaned\portrait-visual-qa-report.json
python tools\art\portrait_candidate_decision_brief.py artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion-edge-cleaned\portrait_candidate.json --report artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion-edge-cleaned\portrait-decision-brief.json --markdown artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion-edge-cleaned\portrait-decision-brief.md
```

Do not update runtime `portrait_manifest.json` until the candidate passes strict promotion review and human visual QA.
