# Portrait Video Generation SOP

This workflow prepares one local Gemini video task folder for each portrait set. It keeps generated videos, exported frames, and temporary candidates under ignored `artifacts/` paths until human QA approves them.

## Folder Contract

Each portrait set gets its own folder:

```text
artifacts/portrait-video-source/<set_id>/
  reference/
    neutral_open.png
  gemini_prompt.md
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

## Create A Source Pack

```powershell
python tools\art\create_portrait_video_source_pack.py `
  --source-image artifacts\portrait-candidate-xingxi-vn-20260607\portraits\neutral_open.png `
  --set-id xingxi-vn-neutral-20260608 `
  --character-name "Xingxi" `
  --source-label "VN neutral candidate"
```

Open `gemini_prompt.md`, upload the image under `reference/`, and use the prompt in Gemini.

## Gemini Output Rules

Ask Gemini for:

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

## Extract Blink And Idle Candidates

After frames are present, run the command from `source_pack.json`, or adapt this pattern:

```powershell
python tools\art\extract_portrait_motion_frames.py `
  --reference-image artifacts\portrait-video-source\xingxi-vn-neutral-20260608\reference\neutral_open.png `
  --frames-dir artifacts\portrait-video-source\xingxi-vn-neutral-20260608\frames `
  --output-dir artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion `
  --report artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\candidate-motion-frame-report.json `
  --source-tool "Gemini video" `
  --generation-prompt "see artifacts\portrait-video-source\xingxi-vn-neutral-20260608\gemini_prompt.md"
```

Then run visual QA and the decision brief before any manifest promotion:

```powershell
python tools\art\portrait_candidate_visual_qa.py artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\portrait_candidate.json --preview artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\preview\portrait-visual-qa.png --report artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\portrait-visual-qa-report.json
python tools\art\portrait_candidate_decision_brief.py artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\portrait_candidate.json --report artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\portrait-decision-brief.json --markdown artifacts\portrait-candidate-xingxi-vn-neutral-20260608-motion\portrait-decision-brief.md
```

Do not update runtime `portrait_manifest.json` until the candidate passes strict promotion review and human visual QA.
