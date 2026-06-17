# E-Moti Current Development Route 2026-06-17

本文档基于 2026-06-17 对当前仓库、测试、QA artifact、资产和工具链的实测扫描。结论只使用本次命令和当前文件状态，不继承未验证的历史口径。

## 1. 本次扫描基线

- 工作目录：`<repo-root>`
- 当前分支：`codex/demo-worktree-cleanup`
- 当前 HEAD：`255be72 test: carry base-only constraints into pet run setup`
- 工作区：`git status --short --untracked-files=all` 只显示 ` M AGENTS.md`。这是外部/用户说明文件变更，本包不覆盖、不提交。
- 远端：本地 checkout 配置了 `origin` 和 `private-origin` 两个 remote。本文档不记录远端 URL。
- PATH 注意事项：直接运行 `python -m pytest` 时，当前 PATH 指向失效的 `.agent-reach-venv` Python，无法启动；本次验证改用本机 Python 3.11 绝对路径。
- 全量测试：`<PYTHON311> -m pytest` 通过，`818 passed in 136.45s`。
- JSON 校验：`assets\companion\original_oc\shop_items.json` 可被 `python -m json.tool` 解析。
- 默认角色包校验：`tools\validate_character_pack.py assets\companion\original_oc` 返回 `ok=true`。
- 可选像素星汐角色包校验：`tools\validate_character_pack.py assets\companion\xingxi_pixel_pet` 返回 `ok=true`。
- full-local release readiness：`status=needs_attention`，`check_count=21`，`ready_check_count=9`，`attention_check_count=12`。
- 新提取的内置 `$imagegen` 单体 base 候选先由 `hatch_pet_base_intake_preflight.py` 验证为 `status=ready_to_record`，随后已通过 `record_imagegen_result.py` 记录到 ignored hatch-pet v2 run。
- v2 hatch-pet job 状态：`total=10`，`complete=1`，`ready=8`，`blocked=1`；`running-left` 仍等待 `running-right` 后再决定镜像或生成。

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
- hatch-pet v2 修边路线尚未完成，但 base 阶段已经推进：`total=10`，`complete=1`，`ready=8`，`blocked=1`。
- 新提取的单体 base 候选已经通过 intake，并已执行 `record_imagegen_result.py`；`decoded\base.png` 和 `references\canonical-base.png` 已生成。下一步不是全量生成，而是先做 `idle_breathe + blink` 第一行。
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
-> 已记录通过 intake 的 v2 base 候选
-> 已复核 decoded/base.png 和 canonical-base.png
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
<PYTHON311> -m pytest tests\test_repository_hygiene.py -q
```

### P1：记录 v2 Xingxi base 候选

目标：把已经通过 intake 的内置 `$imagegen` 单体 base 正式记录到 ignored hatch-pet v2 run，解锁 row jobs。

当前状态：已完成。`record_imagegen_result.py` 返回 `ok=true`，`decoded\base.png` 与 `references\canonical-base.png` 已存在；记录后 `pet_job_status.py` 返回 `complete=1`、`ready=8`、`blocked=1`。

当前可用输入：

```text
<CODEX_HOME>\generated_images\session-extracted\ig_08357860f38e4ece016a3267be0a30819688538de9e364fd82.png
```

已验证事实：

- 来源：built-in-imagegen。
- 形态：单体 base，不是 row strip。
- intake：`ready_to_record`。
- base review：`ok=true`，`decision=accepted_for_row_testing`。
- warning：背景接近 `#FF00FF`，切帧/推广前必须清理。
- 视觉复核：单体像素宠星汐，比例符合 hatch-pet 路线；背景仍为品红 chroma-key，不得直接推广为 runtime 资产。

执行命令：

```powershell
<PYTHON311> $env:CODEX_HOME\skills\hatch-pet\scripts\record_imagegen_result.py --run-dir "artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2" --job-id base --source "<CODEX_HOME>\generated_images\session-extracted\ig_08357860f38e4ece016a3267be0a30819688538de9e364fd82.png"
<PYTHON311> $env:CODEX_HOME\skills\hatch-pet\scripts\pet_job_status.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2
```

人工 QA：

- `decoded\base.png` 是否仍像星汐；
- 是否是小宠物像素路线，而不是精细 GalGame 立绘；
- 边缘是否没有新的红/紫外发光；
- 是否适合继续做 `idle_breathe + blink`。

验收：

```powershell
<PYTHON311> tools\art\review_pixel_pet_base.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\decoded\base.png --character-id xingxi_pixel_pet --prompt artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\prompts\base-pet.md --character-definition artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\character_definition.json --decision accepted_for_row_testing --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\review\base-review
<PYTHON311> -m pytest tests\test_hatch_pet_base_intake_preflight.py tests\test_pixel_pet_base_review.py -q
```

本包记录后的 QA 证据：

```text
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/decoded/base.png
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/references/canonical-base.png
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/review/base-review-20260617/base-review.json
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/review/base-review-20260617/base-review.md
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/review/base-review-20260617/base-review.png
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
<PYTHON311> tools\art\review_pixel_pet_row_candidate.py <frames-dir> --state idle --expected-frames 6 --decision accepted_for_row_testing --require-components --output-dir <review-dir>
<PYTHON311> -m pytest tests\test_pixel_pet_row_review.py tests\test_art_tools.py tests\test_motion.py -q
<PYTHON311> -m pytest
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
<PYTHON311> tools\validate_pixel_pet_pack.py path\to\character_packs_drafts\xingxi_pixel_pet
<PYTHON311> tools\validate_character_pack.py path\to\complete_pack
<PYTHON311> tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\xingxi-pixel-pet-character-library-qa-v2.json --screenshot-dir artifacts\character-library-qa\v2-screenshots
<PYTHON311> -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
<PYTHON311> -m pytest
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
<PYTHON311> tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-20260617\xingxi-pixel-pet-emote-mapping.json --markdown artifacts\route-scan-20260617\xingxi-pixel-pet-emote-mapping.md
<PYTHON311> tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\deepseek-expression-cue-probe-v2.json
<PYTHON311> -m pytest tests\test_visual_actions.py tests\test_presentation_renderer.py tests\test_expression_event_pipeline.py tests\test_llm_smoke.py -q
<PYTHON311> -m pytest
```

### P5：默认替换与发布复核

触发条件：v2 美术、角色包、角色库、桌宠 smoke、LLM 表演映射全部通过后才进入。

目标：决定是否把 `xingxi_pixel_pet` 从可选候选提升为默认包。

验收：

```powershell
<PYTHON311> tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --fail-on-warnings
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1 -PythonPath "<PYTHON311>"
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild -PythonPath "<PYTHON311>"
<PYTHON311> tools\validate_windows_build.py --report artifacts\windows-build-validation.json
<PYTHON311> tools\release_readiness_report.py --full-local-snapshot --json artifacts\release-readiness-full-local-snapshot.json --markdown artifacts\release-readiness-full-local-snapshot.md
<PYTHON311> -m pytest
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
<PYTHON311> -m pytest
<PYTHON311> -m json.tool assets\companion\original_oc\shop_items.json
<PYTHON311> tools\validate_character_pack.py assets\companion\original_oc
<PYTHON311> tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
<PYTHON311> tools\release_readiness_report.py --full-local-snapshot --json artifacts\route-scan-20260617\release-readiness-full-local-snapshot.json --markdown artifacts\route-scan-20260617\release-readiness-full-local-snapshot.md
<PYTHON311> <CODEX_HOME>\skills\hatch-pet\scripts\pet_job_status.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2
<PYTHON311> tools\art\hatch_pet_base_intake_preflight.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2 --job-id base --source <CODEX_HOME>\generated_images\session-extracted\ig_08357860f38e4ece016a3267be0a30819688538de9e364fd82.png --character-id xingxi_pixel_pet --character-definition artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\character_definition.json --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\base-intake-preflight-session-extracted-20260617.json --markdown artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\base-intake-preflight-session-extracted-20260617.md
<PYTHON311> tools\release_readiness_report.py --hatch-pet-base-intake-report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\base-intake-preflight-session-extracted-20260617.json --json artifacts\route-scan-20260617\release-readiness-session-intake.json --markdown artifacts\route-scan-20260617\release-readiness-session-intake.md
<PYTHON311> <CODEX_HOME>\skills\hatch-pet\scripts\record_imagegen_result.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2 --job-id base --source <CODEX_HOME>\generated_images\session-extracted\ig_08357860f38e4ece016a3267be0a30819688538de9e364fd82.png
<PYTHON311> <CODEX_HOME>\skills\hatch-pet\scripts\pet_job_status.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2
<PYTHON311> tools\art\review_pixel_pet_base.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\decoded\base.png --character-id xingxi_pixel_pet --prompt artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\prompts\base-pet.md --character-definition artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\character_definition.json --decision accepted_for_row_testing --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\review\base-review-20260617
rg --files src tests tools packaging assets\companion docs
rg -n "original_oc|xingxi_pixel_pet|load_default_character_pack|DEFAULT" src\guanghe_companion assets\companion tools\validate_character_pack.py tests\test_character_pack.py
rg -n "PIXEL_EXPRESSION_MOTION_IDS|visual_actions|motion_hint|expression" src\guanghe_companion\visual_actions.py src\guanghe_companion\presentation_renderer.py src\guanghe_companion\expression_event_pipeline.py tests\test_pixel_pet_emote_mapping.py
```

## 9. 2026-06-17 P2 row intake 增量记录

本节记录在本路线文档创建后继续推进的真实状态。它只描述 ignored hatch-pet v2 run 的候选资产进展，不代表 runtime assets、默认角色或 release manifest 已更新。

### session imagegen 提取工具

为了解决 subagent 调用内置 `$imagegen` 后只留下会话内联 PNG、没有稳定落盘 `ig_*.png` 的问题，新增了一个可测试工具：

```text
tools/art/extract_session_imagegen_result.py
tests/test_session_imagegen_result_extractor.py
```

工具边界：

- 只从 Codex session JSONL 提取真实 `image_generation_end` 结果；
- 只接受 `ig_` 开头的安全 call id；
- 校验 base64 和 PNG signature；
- 输出到 `<CODEX_HOME>/generated_images/.../ig_*.png` 这类原始生成图目录；
- 可写 JSON report，便于 provenance 复核；
- 不改 `imagegen-jobs.json`，不复制到 `decoded/`，不伪造 visual job 完成状态。

已验证：

```powershell
<PYTHON311> -m pytest tests\test_session_imagegen_result_extractor.py -q
```

结果：`4 passed`。

### subagent row 候选提取与录入

已从两个 subagent 会话中提取真实内置 `$imagegen` 输出，并用 hatch-pet 官方 `record_imagegen_result.py` 录入 ignored v2 run：

```text
idle -> decoded/idle.png
running-right -> decoded/running-right.png
```

录入后 `pet_job_status.py` 的真实状态：

```text
total=10
complete=3
ready=7
blocked=0
```

含义：

- `base`、`idle`、`running-right` 已完成；
- `running-left` 已解锁；
- 其余 row 仍是待生成候选；
- 正式 `assets/companion/xingxi_pixel_pet` 没有更新。

### 部分抽帧 QA

因为 `finalize_pet_run.py` 要求全部 imagegen jobs 完成，当前只用底层抽帧脚本做了部分候选 QA：

```powershell
<PYTHON311> <hatch-pet>/scripts/extract_strip_frames.py --decoded-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\decoded --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\frames-partial-20260617 --states idle,running-right --method auto
<PYTHON311> tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\frames-partial-20260617 --state idle --expected-frames 6 --decision accepted_for_row_testing --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\review\idle-row-review-20260617
<PYTHON311> tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\frames-partial-20260617 --state running-right --expected-frames 8 --decision accepted_for_row_testing --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\review\running-right-row-review-20260617
```

结果：

```text
idle:
  ok=true
  frames=6/6
  extraction_method=components
  average_frame_delta=8.534
  warnings=0

running-right:
  ok=true
  frames=8/8
  extraction_method=components
  average_frame_delta=24.6695
  warnings=0
```

人工视觉复核：

- `idle` 是 6 帧横排，眨眼帧明确，体型稳定；动作幅度偏保守但适合作为桌宠 idle。
- `running-right` 是 8 帧横排，跑动方向清楚，身份和比例保持得住。
- 两条 row 的原始大图背景肉眼有轻微非纯色风险，但 component extraction 已能正确抽出角色；仍需要在完整 pack QA 时继续看边缘残留和透明背景质量。

### 下一步调整

P2 的下一步不应直接全量生成所有 row。建议顺序：

1. 先处理 `running-left`。
2. 因为星汐有单侧星星发饰，直接镜像 `running-right` 可能翻转身份特征；默认不把镜像视为安全。
3. 优先按正常 grounded row 通过 subagent 生成 `running-left`。
4. 只有人工明确接受“发饰侧翻转在左行动画中可接受”时，才使用 `derive_running_left_from_running_right.py`。
5. `running-left` 通过后，再分批生成 `waiting` / `waving` / `jumping` 等低风险 row。
6. 每一批都先做 contact-sheet 或 partial row QA，失败只修失败 row。

本增量仍然遵守：不更新 runtime manifest，不替换默认角色，不提交 ignored artifacts，不让 LLM 或美术流程影响养成状态机。
