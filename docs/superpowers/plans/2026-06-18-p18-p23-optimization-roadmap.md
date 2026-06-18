# P18-P23 Optimization Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continue from the verified P17 gate and turn E-Moti from a reproducible desktop-pet demo into a more convincing AI-first companion while keeping the local pet state machine deterministic and safe.

**Architecture:** Keep the existing controller, typed event, snapshot, character pack, and renderer boundaries. LLM providers may improve speech, expression cues, motion cues, diagnostics, and read-only moment staging, but local code remains the only owner of saves, growth state, inventory, relationship, memory, goals, coins, and character namespaces.

**Tech Stack:** Python 3.11, PySide6, pytest, Pillow, existing OpenAI-compatible expression clients, existing pixel-pet validation tools, existing Windows packaging scripts.

---

## Current Status Verified On 2026-06-18

### Repository State

- Working directory: `D:\学工文档\光核\电子宠物\E-Moti_demo`.
- Branch: `codex/demo-worktree-cleanup`.
- Remote used for the public PR: `origin` -> `https://github.com/shenbo1264/E-Moti.git`.
- Remote default branch: `main`.
- Current branch still reports its old upstream as `private-origin/codex/demo-worktree-cleanup [gone]`; pushing the PR branch to `origin` is therefore part of the publish step.
- Working tree before this document package: `M AGENTS.md` only.
- `AGENTS.md` contains local agent memory context and is intentionally excluded from this PR package.

### Latest Product Gate

The P17 gate in `docs/final_release_gate_2026-07.md` records:

- `original_oc` remains the default bundled character.
- `xingxi_pixel_pet` is an optional bundled official candidate, not the default.
- Ikaros and Nairong remain local UGC/fanwork workflow representatives only and are not bundled.
- Live2D, LivePortrait, AI-video, and VN portrait routes remain research or later renderer paths.
- Live DeepSeek expression cue probe passed at that gate with `5/5` cue cases, `fallback_count=0`, and `changed_fields=[]`.
- The P16 confused/shy pixel row candidate passed ignored artifact row review but is not promoted into runtime assets.
- Windows app and installer artifacts were validated at the gate, but not rebuilt in P17 because packaging inputs did not change.

### Fresh Verification For This Roadmap Package

Commands run before writing this plan:

```powershell
git status --short --untracked-files=all
git branch --show-current
git remote -v
git log --oneline --decorate -14
gh --version
gh auth status
gh repo view --json nameWithOwner,defaultBranchRef,url
python -m pytest
```

Observed result:

- `python -m pytest`: `870 passed`.
- GitHub CLI is installed and authenticated as `shenbo1264`.
- GitHub target repository resolves to `shenbo1264/E-Moti`, default branch `main`.

### What Is Playable Now

The project is currently a runnable and test-covered Windows desktop companion demo:

- Control panel mode and desktop pet mode are covered by tests.
- Tray behavior, hiding/restoring, pet-mode entry, and exit paths are covered.
- Local actions, shop, inventory, relationship, memory, session goals, deterministic moments, dialogue, and snapshot surfaces are covered.
- Character library and pack switching are covered.
- The optional LLM expression path is wired through typed event validation and state mutation guards.
- Optional screen observation, search, TTS, and ASR remain behind settings and boundary tests.

### Remaining Product Gap

The project can be demonstrated and reproduced, but the next quality bar should focus on perceived companion intelligence:

- AI setup and failure recovery need to be easier for a non-developer to understand inside the app.
- Current AI checks prove safety and cue coverage; they do not yet prove sustained multi-turn charm.
- Short-session gameplay exists, but needs more visible feedback, balancing, and repeated-play pacing.
- The pixel-pet route has validated assets, but the newest expressive row candidate still needs human visual approval before runtime promotion.
- Public release docs are good enough for a developer, but first-run onboarding and demo operator flow can be clearer.

---

## Recommended Execution Order

```text
P18 -> P19 -> P20 -> P21 -> P22 -> P23
```

Rationale:

- P18 first: tighten release and onboarding so an external reviewer can run the current project without private context.
- P19 next: make AI provider setup visible and recoverable because AI is the core product claim.
- P20 next: measure multi-turn companion quality before adding more features.
- P21 next: tune the gameplay loop using the measured AI behavior.
- P22 next: promote only approved pixel art and avoid unreviewed asset churn.
- P23 last: polish UGC import after the official path is stable.

---

## File Responsibility Map

- `README.md`: public entry point, setup, run, test, release gates, and active roadmap links.
- `docs/open_source_release_checklist.md`: public release checklist and distribution boundary reminders.
- `docs/llm_expression_operations.md`: provider setup, diagnostics, smoke commands, and live/local fallback guidance.
- `docs/final_release_gate_2026-07.md`: current P17 release evidence; do not rewrite historical results.
- `docs/superpowers/plans/2026-06-18-p18-p23-optimization-roadmap.md`: this implementation plan.
- `src/guanghe_companion/expression_settings.py`: provider presets, defaults, and settings normalization.
- `src/guanghe_companion/expression_clients.py`: provider HTTP clients and public error classification.
- `src/guanghe_companion/expression_diagnostics.py`: typed provider test result generation.
- `src/guanghe_companion/expression_diagnostic_view.py`: user-facing diagnostic labels and actions.
- `src/guanghe_companion/llm_smoke.py`: reusable smoke scenario and review logic.
- `tools/llm_provider_matrix.py`: CLI provider readiness matrix.
- `tools/llm_expression_cue_probe.py`: live cue probe for expression and motion coverage.
- `src/guanghe_companion/companion_moments.py`: deterministic moment selection.
- `src/guanghe_companion/session_goals.py`: deterministic short-session goals.
- `src/guanghe_companion/controller.py`: state owner, event application, snapshots, moments, and session goals.
- `src/guanghe_companion/snapshot.py`: typed UI/export snapshot surface.
- `src/guanghe_companion/app.py`: PySide6 UI, diagnostics panels, character library, and desktop pet surface.
- `src/guanghe_companion/character_library_view_model.py`: character library labels, readiness, provenance, and QA status.
- `assets/companion/xingxi_pixel_pet/`: optional official candidate assets. Modify only in a dedicated asset promotion package.
- `tools/art/review_pixel_pet_row_candidate.py`: ignored row candidate QA.
- `tools/validate_pixel_pet_pack.py`: runtime pixel pack validation.
- `tools/art/pixel_pet_visual_qa.py`: visual edge/alpha QA.
- `tools/pixel_pet_emote_mapping_check.py`: LLM expression-to-motion coverage gate.
- `tools/release_readiness_report.py`: aggregate release readiness gate.
- `tests/`: every production change must start with a focused failing test and end with focused tests plus full `python -m pytest`.

---

## P18: Public Reviewer Onboarding And Release Entry Point

**Purpose:** Make the current repository understandable to a fresh reviewer who wants to run, test, and evaluate the demo without reading private chat context.

**Out of scope:** Runtime behavior changes, default character promotion, new art assets, provider calls.

**Files:**

- Modify: `README.md`
- Modify: `docs/open_source_release_checklist.md`
- Create or modify: `docs/demo_operator_quickstart.md`
- Test: `tests/test_repository_hygiene.py`

- [ ] **Step 1: Add a failing hygiene test for the public quickstart link**

Add this test to `tests/test_repository_hygiene.py`:

```python
def test_readme_links_demo_operator_quickstart():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    quickstart = REPO_ROOT / "docs" / "demo_operator_quickstart.md"

    assert "docs\\demo_operator_quickstart.md" in readme
    assert quickstart.is_file()
```

Run:

```powershell
python -m pytest tests\test_repository_hygiene.py::test_readme_links_demo_operator_quickstart -q
```

Expected: `FAIL` because the quickstart does not exist or is not linked yet.

- [ ] **Step 2: Create the demo operator quickstart**

Create `docs/demo_operator_quickstart.md` with these sections:

```markdown
# Demo Operator Quickstart

## What This Demo Shows

- A Windows desktop companion pet with local deterministic growth state.
- Optional AI expression that can produce speech, expression cues, and motion cues through typed events.
- Character switching between bundled packs, with distribution boundaries visible.

## What This Demo Does Not Do

- It is not a productivity supervisor or course monitor.
- It does not let LLMs mutate saves, inventory, memory, relationship, goals, coins, or growth state.
- It does not use background listening, wake words, mouse control, keyboard control, clipboard control, or window control.

## Five-Minute Demo Flow

1. Run `python -m guanghe_companion.app`.
2. Check status, action, shop, inventory, memory, dialogue, settings, and character library views.
3. Switch to desktop pet mode.
4. Hide and restore from the tray.
5. If a valid provider key or local provider is available, run the LLM provider test and one dialogue turn.

## Verification Commands

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\llm_provider_matrix.py --dry-run --report artifacts\llm_smoke\provider-matrix-dry-run.json --markdown artifacts\llm_smoke\provider-matrix-dry-run.md
```

## Expected Current State

- `original_oc` is the default pack.
- `xingxi_pixel_pet` is an optional official candidate.
- Live AI expression depends on a configured provider or local OpenAI-compatible server.
```

- [ ] **Step 3: Link the quickstart from README**

Add this line near the current roadmap section in `README.md`:

```markdown
type docs\demo_operator_quickstart.md
```

- [ ] **Step 4: Verify and commit**

Run:

```powershell
python -m pytest tests\test_repository_hygiene.py -q
python -m pytest
git diff --check
git add README.md docs\demo_operator_quickstart.md tests\test_repository_hygiene.py
git commit -m "docs: add demo operator quickstart"
```

Acceptance:

- A fresh reviewer can identify how to run, test, and evaluate the current demo.
- The quickstart does not claim AI is live unless a provider is configured and tested.

---

## P19: AI Provider Setup UX And Local Fallback

**Purpose:** Make LLM setup practical in the app, not just through terminal commands.

**Out of scope:** Letting LLM own state, adding background listeners, storing secrets in tracked files.

**Files:**

- Modify: `src/guanghe_companion/expression_settings.py`
- Modify: `src/guanghe_companion/expression_diagnostics.py`
- Modify: `src/guanghe_companion/expression_diagnostic_view.py`
- Modify: `src/guanghe_companion/app.py`
- Modify: `docs/llm_expression_operations.md`
- Test: `tests/test_expression_settings.py`
- Test: `tests/test_expression_diagnostics.py`
- Test: `tests/test_expression_diagnostic_view.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Add failing tests for local fallback recommendation**

Add tests that assert the diagnostic view recommends local fallback when cloud providers fail with auth or quota errors:

```python
def test_expression_diagnostic_view_recommends_local_fallback_for_auth_failure():
    message = format_expression_diagnostic_message(
        {
            "ok": False,
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "stage": "provider_call",
            "reason": "http_401",
            "timeout_seconds": 45,
        }
    )

    assert "replace API key" in message
    assert "Ollama" in message or "LM Studio" in message
```

Run:

```powershell
python -m pytest tests\test_expression_diagnostic_view.py -q
```

Expected: `FAIL` until the message includes a concrete local fallback action.

- [ ] **Step 2: Add the smallest view change**

Update `src/guanghe_companion/expression_diagnostic_view.py` so `http_401`, `http_403`, and `http_429` mention local fallback:

```python
"http_401": "Action: replace API key, or switch to Ollama/LM Studio local provider",
"http_403": "Action: check provider account access, or switch to Ollama/LM Studio local provider",
"http_429": "Action: check quota, switch cloud provider, or use Ollama/LM Studio locally",
```

- [ ] **Step 3: Add app-level provider setup expectations**

In `tests/test_app.py`, add or extend a settings-panel test so the app exposes:

- provider selection;
- model field;
- base URL field;
- provider test action;
- no rendered API key value in labels or diagnostic text.

Run:

```powershell
python -m pytest tests\test_app.py tests\test_expression_diagnostic_view.py -q
```

Expected before implementation: `FAIL` on the missing UI text or missing fallback action.

- [ ] **Step 4: Implement the minimal UI copy/action change**

Update `src/guanghe_companion/app.py` only where the settings or diagnostic panel renders provider status. Do not change state application code.

- [ ] **Step 5: Update operations docs**

In `docs/llm_expression_operations.md`, add a "Recommended Provider Path" section:

```markdown
## Recommended Provider Path

1. Use `python tools\llm_provider_matrix.py --dry-run` to confirm settings shape.
2. Use a local Ollama or LM Studio server when cloud credentials are unavailable.
3. Use DeepSeek or OpenRouter for cloud smoke only after the key is current.
4. Treat missing key, auth failure, quota, timeout, invalid JSON, unsafe event, and state mutation as distinct failures.
```

- [ ] **Step 6: Verify and commit**

Run:

```powershell
python -m pytest tests\test_expression_settings.py tests\test_expression_diagnostics.py tests\test_expression_diagnostic_view.py tests\test_app.py -q
python -m pytest tests\test_desktop_pet_smoke.py -q
python -m pytest
git diff --check
git add src\guanghe_companion\expression_settings.py src\guanghe_companion\expression_diagnostics.py src\guanghe_companion\expression_diagnostic_view.py src\guanghe_companion\app.py docs\llm_expression_operations.md tests\test_expression_settings.py tests\test_expression_diagnostics.py tests\test_expression_diagnostic_view.py tests\test_app.py
git commit -m "feat: clarify llm provider setup"
```

Acceptance:

- A user can recover from invalid-key or quota failure without terminal-only debugging.
- No diagnostic message reveals an API key.
- The local provider path is visible but not auto-started by the app.

---

## P20: Multi-Turn AI Companion Quality Evaluation

**Purpose:** Evaluate whether the AI feels like a companion across a short session, not just one cue at a time.

**Out of scope:** Model fine-tuning, hidden memory writes, autonomous task execution.

**Files:**

- Create: `tests/fixtures/llm_short_session_scenarios.json`
- Create: `tools/review_llm_session_quality.py`
- Modify: `src/guanghe_companion/llm_smoke.py`
- Modify: `docs/llm_expression_operations.md`
- Test: `tests/test_llm_smoke.py`
- Test: `tests/test_llm_smoke_review.py`
- Create: `tests/test_llm_session_quality_review.py`

- [ ] **Step 1: Add a fixture with a ten-turn player-like session**

Create `tests/fixtures/llm_short_session_scenarios.json`:

```json
{
  "version": 1,
  "language": "zh-CN",
  "turns": [
    {"id": "return_after_idle", "player": "我刚回来，星汐还在吗？", "expected_cues": ["joy", "surprised"]},
    {"id": "tired", "player": "今天好累，不太想动。", "expected_cues": ["sleepy", "sadness"]},
    {"id": "celebration", "player": "我刚把一个小任务做完了。", "expected_cues": ["joy"]},
    {"id": "gift", "player": "给你带了一个小礼物。", "expected_cues": ["joy"]},
    {"id": "focus", "player": "我要专注一会儿，你陪着我就好。", "expected_cues": ["focused"]},
    {"id": "confused", "player": "我不知道下一步该怎么玩。", "expected_cues": ["confused"]},
    {"id": "goofy", "player": "做个傻傻的表情给我看。", "expected_cues": ["goofy", "joy"]},
    {"id": "quiet", "player": "先安静陪我一小会儿。", "expected_cues": ["neutral", "sleepy"]},
    {"id": "switch_character", "player": "如果换一个角色，你会怎么介绍自己？", "expected_cues": ["neutral"]},
    {"id": "goodnight", "player": "我要休息了，晚安。", "expected_cues": ["sleepy"]}
  ]
}
```

- [ ] **Step 2: Add failing loader and review tests**

Add tests:

```python
def test_llm_short_session_fixture_loads_player_turns():
    scenarios = load_short_session_scenarios()

    assert len(scenarios) == 10
    assert scenarios[0].turn_id == "return_after_idle"
    assert scenarios[0].player_text
    assert scenarios[0].expected_cues
```

```python
def test_session_quality_review_flags_flat_repeated_speech(tmp_path):
    report = {
        "ok": True,
        "turns": [
            {"speech": "嗯嗯。", "visual_actions": {"expression": "neutral"}},
            {"speech": "嗯嗯。", "visual_actions": {"expression": "neutral"}},
            {"speech": "嗯嗯。", "visual_actions": {"expression": "neutral"}}
        ],
        "state_mutation": {"changed_fields": []}
    }

    result = review_session_quality(report)

    assert result["ok"] is False
    assert "repeated_speech" in result["reasons"]
    assert "low_expression_diversity" in result["reasons"]
```

Run:

```powershell
python -m pytest tests\test_llm_smoke.py tests\test_llm_session_quality_review.py -q
```

Expected: `FAIL` because the loader and review tool do not exist yet.

- [ ] **Step 3: Implement deterministic review metrics**

Implement `tools/review_llm_session_quality.py` with pure functions:

```python
def review_session_quality(report: Mapping[str, object]) -> dict[str, object]:
    turns = list(report.get("turns", []))
    speeches = [str(turn.get("speech", "")).strip() for turn in turns if isinstance(turn, dict)]
    expressions = [
        str(turn.get("visual_actions", {}).get("expression", "")).strip()
        for turn in turns
        if isinstance(turn, dict) and isinstance(turn.get("visual_actions"), dict)
    ]
    reasons: list[str] = []
    if len(set(speeches)) < max(2, len(speeches) // 2):
        reasons.append("repeated_speech")
    if len({item for item in expressions if item}) < 3:
        reasons.append("low_expression_diversity")
    if report.get("state_mutation", {}).get("changed_fields"):
        reasons.append("state_mutated")
    return {"ok": not reasons, "reasons": reasons, "turn_count": len(turns)}
```

Adapt the exact implementation to existing smoke report shapes, but keep it pure and testable.

- [ ] **Step 4: Add CLI report output**

The CLI must accept:

```powershell
python tools\review_llm_session_quality.py artifacts\llm_smoke\session.json --json artifacts\llm_smoke\session-quality.json --markdown artifacts\llm_smoke\session-quality.md
```

The Markdown output must include:

- turn count;
- repeated speech status;
- expression diversity count;
- state mutation status;
- next action.

- [ ] **Step 5: Verify and commit**

Run:

```powershell
python -m pytest tests\test_llm_smoke.py tests\test_llm_smoke_review.py tests\test_llm_session_quality_review.py -q
python tools\llm_dialogue_smoke.py --provider deepseek --dry-run --report artifacts\llm_smoke\short-session-dry-run.json
python tools\review_llm_session_quality.py artifacts\llm_smoke\short-session-dry-run.json --json artifacts\llm_smoke\short-session-quality-dry-run.json --markdown artifacts\llm_smoke\short-session-quality-dry-run.md
python -m pytest
git diff --check
git add tests\fixtures\llm_short_session_scenarios.json tools\review_llm_session_quality.py src\guanghe_companion\llm_smoke.py docs\llm_expression_operations.md tests\test_llm_smoke.py tests\test_llm_smoke_review.py tests\test_llm_session_quality_review.py
git commit -m "feat: add llm session quality review"
```

Acceptance:

- The project can distinguish "provider works" from "AI performance is too flat".
- The review tool is deterministic and does not call a provider.
- Live calls remain optional and ignored under `artifacts/llm_smoke/`.

---

## P21: Play Loop Pacing And Visible Session Feedback

**Purpose:** Make a short play session feel intentional by showing current goals, recent moment triggers, and safe next actions.

**Out of scope:** Changing E-Moti into a productivity tool or letting AI complete goals.

**Files:**

- Modify: `src/guanghe_companion/session_goals.py`
- Modify: `src/guanghe_companion/companion_moments.py`
- Modify: `src/guanghe_companion/controller.py`
- Modify: `src/guanghe_companion/snapshot.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_session_goals.py`
- Test: `tests/test_companion_moments.py`
- Test: `tests/test_controller.py`
- Test: `tests/test_snapshot.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Add failing tests for visible session feedback**

Add tests that assert snapshots include:

```python
assert snapshot.session_goal["goal_id"] == "interact_twice"
assert snapshot.next_suggested_action["action_id"]
assert snapshot.recent_moment["moment_id"] == "return_after_idle"
```

If `recent_moment` does not exist yet, add a failing test in `tests/test_snapshot.py` first.

Run:

```powershell
python -m pytest tests\test_session_goals.py tests\test_companion_moments.py tests\test_snapshot.py -q
```

Expected: `FAIL` on missing `recent_moment` or missing UI exposure.

- [ ] **Step 2: Add typed snapshot field**

Extend the snapshot dataclasses with a small serializable field:

```python
recent_moment: dict[str, object] | None = None
```

When no moment is present, serialize it as `None`. Do not store provider output in this field.

- [ ] **Step 3: Let controller own moment recording**

In `src/guanghe_companion/controller.py`, record only deterministic moment metadata:

```python
self.last_companion_moment = {
    "moment_id": moment.moment_id,
    "tone": moment.tone,
    "expression": moment.expression,
    "motion": moment.motion,
}
```

Do not write memory, relationship, or dialogue history from this metadata.

- [ ] **Step 4: Render compact UI feedback**

In `src/guanghe_companion/app.py`, show the current session goal and recent moment in existing status/detail panels. Keep the text compact and utilitarian.

- [ ] **Step 5: Verify and commit**

Run:

```powershell
python -m pytest tests\test_session_goals.py tests\test_companion_moments.py tests\test_controller.py tests\test_snapshot.py tests\test_app.py -q
python -m pytest tests\test_desktop_pet_smoke.py -q
python -m pytest
git diff --check
git add src\guanghe_companion\session_goals.py src\guanghe_companion\companion_moments.py src\guanghe_companion\controller.py src\guanghe_companion\snapshot.py src\guanghe_companion\app.py tests\test_session_goals.py tests\test_companion_moments.py tests\test_controller.py tests\test_snapshot.py tests\test_app.py
git commit -m "feat: show companion session feedback"
```

Acceptance:

- Users can see why the pet reacted and what safe local action to try next.
- AI can phrase a moment only through existing typed expression paths.

---

## P22: Approved Pixel-Pet Row Promotion

**Purpose:** Promote exactly one human-approved pixel row candidate into `xingxi_pixel_pet` without destabilizing the renderer or default pack.

**Out of scope:** Default promotion, unapproved fanwork assets, full spritesheet regeneration, Live2D.

**Files:**

- Modify after approval only: `assets/companion/xingxi_pixel_pet/spritesheet.png`
- Modify after approval only: `assets/companion/xingxi_pixel_pet/motion_manifest.json`
- Modify after approval only: `assets/companion/xingxi_pixel_pet/provenance.md`
- Modify after approval only: `assets/companion/xingxi_pixel_pet/qa_report.json`
- Test: `tests/test_pixel_pet_pack_validator_tool.py`
- Test: `tests/test_pixel_pet_visual_qa.py`
- Test: `tests/test_pixel_pet_emote_mapping.py`
- Test: `tests/test_motion.py`

- [ ] **Step 1: Stop unless visual approval exists**

Before editing assets, confirm the approved source row path, expected motion id, and target row number. The current known candidate evidence path is:

```text
artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\p16-confused-shy-row-20260618\review\confused-shy-row-contact-sheet.png
```

Do not promote the row if approval is missing or ambiguous.

- [ ] **Step 2: Add failing manifest expectation**

If the approved motion is `ConfusedShy`, add a test that expects it in the manifest:

```python
def test_xingxi_pixel_pet_manifest_includes_confused_shy_motion():
    manifest = json.loads(
        (REPO_ROOT / "assets" / "companion" / "xingxi_pixel_pet" / "motion_manifest.json").read_text(encoding="utf-8")
    )

    assert "ConfusedShy" in manifest["motions"]
    assert manifest["motions"]["ConfusedShy"]["frame_count"] == 6
```

Run:

```powershell
python -m pytest tests\test_motion.py::test_xingxi_pixel_pet_manifest_includes_confused_shy_motion -q
```

Expected: `FAIL` until the approved row is promoted.

- [ ] **Step 3: Promote one row only**

Use a focused image tool or existing row tooling to paste the approved six frames into a single target row. Keep:

- frame width: `192`;
- frame height: `208`;
- sheet rows: `9`;
- RGBA mode;
- transparent background;
- no changes to other rows.

- [ ] **Step 4: Update provenance and QA**

Append a dated entry to `assets/companion/xingxi_pixel_pet/provenance.md`:

```markdown
## ConfusedShy Row Promotion - 2026-06-18

- Source: ignored P16 row candidate under `artifacts/pixel-pet-sequence-drafts/...`.
- Review: human-approved contact sheet before promotion.
- Scope: one motion row only; default character unchanged.
- Distribution: official candidate asset for Xingxi only.
```

Update `qa_report.json` with the new row id and manual approval status.

- [ ] **Step 5: Verify and commit**

Run:

```powershell
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-20260618\p22-xingxi-pixel-pack-validation.json
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\route-scan-20260618\p22-xingxi-pixel-visual-qa.json --preview artifacts\route-scan-20260618\p22-xingxi-pixel-visual-qa-preview.png --fail-on-warnings
python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-20260618\p22-xingxi-pixel-emote-mapping.json --markdown artifacts\route-scan-20260618\p22-xingxi-pixel-emote-mapping.md
python -m pytest tests\test_pixel_pet_pack_validator_tool.py tests\test_pixel_pet_visual_qa.py tests\test_pixel_pet_emote_mapping.py tests\test_motion.py -q
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
git diff --check
git add assets\companion\xingxi_pixel_pet\spritesheet.png assets\companion\xingxi_pixel_pet\motion_manifest.json assets\companion\xingxi_pixel_pet\provenance.md assets\companion\xingxi_pixel_pet\qa_report.json tests\test_motion.py
git commit -m "feat: promote xingxi pixel confused shy row"
```

Acceptance:

- Exactly one approved row is promoted.
- `original_oc` remains the default pack.
- Visual QA and emote mapping remain ready.

---

## P23: Character Pack Import Wizard And UGC Safety

**Purpose:** Make local UGC packs easier to import while keeping rights and distribution boundaries visible.

**Out of scope:** Bundling Ikaros, Nairong, or any third-party/fanwork assets.

**Files:**

- Modify: `src/guanghe_companion/app.py`
- Modify: `src/guanghe_companion/character_library_view_model.py`
- Modify: `src/guanghe_companion/character_pack_import.py`
- Modify: `docs/character_pack_authoring_runbook.md`
- Test: `tests/test_app.py`
- Test: `tests/test_character_library_view_model.py`
- Test: `tests/test_character_pack_import_tool.py`

- [ ] **Step 1: Add failing tests for import confirmation labels**

Add a view-model test:

```python
def test_character_library_text_warns_private_fanwork_not_for_distribution(tmp_path):
    pack = _summary(tmp_path, distribution_boundary="private_local_fanwork")

    text = character_pack_badge_text(pack)

    assert "Private fanwork" in text
    assert "do not distribute" in text.lower()
```

Run:

```powershell
python -m pytest tests\test_character_library_view_model.py -q
```

Expected: `FAIL` until the badge text is explicit enough.

- [ ] **Step 2: Add import result fields without changing file copy behavior**

Extend `CharacterPackImportResult.to_dict()` with:

```python
"distribution_warning": _distribution_warning(self.distribution_boundary)
```

Where `_distribution_warning("private_local_fanwork")` returns:

```text
Private fanwork stays local and must not be redistributed without rights.
```

- [ ] **Step 3: Surface confirmation in the UI**

In `src/guanghe_companion/app.py`, show the warning after validation and before final import confirmation. Do not block local imports solely because a pack is private fanwork.

- [ ] **Step 4: Document UGC import flow**

In `docs/character_pack_authoring_runbook.md`, add:

```markdown
## Local UGC Import Boundary

- `shareable_after_review`: original or rights-cleared work that may be published after QA.
- `local_ugc_only`: user-created local pack; do not bundle without rights review.
- `private_local_fanwork`: local fanwork or third-party-inspired pack; do not redistribute.
```

- [ ] **Step 5: Verify and commit**

Run:

```powershell
python -m pytest tests\test_character_library_view_model.py tests\test_character_pack_import_tool.py tests\test_app.py -q
python -m pytest tests\test_desktop_pet_smoke.py -q
python -m pytest
git diff --check
git add src\guanghe_companion\app.py src\guanghe_companion\character_library_view_model.py src\guanghe_companion\character_pack_import.py docs\character_pack_authoring_runbook.md tests\test_app.py tests\test_character_library_view_model.py tests\test_character_pack_import_tool.py
git commit -m "feat: clarify character import boundaries"
```

Acceptance:

- Local UGC is easier to import.
- Distribution warnings are visible before users treat fanwork as publishable.
- No third-party character assets enter the repository.

---

## Release Gate After P18-P23

Run these commands before calling the next phase complete:

```powershell
git status --short --untracked-files=all
python -m json.tool assets\companion\original_oc\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-20260618\p23-xingxi-pixel-pack-validation.json
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\route-scan-20260618\p23-xingxi-pixel-visual-qa.json --preview artifacts\route-scan-20260618\p23-xingxi-pixel-visual-qa-preview.png --fail-on-warnings
python tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-20260618\p23-xingxi-pixel-emote-mapping.json --markdown artifacts\route-scan-20260618\p23-xingxi-pixel-emote-mapping.md
python tools\llm_provider_matrix.py --dry-run --report artifacts\llm_smoke\p23-provider-matrix-dry-run.json --markdown artifacts\llm_smoke\p23-provider-matrix-dry-run.md
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
git diff --check
```

Run a live or local LLM gate only when a current provider is configured:

```powershell
python tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\p23-deepseek-expression-cue-probe.json
python tools\review_llm_session_quality.py artifacts\llm_smoke\p23-deepseek-expression-cue-probe.json --json artifacts\llm_smoke\p23-session-quality.json --markdown artifacts\llm_smoke\p23-session-quality.md
```

Run packaging only if dependencies, default assets, packaging scripts, installer behavior, or bundled runtime assets changed:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\route-scan-20260618\p23-windows-build-validation.json
```

---

## Hard Stops

Stop for explicit confirmation before:

- changing the default pack from `original_oc`;
- bundling Ikaros, Nairong, or any third-party/fanwork character pack;
- committing generated art that has not passed contact-sheet QA and human visual approval;
- adding mouse, keyboard, clipboard, window control, wake word, background listening, startup persistence, elevated install, or system-level automation;
- changing installer behavior, install path, privileges, or auto-start policy;
- adding a runtime dependency that affects packaging;
- pushing to a new remote, changing branch strategy, merging to `main`, or publishing release binaries.

---

## Definition Of Done

P18-P23 are complete only when:

- public onboarding explains how to run and evaluate the demo;
- app-level LLM diagnostics distinguish missing key, auth failure, quota, timeout, invalid response, unsafe event, and state mutation;
- at least one cloud or local provider path has current smoke evidence, or docs truthfully mark AI as not live-verified;
- multi-turn AI quality has a deterministic review gate;
- session goals and moments are visible enough to support several minutes of play;
- any promoted pixel-pet row has human visual approval and passes pack, visual, emote mapping, UI, and full pytest gates;
- local UGC import makes provenance, license, and distribution boundaries visible;
- `data\companion_save.json`, API keys, ignored LLM smoke artifacts, local fanwork, and private notes remain untracked;
- final `python -m pytest` passes;
- `git status --short --untracked-files=all` is understood and reported.
