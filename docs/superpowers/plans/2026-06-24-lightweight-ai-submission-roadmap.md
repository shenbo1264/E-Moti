# Lightweight AI Submission Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a course submission package that is small enough to upload, includes the private AI configuration needed for tutor review, and keeps GitHub/public source clean of secrets and heavyweight model runtimes.

**Architecture:** E-Moti should follow the Shinsekai-style adapter route: the desktop pet, character packs, state machine, LLM expression pipeline, screen observation, search, and proactive interaction live in the lightweight client; heavyweight AI runtimes are external services or optional local bundles. The course submission package may include private local settings under a packaged `user_data/` directory, while public Git history only contains tools, templates, tests, and documentation.

**Tech Stack:** Python 3.11, PySide6, existing typed `DialogueRequest` and expression event pipeline, DeepSeek/OpenAI-compatible LLM client, existing screen observation and web search services, existing proactive companion service, pytest, PyInstaller onedir packaging.

---

## Product Route

The default deliverable must be the lightweight course submission package:

```text
dist/E-Moti-course-submission.zip
  E-Moti.exe
  _internal/
  assets/
  voice_services/              # launchers only, not large model runtimes
  user_data/
    expression_settings.json   # private course settings, may include tutor-review API key
    capability_settings.json   # private course settings for search/screen/proactive defaults
    long_term_memory.json      # optional curated initial memory
```

The public GitHub repository must not include the private `user_data` payload, provider keys, or full `voice_runtime`.

The full local voice package remains optional:

```text
dist/E-Moti/
  voice_runtime/               # optional local TTS/ASR/GPT-SoVITS runtime, too large for upload
```

Do not present the full local voice runtime as the normal course submission.

---

## File Structure

- Modify: `src/guanghe_companion/runtime_paths.py`
  - Frozen app should prefer a sibling `user_data/` directory when present.
  - This lets course submission zips include private settings without writing secrets into source.

- Modify: `tests/test_runtime_paths.py`
  - Test frozen portable `user_data/` preference.

- Create: `tools/build_course_submission_package.py`
  - Copies a frozen onedir app into `dist/E-Moti-course-submission`.
  - Excludes `voice_runtime` by default.
  - Overlays private config from an ignored directory into packaged `user_data/`.
  - Writes a JSON report and zip.
  - Refuses unsafe config filenames and paths.

- Create: `tests/test_course_submission_package_tool.py`
  - Tests private config overlay, `voice_runtime` exclusion, report generation, and path safety.

- Modify: `.gitignore`
  - Ignore `private_submission_config/`.

- Create: `private_submission_config.example/README.md`
  - Documents which private files the user can place in ignored `private_submission_config/`.

- Later modify: `src/guanghe_companion/app.py`, `src/guanghe_companion/capability_panels.py`, `src/guanghe_companion/proactive_companion.py`, `src/guanghe_companion/web_search.py`
  - AI experience tasks below.

---

## Task 1: Portable Private Config For Course Submission

**Files:**
- Modify: `src/guanghe_companion/runtime_paths.py`
- Modify: `tests/test_runtime_paths.py`

- [ ] **Step 1: Write failing runtime path test**

Add this test to `tests/test_runtime_paths.py`:

```python
def test_frozen_user_data_prefers_packaged_sibling_user_data(monkeypatch, tmp_path):
    from guanghe_companion.runtime_paths import expression_settings_path, user_data_dir

    app_dir = tmp_path / "E-Moti"
    app_dir.mkdir()
    packaged_user_data = app_dir / "user_data"
    packaged_user_data.mkdir()
    exe_path = app_dir / "E-Moti.exe"
    exe_path.write_text("", encoding="utf-8")
    local_app_data = tmp_path / "LocalAppData"

    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(exe_path))

    assert user_data_dir() == packaged_user_data
    assert expression_settings_path() == packaged_user_data / "expression_settings.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests\test_runtime_paths.py::test_frozen_user_data_prefers_packaged_sibling_user_data -q
```

Expected: fail because frozen app currently uses `%LOCALAPPDATA%\E-Moti`.

- [ ] **Step 3: Implement portable user data preference**

In `src/guanghe_companion/runtime_paths.py`, add:

```python
def packaged_user_data_dir() -> Path:
    if not is_frozen():
        return repo_root() / "data"
    return Path(sys.executable).resolve().parent / "user_data"
```

Then update `user_data_dir()`:

```python
def user_data_dir() -> Path:
    override = os.environ.get(USER_DATA_ENV)
    if override:
        return Path(override).expanduser()
    packaged = packaged_user_data_dir()
    if is_frozen() and packaged.exists():
        return packaged
    if is_frozen():
        return _local_app_data_root() / APP_DATA_DIR_NAME
    return repo_root() / "data"
```

- [ ] **Step 4: Run runtime path tests**

Run:

```powershell
python -m pytest tests\test_runtime_paths.py -q
```

Expected: all runtime path tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src\guanghe_companion\runtime_paths.py tests\test_runtime_paths.py
git commit -m "feat: support packaged course user data"
```

---

## Task 2: Build Course Submission Package With Private Config

**Files:**
- Create: `tools/build_course_submission_package.py`
- Create: `tests/test_course_submission_package_tool.py`
- Modify: `.gitignore`
- Create: `private_submission_config.example/README.md`

- [ ] **Step 1: Write failing tests**

Create `tests/test_course_submission_package_tool.py` with tests for:

```python
def test_course_submission_package_excludes_voice_runtime_and_overlays_private_config(tmp_path):
    from tools.build_course_submission_package import build_course_submission_package

    app_dir = tmp_path / "dist" / "E-Moti"
    (app_dir / "_internal" / "voice_services").mkdir(parents=True)
    (app_dir / "voice_runtime").mkdir()
    (app_dir / "voice_runtime" / "huge.bin").write_bytes(b"large")
    (app_dir / "E-Moti.exe").write_bytes(b"MZ")
    private_config = tmp_path / "private_submission_config"
    private_config.mkdir()
    (private_config / "expression_settings.json").write_text(
        '{"enabled": true, "provider": "deepseek", "api_key": "private"}',
        encoding="utf-8",
    )

    report = build_course_submission_package(
        app_dir=app_dir,
        private_config_dir=private_config,
        output_dir=tmp_path / "dist" / "E-Moti-course-submission",
        zip_path=tmp_path / "dist" / "E-Moti-course-submission.zip",
    )

    assert report.ok is True
    assert (tmp_path / "dist" / "E-Moti-course-submission" / "E-Moti.exe").is_file()
    assert not (tmp_path / "dist" / "E-Moti-course-submission" / "voice_runtime").exists()
    assert (
        tmp_path / "dist" / "E-Moti-course-submission" / "user_data" / "expression_settings.json"
    ).is_file()
    assert report.private_config_files == ("expression_settings.json",)
```

```python
def test_course_submission_package_rejects_nested_private_config_paths(tmp_path):
    from tools.build_course_submission_package import build_course_submission_package

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "E-Moti.exe").write_bytes(b"MZ")
    private_config = tmp_path / "private"
    (private_config / "nested").mkdir(parents=True)
    (private_config / "nested" / "secret.json").write_text("{}", encoding="utf-8")

    report = build_course_submission_package(
        app_dir=app_dir,
        private_config_dir=private_config,
        output_dir=tmp_path / "out",
        zip_path=tmp_path / "out.zip",
    )

    assert report.ok is False
    assert "private config file must be at top level: nested/secret.json" in report.errors
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests\test_course_submission_package_tool.py -q
```

Expected: fail because `tools.build_course_submission_package` does not exist.

- [ ] **Step 3: Implement the package builder**

Create `tools/build_course_submission_package.py` with:

- `CourseSubmissionPackageReport`
- `build_course_submission_package(...)`
- `main(...)`
- default paths:
  - app dir: `dist/E-Moti-submission-lite` if present, else `dist/E-Moti`
  - private config: `private_submission_config`
  - output dir: `dist/E-Moti-course-submission`
  - zip: `dist/E-Moti-course-submission.zip`
- copy app tree while excluding `voice_runtime` unless `--include-voice-runtime` is passed;
- copy private config files into `user_data/`;
- allow only top-level:
  - `expression_settings.json`
  - `capability_settings.json`
  - `long_term_memory.json`
  - `dialogue_history.json`
  - `companion_demo_save.json`
- write report JSON when `--report` is passed.

- [ ] **Step 4: Update ignore/template**

Add to `.gitignore`:

```gitignore
private_submission_config/
```

Create `private_submission_config.example/README.md`:

```markdown
# Private Submission Config Example

Create an ignored sibling directory named `private_submission_config/` when preparing a tutor/course submission package.

Allowed files:
- `expression_settings.json`
- `capability_settings.json`
- `long_term_memory.json`
- `dialogue_history.json`
- `companion_demo_save.json`

Do not commit `private_submission_config/`.
```

- [ ] **Step 5: Run package builder tests**

Run:

```powershell
python -m pytest tests\test_course_submission_package_tool.py -q
```

Expected: pass.

- [ ] **Step 6: Build real course package**

Run:

```powershell
python tools\build_course_submission_package.py --report artifacts\final-package-qa\course-submission-package.json
```

Expected:

- `dist\E-Moti-course-submission.zip` exists;
- `dist\E-Moti-course-submission\user_data\expression_settings.json` exists when private config exists;
- report JSON has `ok=true`;
- zip excludes `voice_runtime` by default.

- [ ] **Step 7: Smoke the real course package**

Run:

```powershell
python tools\mentor_preview_smoke.py --app-dir dist\E-Moti-course-submission --work-root artifacts\final-package-qa\mentor-preview-smoke-course-submission --seconds 5 --report artifacts\final-package-qa\mentor-preview-smoke-course-submission.json
```

Expected:

- `ok=true`;
- control panel and pet mode launches pass;
- `voice_runtime_present=false`;
- no missing required packaged files.

- [ ] **Step 8: Commit**

```powershell
git add .gitignore private_submission_config.example\README.md tests\test_course_submission_package_tool.py tools\build_course_submission_package.py
git commit -m "feat: build course submission package"
```

---

## Task 3: LLM Must Be The Default AI Core For Submission

**Files:**
- Modify: `src/guanghe_companion/expression_settings.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_expression_settings.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Add tests for private DeepSeek settings loading**

Test that packaged `user_data/expression_settings.json` enables DeepSeek through `ExpressionSettingsStore`.

- [ ] **Step 2: Add UI status copy**

Control panel AI settings should clearly show:

- enabled provider;
- model;
- live test button;
- no secret echo.

- [ ] **Step 3: Verify live DeepSeek smoke**

Run with private config:

```powershell
python tools\llm_dialogue_smoke.py --provider deepseek --timeout-seconds 45 --report artifacts\final-package-qa\course-deepseek-smoke.json
```

Expected: `ok=true`, no state mutation.

---

## Task 4: Context Builder For Memory, History, Screen, And Search

**Files:**
- Create: `src/guanghe_companion/ai_context_builder.py`
- Test: `tests/test_ai_context_builder.py`
- Modify only if needed: `src/guanghe_companion/expression_context.py`

The builder should output one bounded read-only payload:

```python
{
    "recent_dialogue": [...],
    "long_term_memory": [...],
    "perception_summary": "...",
    "tool_results": [...],
}
```

Rules:

- never write memory/state;
- max 5 recent turns;
- max 5 long-term memory summaries;
- max 3 search/topic cards;
- sanitize control characters;
- keep screenshots out of storage.

---

## Task 5: TopicScout For Web Search And Trending Conversation Hooks

**Files:**
- Create: `src/guanghe_companion/topic_scout.py`
- Test: `tests/test_topic_scout.py`
- Modify: `src/guanghe_companion/web_search.py` only if the current interface needs one small helper.

TopicScout should:

- generate safe search queries from user interests, recent chat, and memory;
- call existing `WebSearchService`;
- return topic cards:

```python
{
    "source": "web_search",
    "title": "...",
    "summary": "...",
    "opening_line": "我刚看到一个有点好笑的话题，要听吗？"
}
```

It must not autoplay long explanations. It should create a conversational hook that asks permission.

---

## Task 6: Screen Observation As Read-Only Context

**Files:**
- Modify: `src/guanghe_companion/screen_observation.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_screen_observation.py`
- Test: `tests/test_app.py`

Acceptance:

- manual “observe screen” works;
- optional timed observation respects settings interval;
- no screenshots are persisted by default;
- only sanitized text summary enters expression context.

---

## Task 7: Proactive Interaction Requests

**Files:**
- Modify: `src/guanghe_companion/proactive_companion.py`
- Modify: `src/guanghe_companion/capability_settings.py`
- Modify: `src/guanghe_companion/capability_panels.py`
- Test: `tests/test_proactive_companion.py`
- Test: `tests/test_capability_settings.py`
- Test: `tests/test_app.py`

Acceptance:

- user can enable/disable proactive requests;
- settings include interval, cooldown, daily limit, quiet hours, and context-topic toggle;
- proactive output is a short permission request, not a forced long monologue;
- rejection feedback increases cooldown;
- all proactive speech still goes through typed events.

---

## Release Verification

Run for every package that touches AI or packaging:

```powershell
python -m pytest tests\test_runtime_paths.py tests\test_course_submission_package_tool.py tests\test_mentor_preview_smoke.py -q
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
python tools\build_course_submission_package.py --report artifacts\final-package-qa\course-submission-package.json
python tools\mentor_preview_smoke.py --app-dir dist\E-Moti-course-submission --work-root artifacts\final-package-qa\mentor-preview-smoke-course-submission --seconds 5 --report artifacts\final-package-qa\mentor-preview-smoke-course-submission.json
```

If live AI credentials are present:

```powershell
python tools\llm_dialogue_smoke.py --provider deepseek --timeout-seconds 45 --report artifacts\final-package-qa\course-deepseek-smoke.json
python tools\voice_services\preflight_voice_services.py --report artifacts\final-package-qa\voice-service-preflight.json --timeout 2
```

---

## Definition Of Done

- Course submission zip is lightweight and includes private config when `private_submission_config/` exists.
- GitHub/public source contains no private config, API key, `voice_runtime`, or runtime save/cache files.
- LLM chat is the required AI core and is verified through live or private-config smoke.
- Screen observation, web search, and proactive requests are opt-in and read-only context providers.
- State machine ownership remains local: LLM cannot write growth state, inventory, relationship, memory, goals, coins, or saves directly.
