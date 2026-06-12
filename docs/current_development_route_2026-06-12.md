# E-Moti Current Development Route 2026-06-12

本文档基于 2026-06-12 对当前仓库的实测扫描。结论只使用本次命令、当前文件和当前 QA 报告，不继承未验证的历史说法。

## 1. 本次实测基线

- 工作目录：仓库根目录
- 当前分支：`codex/demo-worktree-cleanup`
- 路线扫描起点 HEAD：`474ea1c test: add hatch pet imagegen route preflight`
- 工作区：`git status --short --untracked-files=all` 初始为空；本次扫描生成的 `artifacts/route-scan-20260612/` 是忽略证据产物，不应提交。
- 远端：当前本地 checkout 配置了 `origin` 和 `private-origin`；本文档不记录远端 URL。
- 全量测试：第一次 124 秒超时无结论；延长超时后 `python -m pytest` 通过，结果为 `801 passed in 129.03s`。
- JSON 校验：`python -m json.tool assets\companion\original_oc\shop_items.json` 通过。
- 默认角色包：`python tools\validate_character_pack.py assets\companion\original_oc` 通过，`ok=true`。
- 可选像素星汐包：`python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet` 通过，`ok=true`。
- 当前 release readiness：`python tools\release_readiness_report.py --full-local-snapshot ...` 返回 `needs_attention`，共 `17` 项检查，`8` 项 ready，`9` 项 attention。
- 像素星汐视觉 QA：`pixel_pet_visual_qa.py` 返回 `ok=true` 但 `status=ready_with_warnings`，警告为 `suspicious_edge_halo_risk`，`suspicious_edge_halo_pixel_count=13883`，`suspicious_edge_halo_ratio=0.373179`。

## 2. 当前项目真实状态

项目不是空架子。当前可保留的可演示基线包括：

- PySide6 控制面板、桌宠模式和系统托盘生命周期；
- `original_oc` 默认角色包和 `xingxi_pixel_pet` 可选内置候选包；
- 角色库、角色切换、角色包导入、角色元数据和分发边界显示；
- 本地养成状态机、背包、商店、关系、记忆和存档；
- `sprite`、`portrait`、`live2d_web` 三类 renderer 边界，其中 sprite 是当前回归安全基线；
- LLM expression 链路、typed events、visual actions、DeepSeek live smoke 历史证据；
- 屏幕观察、搜索、TTS、ASR 的可选能力设置和边界；
- Windows frozen app / installer 校验工具；
- pixel-pet、portrait/video、LivePortrait、release readiness 等 QA 工具链。

当前不应被误判为 ready 的部分：

- `xingxi_pixel_pet` 虽然已作为内置候选包存在，但视觉 QA 有明显边缘 halo 风险，不能替换默认 `original_oc`。
- hatch-pet v2 edge-style 路线目前只有 `base` job ready；9 个 row job 仍因 base 未生成而 blocked。
- 当前 secondary fallback 的 OpenAI Image API 路径被 `invalid_api_key` 阻断。
- 当前 native `codex exec` imagegen 路径被 WindowsApps `codex.exe Access is denied` 阻断。
- VN portrait / AI-video / LivePortrait 研究线仍有 body drift、缺表达、缺 blink、缺权重等阻断，不应回到近期开发表主线。

## 3. 架构判断

### 已经相对解耦的边界

- 养成状态仍由 `CompanionController`、engine、inventory、relationship、memory、storage 等本地模块拥有。
- LLM 输出必须走 expression request/parser/event pipeline 和 typed events，不直接写状态、背包、关系、记忆、目标或存档。
- renderer 由 `presentation_renderer.py`、`visual_actions.py`、`spirit_stage.py`、`live2d_web.py` 等适配层承接表现，不应反向控制状态机。
- screen observation 和 web search 只进入只读 expression context。
- ASR 只产生玩家文本输入，TTS 只消费已验证 speech。
- 角色包、角色注册表、用户包导入和分发边界已经是可测试合同。

### 仍然偏重或容易误导的部分

- `src\guanghe_companion\app.py` 约 86 KB，仍承担 UI、托盘、角色库、能力面板和 renderer 同步等多职责。它现在不宜大拆，但后续需要按窗口服务、角色库面板、能力运行时面板逐步剥离。
- `tools\release_readiness_report.py` 约 98 KB，聚合了过多研究线报告。短期可以继续用作事实仪表盘，长期应拆成 check provider。
- art 工具链同时保留 pixel-pet、portrait AI-video、LivePortrait、Live2D 研究路径，文档必须持续标明主线，否则很容易把工作带回失败的 VN/AI-video 迭代。
- 当前缺少一个安全的“外部或内置 imagegen 结果 intake 预检”入口。只要有人把随机旧图或错误角色图当成 v2 base，后续 row 生成都会污染路线。

## 4. 产品路线结论

近期开发表主线保持不变：

```text
original_oc 稳定默认包
-> xingxi_pixel_pet 作为可选内置候选
-> hatch-pet 风格 v2 base 重新锁形
-> 只生成一个动作 row
-> contact-sheet QA
-> 只修失败 row
-> 组装完整 pack
-> 角色库和桌宠 smoke
-> 再单独决定是否默认替换
```

LLM 是表现力核心，但不是养成状态机核心。下一阶段应该强化的是：

- speech 更像角色而不是工具回复；
- typed `visual_actions.expression` / `motion` 能映射到像素宠动作族；
- pixel-pet row 命名和 motion family 可被 LLM 表演选择；
- 所有 AI 能力仍只通过 typed event 和 renderer adapter 影响表现。

## 5. 下一阶段开发计划

### P0: 锁定路线文档和证据入口

目标：把当前扫描结果固化，避免后续 agent 继续围绕旧 VN/AI-video/Live2D 路线无意义迭代。

范围：

- 新增本路线文档；
- README 指向本路线文档；
- 忽略 `artifacts/route-scan-*/` 证据目录；
- 不改生产代码、不改默认角色、不改 runtime manifest。

验收：

```powershell
git diff --check
python -m pytest tests\test_repository_hygiene.py -q
```

### P1: v2 base 生成路线安全 intake

目标：在真正生成 v2 base 前先解决“图从哪里来、能不能被记录、是否对应当前 job”的问题，防止旧图、错图、手改 manifest 污染路线。

当前已实现：

- 新增只读预检工具 `tools\art\hatch_pet_base_intake_preflight.py`；
- 输入 `--run-dir`、`--job-id base`、`--source <image>`；
- 默认只接受 `$CODEX_HOME\generated_images\...\ig_*.png` 这类内置 imagegen 产物；
- 校验 `imagegen-jobs.json` 中 `base` job 存在、ready、未完成、不会覆盖；
- 复用 `review_pixel_pet_base.py` 的 base 视觉审查；
- 只输出 JSON/Markdown 和下一条 `record_imagegen_result.py` 命令，不复制文件、不改 manifest。

验收：

```powershell
python tools\art\hatch_pet_base_intake_preflight.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2 --job-id base --source "$env:CODEX_HOME\generated_images\<session>\ig_<image>.png" --character-id xingxi_pixel_pet --character-definition artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\character_definition.json --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\base-intake-preflight.json --markdown artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\base-intake-preflight.md
python -m pytest tests\test_hatch_pet_base_intake_preflight.py tests\test_pixel_pet_base_review.py -q
python -m pytest
```

当前检查点：

- 工具本身已完成 TDD 红绿：新增测试先因模块不存在失败，随后 `tests\test_hatch_pet_base_intake_preflight.py` 通过，结果为 `5 passed`。
- 工具只做 intake 预检，不生成图片、不复制图片、不写 `decoded/base.png`、不修改 `imagegen-jobs.json`。
- P1 工具加入后，全量 `python -m pytest` 通过，结果为 `806 passed in 122.04s`。
- 下一步仍需要真实 `$imagegen` 或有效 provider 产生 v2 `base` 图后，再用该工具检查并调用 `record_imagegen_result.py`。

### P2: 只生成并审查 v2 Xingxi base

目标：取得一张真正可接受的 `xingxi_pixel_pet_edge_style_v2` canonical base。

前置条件：

- `$imagegen` 或有效 provider 路线可用；
- `hatch_pet_imagegen_readiness.py` 不再是 `blocked_invalid_openai_api_key`；
- `hatch_pet_imagegen_route_preflight.py` 不再是 `blocked_generation_route`，或者明确采用内置 imagegen 结果 intake。

验收：

```powershell
python tools\art\hatch_pet_imagegen_readiness.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2 --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\imagegen-readiness.json --markdown artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\imagegen-readiness.md
python tools\art\hatch_pet_imagegen_route_preflight.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2 --check-codex-exec --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\imagegen-route-preflight.json --markdown artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\imagegen-route-preflight.md
python tools\art\review_pixel_pet_base.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\decoded\base.png --character-id xingxi_pixel_pet --prompt artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\prompts\base-pet.md --character-definition artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\character_definition.json --decision accepted_for_row_testing --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\review\base-review
```

禁止：

- 不手改 `imagegen-jobs.json`；
- 不伪造 `decoded\base.png`；
- 不一次性生成所有 row；
- 不改 `assets\companion\original_oc` 或默认角色。

### P3: v2 第一行动作 row

目标：只做 `idle_breathe + blink`，验证 v2 形体在动作序列里是否稳定。

验收：

```powershell
python tools\art\review_pixel_pet_row_candidate.py <frames-dir> --state idle --expected-frames 6 --decision accepted_for_row_testing --require-components --output-dir <review-dir>
python -m pytest tests\test_pixel_pet_row_review.py tests\test_art_tools.py tests\test_motion.py -q
python -m pytest
```

人工 QA：

- 头身比例是否仍是 hatch-pet 小宠物方向；
- 眨眼是否自然，是否比 3 帧更顺；
- 身体是否有轻微呼吸感但不漂移；
- 边缘是否没有红/紫 halo；
- 小尺寸桌宠是否可读。

### P4: 完整 pack 和角色库 smoke

目标：v2 row 全部通过后才组装完整包，并验证导入、角色库、桌宠渲染。

验收：

```powershell
python tools\validate_pixel_pet_pack.py path\to\character_packs_drafts\xingxi_pixel_pet
python tools\validate_character_pack.py path\to\complete_pack
python tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\xingxi-pixel-pet-character-library-qa.json --screenshot-dir artifacts\character-library-qa\screenshots
python -m pytest tests\test_character_registry.py tests\test_character_session.py tests\test_character_pack_import_tool.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
```

### P5: LLM 表演映射增强

目标：在动作 row 稳定后，再把 LLM expression/motion cue 映射到像素宠动作族。

范围：

- 增强 `visual_actions.expression` 到 pixel motion family 的映射；
- 增加 `goofy`、`confused`、`sleepy`、`focused`、`joy` 等表现族；
- 不改变状态机、不写存档、不绕过 typed events。

验收：

```powershell
python -m pytest tests\test_visual_actions.py tests\test_presentation_renderer.py tests\test_expression_event_pipeline.py -q
python tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\deepseek-expression-cue-probe.json
python -m pytest
```

### P6: 默认替换和发布复核

触发条件：只有 v2 美术、角色包、角色库、桌宠、LLM 表演映射全部过关后才进入。

验收：

```powershell
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --fail-on-warnings
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\windows-build-validation.json
python tools\release_readiness_report.py --full-local-snapshot --json artifacts\release-readiness-full-local-snapshot.json --markdown artifacts\release-readiness-full-local-snapshot.md
python -m pytest
```

## 6. 明确不做

- 不继续围绕旧 VN portrait / AI-video / LivePortrait 失败路径做主线迭代；
- 不把 Live2D 当成当前交付阻塞项；
- 不把 Ikaros、Nairong 作为开源默认资源分发；
- 不把 LLM 接管养成状态机；
- 不新增鼠标、键盘、剪贴板、窗口控制；
- 不手工合成或脚本伪造美术生成结果；
- 不提交 `data/companion_save.json`、API key、ignored QA artifacts。

## 7. 本次扫描命令

```powershell
git status --short --untracked-files=all
git log --oneline --decorate -12
git branch --show-current
git remote -v
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\release_readiness_report.py --full-local-snapshot --json artifacts\route-scan-20260612\release-readiness-full-local-snapshot.json --markdown artifacts\route-scan-20260612\release-readiness-full-local-snapshot.md
python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\route-scan-20260612\xingxi-pixel-pet-visual-qa.json --preview artifacts\route-scan-20260612\xingxi-pixel-pet-visual-qa-preview.png
```
