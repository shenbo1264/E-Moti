# E-Moti Current Development Route 2026-06-17

本文档基于 2026-06-17 对当前仓库、测试、QA artifact、资产和工具链的实测扫描。结论只使用本次命令和当前文件状态，不继承未验证的历史口径。

## 1. 本次扫描基线

- 工作目录：`D:\学工文档\光核\电子宠物\E-Moti_demo`
- 当前分支：`codex/demo-worktree-cleanup`
- 当前 HEAD：`255be72 test: carry base-only constraints into pet run setup`
- 工作区：`git status --short --untracked-files=all` 只显示 ` M AGENTS.md`。这是外部/用户说明文件变更，本包不覆盖、不提交。
- 远端：本地 checkout 配置了 `origin` 和 `private-origin` 两个 remote。本文档不记录远端 URL。
- PATH 注意事项：直接运行 `python -m pytest` 时，当前 PATH 指向失效的 `.agent-reach-venv` Python，无法启动；本次验证改用本机 Python 3.11 绝对路径。
- 全量测试：`C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m pytest` 通过，`818 passed in 136.45s`。
- JSON 校验：`assets\companion\original_oc\shop_items.json` 可被 `python -m json.tool` 解析。
- 默认角色包校验：`tools\validate_character_pack.py assets\companion\original_oc` 返回 `ok=true`。
- 可选像素星汐角色包校验：`tools\validate_character_pack.py assets\companion\xingxi_pixel_pet` 返回 `ok=true`。
- full-local release readiness：`status=needs_attention`，`check_count=21`，`ready_check_count=9`，`attention_check_count=12`。
- 新提取的内置 `$imagegen` 单体 base 候选：`hatch_pet_base_intake_preflight.py` 返回 `status=ready_to_record`，但尚未记录到 hatch-pet run。

本次新增 ignored 证据：

```text
artifacts/route-scan-20260617/release-readiness-full-local-snapshot.json
artifacts/route-scan-20260617/release-readiness-full-local-snapshot.md
artifacts/route-scan-20260617/release-readiness-session-intake.json
artifacts/route-scan-20260617/release-readiness-session-intake.md
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/base-intake-preflight-session-extracted-20260617.json
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/base-intake-preflight-session-extracted-20260617.md
```

这些 artifact 只作为证据，不进入 release 资产，不改默认角色。

## 2. 当前真实阶段判断

项目基础可演示，不是空架子。稳定基线包括：

- PySide6 控制面板、桌宠模式、系统托盘生命周期。
- `original_oc` 默认角色包。
- `xingxi_pixel_pet` 可选内置 sprite 候选包。
- 角色库、角色切换、用户包导入、分发边界展示。
- 本地养成状态机、背包、商店、关系、记忆、存档。
- `sprite`、`portrait`、`live2d_web` 三类 renderer 边界，其中 sprite 是当前最稳回归基线。
- LLM expression、typed events、visual actions、DeepSeek smoke 历史 artifact。
- 屏幕观察、联网搜索、TTS、ASR 的可选设置和只读/只消费边界。
- Windows frozen app / installer 校验工具链。
- pixel-pet、portrait/video、LivePortrait、release readiness 等 QA 工具链。

项目当前不能被判断为“美术可默认推广”。主要原因：

- `assets\companion\xingxi_pixel_pet` 虽然是可选内置候选，但 pixel visual QA 仍报告 `suspicious_edge_halo_risk`。
- 当前 edge halo 指标：`suspicious_edge_halo_pixel_count=13883`，`suspicious_edge_halo_ratio=0.373179`。
- `pixel_pet_edge_style_brief` 结论为 `regenerate_or_redraw_edge_style`，`default_promotion_allowed=false`。
- hatch-pet v2 修边路线尚未完成：`total=10`，`complete=0`，`ready=1`，`blocked=9`；只有 `base` job ready。
- 新提取的单体 base 候选已经通过 intake，状态是 `ready_to_record`，但还没有执行 `record_imagegen_result.py`，所以 `decoded\base.png` 和 `references\canonical-base.png` 仍未生成。
- 旧 VN portrait / AI-video / LivePortrait 研究线仍有 body drift、缺表情、缺 blink、缺权重等 blocker，不应回到近期主线。

## 3. 架构现状

当前架构已经形成了几个清晰边界：

- `CompanionController`、`engine`、`inventory`、`relationship`、`memory`、`storage` 仍是状态、存档、背包、关系和记忆的权威入口。
- LLM 输出必须走 expression request、parser、event pipeline 和 typed events，不直接写状态。
- `presentation_renderer.py` 和 `visual_actions.py` 把 typed visual actions 映射到 sprite/pixel/portrait 表现层。
- screen observation 和 web search 只进入只读 expression context。
- ASR 只能成为玩家文本输入；TTS 只消费已验证 speech。
- 角色包、角色注册表、用户包导入和分发边界已经是可测试合同。

仍然偏重或需要后续拆分的部分：

- `src\guanghe_companion\app.py` 约 86 KB，仍集中承载 UI、托盘、角色库、能力面板、桌宠同步等职责。短期不建议大拆，但后续应按角色库面板、能力运行面板、桌宠同步服务逐步剥离。
- `tools\release_readiness_report.py` 已成为大型聚合仪表盘，适合继续作为事实汇总入口，但后续可拆成 check provider。
- `tools\art\` 同时保留 pixel-pet、portrait AI-video、LivePortrait、Live2D 等研究工具，路线文档必须持续标明主线，否则容易回到失败的 VN/AI-video 迭代。
- imagegen 产物落盘链路仍不够顺滑。本次已经证明可以从会话中提取真实内置 `$imagegen` PNG 并通过 intake，但这仍是半手动流程。若后续频繁使用，应做一个受测的 session imagegen extraction helper。

## 4. 产品路线结论

近期主线保持 hatch-pet-style pixel-pet sequence：

```text
original_oc 保持默认
-> xingxi_pixel_pet 保持可选内置候选
-> 记录已通过 intake 的 v2 base 候选
-> 复核 decoded/base.png 和 canonical-base.png
-> 只生成 idle_breathe + blink 第一行
-> contact-sheet QA
-> 只修失败 row
-> 完整 pack validation
-> character library / desktop pet smoke
-> LLM expression 到 pixel motion family 的表现映射复核
-> 再单独决定是否默认替换
```

LLM 是表现力核心，但不是养成状态机核心。下一阶段应强化的是：

- speech 更像角色，而不是工具回包；
- typed `visual_actions.expression` / `motion` 能选择像素宠动作族；
- pixel-pet row 命名能承接 `goofy`、`confused`、`sleepy`、`focused`、`joy` 等表演 cue；
- 所有 AI 能力仍只通过 typed events 和 renderer adapter 影响表现。

`Ikaros` 和 `Nairong` 只保留 local UGC workflow 代表身份。除非权利边界明确，不进入开源默认资产，也不作为仓库分发素材推进。

## 5. 下一阶段开发计划

### P0：记录当前路线文档

目标：把本次扫描和下一步路线固化，避免继续围绕旧 VN portrait / AI-video / Live2D 做无意义主线迭代。

范围：

- 新增本路线文档。
- README 当前路线入口指向本路线文档。
- 不改生产代码。
- 不改 runtime manifest。
- 不提交 ignored artifacts、`AGENTS.md` 或 save 文件。

验收：

```powershell
git diff --check
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests\test_repository_hygiene.py -q
```

### P1：记录 v2 Xingxi base 候选

目标：把已经通过 intake 的内置 `$imagegen` 单体 base 正式记录到 ignored hatch-pet v2 run，解锁 row jobs。

当前可用输入：

```text
C:\Users\19970\.codex\generated_images\session-extracted\ig_08357860f38e4ece016a3267be0a30819688538de9e364fd82.png
```

已验证事实：

- 来源：built-in-imagegen。
- 形态：单体 base，不是 row strip。
- intake：`ready_to_record`。
- base review：`ok=true`，`decision=accepted_for_row_testing`。
- warning：背景接近 `#FF00FF`，切帧/推广前必须清理。

执行命令：

```powershell
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe $env:CODEX_HOME\skills\hatch-pet\scripts\record_imagegen_result.py --run-dir "artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2" --job-id base --source "C:\Users\19970\.codex\generated_images\session-extracted\ig_08357860f38e4ece016a3267be0a30819688538de9e364fd82.png"
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe $env:CODEX_HOME\skills\hatch-pet\scripts\pet_job_status.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2
```

人工 QA：

- `decoded\base.png` 是否仍像星汐；
- 是否是小宠物像素路线，而不是精细 GalGame 立绘；
- 边缘是否没有新的红/紫外发光；
- 是否适合继续做 `idle_breathe + blink`。

验收：

```powershell
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\art\review_pixel_pet_base.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\decoded\base.png --character-id xingxi_pixel_pet --prompt artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\prompts\base-pet.md --character-definition artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\character_definition.json --decision accepted_for_row_testing --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\review\base-review
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests\test_hatch_pet_base_intake_preflight.py tests\test_pixel_pet_base_review.py -q
```

### P2：只生成第一行动作 row

目标：只做 `idle_breathe + blink`，验证 v2 base 在序列帧中是否稳定。

范围：

- 只生成 `idle` row。
- 输出 contact sheet。
- 不生成全套动作。
- 不改 `assets\companion\xingxi_pixel_pet`。
- 不改默认角色。

验收：

```powershell
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\art\review_pixel_pet_row_candidate.py <frames-dir> --state idle --expected-frames 6 --decision accepted_for_row_testing --require-components --output-dir <review-dir>
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests\test_pixel_pet_row_review.py tests\test_art_tools.py tests\test_motion.py -q
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m pytest
```

人工 QA：

- 眨眼是否有足够中间帧，不是三帧硬切；
- 呼吸是否微弱但可见；
- 身体中心是否稳定，没有体漂；
- 表情是否仍然是星汐；
- 小尺寸桌宠是否可读。

### P3：完整 v2 pack 和角色库 smoke

触发条件：P2 第一行通过后，再逐行动作生成和修复。

目标：完成 v2 Xingxi pack，但仍作为候选，不默认替换。

验收：

```powershell
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\validate_pixel_pet_pack.py path\to\character_packs_drafts\xingxi_pixel_pet
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\validate_character_pack.py path\to\complete_pack
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\xingxi-pixel-pet-character-library-qa-v2.json --screenshot-dir artifacts\character-library-qa\v2-screenshots
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m pytest
```

### P4：LLM 表演闭环复核

目标：把 LLM 的表达 cue 与 pixel-pet motion family 做一次真实复核，让“AI 是核心”落在表现力上，而不是接管状态机。

范围：

- 复核 `PIXEL_EXPRESSION_MOTION_IDS` 与 v2 pack `motion_manifest.json`。
- 重跑 DeepSeek expression cue probe。
- 检查 fallback、speech 长度、表情覆盖、状态突变。
- 不允许 LLM 写状态、背包、关系、记忆、目标或存档。

验收：

```powershell
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-20260617\xingxi-pixel-pet-emote-mapping.json --markdown artifacts\route-scan-20260617\xingxi-pixel-pet-emote-mapping.md
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\deepseek-expression-cue-probe-v2.json
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests\test_visual_actions.py tests\test_presentation_renderer.py tests\test_expression_event_pipeline.py tests\test_llm_smoke.py -q
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m pytest
```

### P5：默认替换与发布复核

触发条件：v2 美术、角色包、角色库、桌宠 smoke、LLM 表演映射全部通过后才进入。

目标：决定是否把 `xingxi_pixel_pet` 从可选候选提升为默认包。

验收：

```powershell
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --fail-on-warnings
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1 -PythonPath "C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe"
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild -PythonPath "C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe"
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\validate_windows_build.py --report artifacts\windows-build-validation.json
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\release_readiness_report.py --full-local-snapshot --json artifacts\release-readiness-full-local-snapshot.json --markdown artifacts\release-readiness-full-local-snapshot.md
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m pytest
```

## 6. 暂停或降级的路线

以下路线保留为研究线，不作为近期交付主线：

- VN portrait 默认推广。
- AI-video 直接生成可用序列帧。
- LivePortrait 本地推理。
- Live2D 正式模型制作与运行时替换。
- Ikaros / Nairong 作为开源默认资产。

这些路线不是永远删除，而是不能再阻塞 pixel-pet sequence 主线。

## 7. 明确不做

- 不继续围绕失败的 AI-video 方案无边界迭代。
- 不把 Ikaros、Nairong 素材放进开源默认资产。
- 不把 ignored 草稿图直接写进 runtime manifest。
- 不手改 `imagegen-jobs.json`。
- 不伪造 `decoded\base.png`。
- 不在没有 TDD 和验收命令的情况下拆 `app.py`。
- 不让 LLM 修改成长状态、背包、关系、记忆、目标或存档。
- 不新增鼠标、键盘、剪贴板、窗口控制。
- 不提交 `data\companion_save.json`、API key、ignored QA artifacts。

## 8. 本次实际执行过的命令

```powershell
git status --short --untracked-files=all
git log --oneline --decorate -12
git branch --show-current
git remote -v
python -m pytest
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m pytest
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe -m json.tool assets\companion\original_oc\shop_items.json
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\validate_character_pack.py assets\companion\original_oc
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\release_readiness_report.py --full-local-snapshot --json artifacts\route-scan-20260617\release-readiness-full-local-snapshot.json --markdown artifacts\route-scan-20260617\release-readiness-full-local-snapshot.md
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe C:\Users\19970\.codex\skills\hatch-pet\scripts\pet_job_status.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\art\hatch_pet_base_intake_preflight.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2 --job-id base --source C:\Users\19970\.codex\generated_images\session-extracted\ig_08357860f38e4ece016a3267be0a30819688538de9e364fd82.png --character-id xingxi_pixel_pet --character-definition artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\character_definition.json --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\base-intake-preflight-session-extracted-20260617.json --markdown artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\base-intake-preflight-session-extracted-20260617.md
C:\Users\19970\AppData\Local\Programs\Python\Python311\python.exe tools\release_readiness_report.py --hatch-pet-base-intake-report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\base-intake-preflight-session-extracted-20260617.json --json artifacts\route-scan-20260617\release-readiness-session-intake.json --markdown artifacts\route-scan-20260617\release-readiness-session-intake.md
rg --files src tests tools packaging assets\companion docs
rg -n "original_oc|xingxi_pixel_pet|load_default_character_pack|DEFAULT" src\guanghe_companion assets\companion tools\validate_character_pack.py tests\test_character_pack.py
rg -n "PIXEL_EXPRESSION_MOTION_IDS|visual_actions|motion_hint|expression" src\guanghe_companion\visual_actions.py src\guanghe_companion\presentation_renderer.py src\guanghe_companion\expression_event_pipeline.py tests\test_pixel_pet_emote_mapping.py
```
