# E-Moti Current Development Route 2026-06-17

本文档基于 2026-06-17 对当前仓库、测试、QA artifact、资产和工具链的实测扫描。结论只使用本次命令和当前文件状态，不继承未验证的历史口径。

## 1. 本次扫描基线

- 工作目录：`<repo-root>`
- 当前分支：`codex/demo-worktree-cleanup`
- 当前 HEAD：`d8d1057 test: add session imagegen extraction helper`
- 工作区：`git status --short --untracked-files=all` 显示 ` M AGENTS.md` 和 ` M docs/current_development_route_2026-06-17.md`。`AGENTS.md` 是外部/用户说明文件变更，本包不覆盖、不提交；路线文档是本次工作对象。
- 远端：本地 checkout 配置了 `origin` 和 `private-origin` 两个 remote。本文档不记录远端 URL。
- PATH 注意事项：直接运行 `python -m pytest` 时，当前 PATH 指向失效的 `.agent-reach-venv` Python，无法启动；本次验证改用本机 Python 3.11 绝对路径。
- 全量测试：本次追加当前扫描后重新运行 `<PYTHON311> -m pytest`，结果 `822 passed in 110.57s`。
- JSON 校验：`assets\companion\original_oc\shop_items.json` 可被 `python -m json.tool` 解析。
- 默认角色包校验：`tools\validate_character_pack.py assets\companion\original_oc` 返回 `ok=true`。
- 可选像素星汐角色包校验：`tools\validate_character_pack.py assets\companion\xingxi_pixel_pet` 返回 `ok=true`。
- full-local release readiness：`status=needs_attention`，`check_count=21`，`ready_check_count=9`，`attention_check_count=12`。
- 新提取的内置 `$imagegen` 单体 base 候选先由 `hatch_pet_base_intake_preflight.py` 验证为 `status=ready_to_record`，随后已通过 `record_imagegen_result.py` 记录到 ignored hatch-pet v2 run。
- v2 hatch-pet job 状态已重新验证：`total=10`，`complete=10`，`ready=0`，`blocked=0`。完整 ignored candidate pack 已生成，并通过 pixel-pet pack validator 与 character-pack validator。

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
- hatch-pet v2 修边路线已从 base/row 阶段推进到完整 ignored candidate pack 阶段：`total=10`，`complete=10`，`ready=0`，`blocked=0`。
- 完整 v2 candidate pack 已通过结构验证和运行时角色包验证，并已成功导入 ignored `character_packs\xingxi_pixel_pet` 做本地用户包 smoke 基础。
- 下一步不是继续生成 row，而是做角色库/UI smoke、LLM motion mapping 复核、人工美术 QA 和默认推广门禁。
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

近期主线保持 hatch-pet-style pixel-pet sequence，但当前阶段已经从“生成第一行动作”推进到“完整 v2 候选包草稿复核”：

```text
original_oc 保持默认
-> xingxi_pixel_pet 保持可选内置候选
-> 已完成 v2 hatch-pet run 的 9 行动作序列
-> 已完成 contact-sheet QA
-> 已生成 ignored complete candidate pack
-> 已通过 pixel-pet pack validation
-> 已通过 character-pack validation
-> 已完成 ignored local user-pack import validation
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

当前状态：已完成并已被后续完整 row set 继承。`record_imagegen_result.py` 返回 `ok=true`，`decoded\base.png` 与 `references\canonical-base.png` 已存在；最新 `pet_job_status.py` 返回 `complete=10`、`ready=0`、`blocked=0`。

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

当前状态：已完成，并已继续推进到完整 row set。保留本段作为历史门禁说明，后续不应再回到“先做第一行”的阶段。

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

当前状态：完整 ignored candidate pack 已生成并通过结构验证；剩余工作是角色库/UI smoke、人工美术 QA、LLM motion mapping 复核和是否替换 optional bundled candidate 的独立决策。

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

## 10. 2026-06-17 P3 v2 complete candidate pack 增量记录

本节记录 v2 hatch-pet run 从 row 候选推进到完整候选包草稿的真实状态。所有输出仍位于 ignored artifact 路径；正式 `assets/companion/original_oc`、`assets/companion/xingxi_pixel_pet`、默认角色和 runtime manifest 均未更新。

### row 生成与 subagent 分工

按 hatch-pet 规则，row-strip visual generation 使用 subagent，父进程只负责提取、录入、抽帧、QA 和 finalize。

已委派并完成的 row：

```text
idle -> subagent, extracted from session imagegen payload
running-right -> subagent, extracted from session imagegen payload
running-left -> subagent, normal grounded generation; no mirror shortcut
waving -> subagent, extracted from session imagegen payload
jumping -> subagent, extracted from session imagegen payload
failed -> subagent, extracted from session imagegen payload
waiting -> subagent, extracted from session imagegen payload
running -> subagent, extracted from session imagegen payload
review -> subagent, first inline attempt had wrong count; subagent regenerated 6-frame candidate, then parent extracted final payload
```

父进程使用 `tools/art/extract_session_imagegen_result.py` 从 Codex session JSONL 提取真实内置 `$imagegen` PNG，再用 `<hatch-pet>/scripts/record_imagegen_result.py` 录入 `imagegen-jobs.json`。未手改 manifest，未复制本地伪造 row，未用 Pillow/脚本生成视觉内容。

录入后的真实 job 状态：

```text
total=10
complete=10
ready=0
blocked=0
```

### 完整 finalize

已运行：

```powershell
<PYTHON311> <hatch-pet>/scripts/finalize_pet_run.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2 --skip-videos --skip-package
```

结果：

```text
ok=true
frames_root=artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/frames
final/spritesheet.png written
final/spritesheet.webp written
final/validation.json ok=true
qa/review.json ok=true
qa/contact-sheet.png written
spritesheet size=1536x1872
spritesheet mode=RGBA
errors=0
warnings=0
```

人工 contact-sheet 复核：

- 9 个 animation rows 全部存在；
- 每行帧数与 motion manifest 一致；
- unused cells 透明；
- `idle` 有眨眼；
- `running-right`、`running-left`、`running` 运动方向清楚；
- `waving` 可读但幅度保守；
- `waiting` 与 `idle` 区分度有限但仍可用；
- `jumping`、`failed`、`review` 表意清楚；
- 未发现 guide marks、文字、阴影、速度线、尘土、漂浮装饰或 slot crossing。

### ignored candidate pack

已创建 ignored 草稿包：

```text
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/candidate-pack/xingxi_pixel_pet/
  character.json
  dialogue_style.json
  motion_manifest.json
  spritesheet.png
  preview/contact-sheet.png
  provenance.md
  qa_report.json
  shop_items.json
  LICENSE.md
  item_icons/
```

已验证：

```powershell
<PYTHON311> tools\validate_pixel_pet_pack.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack\xingxi_pixel_pet --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack-validation.json
<PYTHON311> tools\validate_character_pack.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack\xingxi_pixel_pet
<PYTHON311> tools\art\pixel_pet_visual_qa.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack\xingxi_pixel_pet\spritesheet.png --motion-manifest artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack\xingxi_pixel_pet\motion_manifest.json --preview artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack-visual-qa-preview.png
```

结果：

```text
validate_pixel_pet_pack: ok=true
validate_character_pack: ok=true
pixel_pet_visual_qa: ok=true, status=ready_with_warnings
visual warning: suspicious_edge_halo_risk
suspicious_edge_halo_pixel_count=13790
suspicious_edge_halo_ratio=0.401047
```

### 当前决策

v2 已经从“row 测试”推进到“完整候选包草稿”。它可以用于下一步本地导入、角色库 smoke、LLM motion mapping 复核和人工美术 QA。

但它仍不能直接推广为默认或正式 bundled replacement，原因是：

- visual QA 仍报 `suspicious_edge_halo_risk`；
- `waving` 和 `waiting` 动作幅度偏保守，需要人工确认是否足够灵动；
- ignored candidate pack 还没有进入正式 `assets/companion/xingxi_pixel_pet`；
- 未运行 UI character-library smoke、full app smoke、Windows packaging gate。

下一步建议：

1. 用该 ignored candidate pack 跑本地导入或角色库 QA，不更新默认角色。
2. 如果 UI smoke 通过，再由人工决定是否把 v2 作为新的 optional bundled candidate 替换现有 `assets/companion/xingxi_pixel_pet`。
3. 若要默认推广，必须先解决或接受 edge halo warning，并运行 UI、full pytest、Windows app/installer gates。

## 11. 2026-06-17 current rescan 后的开发计划

本节是当前轮重新扫描后的最新计划，优先级高于前面保留的历史 P1/P2 阶段说明。

### 本轮重新验证的事实

已重新执行：

```powershell
git status --short --untracked-files=all
git log --oneline --decorate -12
git branch --show-current
<PYTHON311> <hatch-pet>\scripts\pet_job_status.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2
<PYTHON311> tools\validate_pixel_pet_pack.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack\xingxi_pixel_pet --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack-validation-rescan-20260617.json
<PYTHON311> tools\validate_character_pack.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack\xingxi_pixel_pet
<PYTHON311> tools\art\pixel_pet_visual_qa.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack\xingxi_pixel_pet\spritesheet.png --motion-manifest artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack\xingxi_pixel_pet\motion_manifest.json --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack-visual-qa-rescan-20260617.json --preview artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack-visual-qa-preview-rescan-20260617.png
<PYTHON311> tools\validate_character_pack.py character_packs\xingxi_pixel_pet
<PYTHON311> tools\validate_pixel_pet_pack.py character_packs\xingxi_pixel_pet --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\imported-pack-validation-rescan-20260617.json
git diff --check
<PYTHON311> -m pytest tests\test_repository_hygiene.py tests\test_session_imagegen_result_extractor.py tests\test_pixel_pet_pack_validator_tool.py tests\test_character_pack_import_tool.py tests\test_pixel_pet_visual_qa.py -q
<PYTHON311> -m pytest
```

结果：

```text
branch=codex/demo-worktree-cleanup
HEAD=d8d1057 test: add session imagegen extraction helper
working tree tracked changes=AGENTS.md, docs/current_development_route_2026-06-17.md
v2 hatch-pet jobs=10 total, 10 complete, 0 ready, 0 blocked
candidate pixel-pet pack validation=ok=true
candidate runtime character-pack validation=ok=true
imported local user-pack validation=ok=true
candidate visual QA=ok=true, status=ready_with_warnings
candidate visual warning=suspicious_edge_halo_risk
suspicious_edge_halo_pixel_count=13790
suspicious_edge_halo_ratio=0.401047
focused regression tests=22 passed
full pytest=822 passed in 110.57s
```

### 当前阶段结论

v2 Xingxi pixel-pet 已经不是“缺 row 的制作中状态”，而是“完整 ignored 候选包待体验和推广门禁”的状态。

可以继续做：

- 本地用户包导入 smoke；
- 角色库 UI 和桌宠模式 smoke；
- LLM expression 到 pixel motion family 的映射复核；
- 对 `waving`、`waiting` 和边缘 halo 的人工美术 QA；
- 在通过 UI/LLM/美术门禁后，单独开包决定是否替换 `assets\companion\xingxi_pixel_pet`。

不能直接做：

- 不直接替换默认 `original_oc`；
- 不把 ignored candidate pack 直接提交为 release 资产；
- 不跳过 `suspicious_edge_halo_risk`；
- 不把 Ikaros、Nairong 作为开源默认资产；
- 不把 LLM 接管成长状态机。

### 建议下一包：P3-smoke-and-art-gate

目标：确认 v2 ignored candidate pack 在真实 UI/桌宠路径里是否可用，并把人工美术风险转成明确决策。

范围：

- 使用已经导入到 ignored `character_packs\xingxi_pixel_pet` 的本地用户包；
- 跑角色库 QA，确认 provenance、license、distribution boundary、切换入口、桌宠入口可见；
- 跑 `tests\test_app.py` 和 `tests\test_desktop_pet_smoke.py`；
- 复看 visual QA preview 和 contact sheet，明确 `waving`/`waiting` 是否需要重生；
- 不更新 `assets\companion\xingxi_pixel_pet`；
- 不更新默认角色；
- 不改安装器。

验收：

```powershell
<PYTHON311> tools\character_library_qa.py --character-id xingxi_pixel_pet --character-root character_packs --report artifacts\character-library-qa\xingxi-pixel-pet-v2-local-user-pack-qa.json --screenshot-dir artifacts\character-library-qa\xingxi-pixel-pet-v2-local-user-pack-screenshots
<PYTHON311> -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
<PYTHON311> -m pytest tests\test_character_library_qa_tool.py tests\test_character_pack_import_tool.py tests\test_pixel_pet_pack_validator_tool.py tests\test_pixel_pet_visual_qa.py -q
<PYTHON311> -m pytest
```

人工验收：

- 角色库能找到本地 `xingxi_pixel_pet`；
- 分发边界和来源信息没有把候选包误写成已发布默认资产；
- 切换角色后控制面板和桌宠模式都能显示 v2；
- 桌宠小尺寸下眨眼、跑动、失败、审阅动作可读；
- `waving` 和 `waiting` 的幅度是否足够灵动有明确结论；
- 若边缘 halo 在实际桌面透明窗口里明显，先修边，不进入 bundled promotion。

### 后续包拆分

P4-llm-motion-map：

- 将 v2 candidate pack 的 `motion_manifest.json` 与 `PIXEL_EXPRESSION_MOTION_IDS` 做映射复核；
- 使用 DeepSeek 做 expression cue probe；
- 验证 LLM 输出只影响 speech/expression/motion/interaction intent，不写成长、背包、关系、记忆、目标或存档。

P5-optional-bundled-candidate-promotion：

- 只在 P3 和 P4 通过后考虑；
- 替换或更新 `assets\companion\xingxi_pixel_pet`，仍保持 `original_oc` 默认；
- 必须跑 UI tests、full pytest、pixel visual QA、release readiness；
- 如果涉及冻结包或安装器行为，再跑 Windows app/installer gates。

P6-default-promotion：

- 只在用户明确要求时进入；
- 需要单独评估开源资产质量、边缘 halo、角色表现力、包装体积和回滚方案；
- 必须运行 full pytest、UI smoke、Windows app build、installer build、frozen exe smoke。

## 12. 2026-06-18 P3 local user-pack smoke 结果

本节记录 P3-smoke-and-art-gate 的当前真实结果。结论：本地用户包 UI/桌宠路径可用，但美术门禁不通过，不能进入 bundled promotion。

### QA 工具修正

执行 P3 时发现 `tools\character_library_qa.py` 原本只能使用临时 user-data 下的默认 `character_packs`，不能按路线文档指定 `--character-root character_packs`。更重要的是，当本地包与 bundled 包同为 `xingxi_pixel_pet` 时，旧 QA 会优先测到 bundled 包，形成假阳性。

本包已按 TDD 修正：

- `run_character_library_qa(..., character_root=...)` 支持显式本地用户包根目录；
- CLI 新增 `--character-root`；
- 报告新增 `candidate_source` 和 `candidate_pack_path`；
- 当指定 `character_root` 时，QA 要求被测候选来自 `Source: user`，且路径必须在该 root 内；
- 该变更只影响 QA 工具，不改变生产应用的角色包优先级或默认角色。

已验证：

```powershell
<PYTHON311> -m pytest tests\test_character_library_qa_tool.py -q
```

结果：`5 passed`。

### v2 本地用户包 smoke

已执行：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
<PYTHON311> tools\character_library_qa.py --character-id xingxi_pixel_pet --character-root character_packs --report artifacts\character-library-qa\xingxi-pixel-pet-v2-local-user-pack-qa.json --screenshot-dir artifacts\character-library-qa\xingxi-pixel-pet-v2-local-user-pack-screenshots --pet-seconds 0.5
```

结果：

```text
ok=true
default_character_id=original_oc
selected_character_id=xingxi_pixel_pet
after_switch_character_id=xingxi_pixel_pet
candidate_source=user
candidate_pack_path=character_packs\xingxi_pixel_pet
candidate_backend=sprite
desktop_backend=sprite
errors=[]
```

截图证据：

```text
artifacts/character-library-qa/xingxi-pixel-pet-v2-local-user-pack-screenshots/xingxi_pixel_pet-character-library.png
artifacts/character-library-qa/xingxi-pixel-pet-v2-local-user-pack-screenshots/xingxi_pixel_pet-desktop-pet.png
```

UI 结论：

- 角色库能找到本地 `xingxi_pixel_pet`；
- 角色详情明确显示 `Source: user`；
- 切换后控制面板和桌宠窗口均能使用 sprite backend；
- 默认角色仍是 `original_oc`；
- 没有修改 bundled assets、default pack 或 runtime manifest。

### art gate 结论

人工查看桌宠截图后，紫/洋红外边缘在透明桌宠窗口中明显可见。该问题已经不是纯检测噪声，而是真实可见的美术 blocker。

保留结论：

```text
candidate visual QA=ok=true, status=ready_with_warnings
candidate visual warning=suspicious_edge_halo_risk
suspicious_edge_halo_pixel_count=13790
suspicious_edge_halo_ratio=0.401047
default promotion allowed=false
```

已生成修边 brief：

```text
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/edge-style-brief-v2-local-smoke-20260618.json
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/edge-style-brief-v2-local-smoke-20260618.md
```

本包最终验证：

```powershell
git diff --check
<PYTHON311> -m pytest tests\test_character_library_qa_tool.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
<PYTHON311> -m pytest tests\test_character_pack_import_tool.py tests\test_pixel_pet_pack_validator_tool.py tests\test_pixel_pet_visual_qa.py tests\test_pixel_pet_edge_style_brief.py -q
<PYTHON311> -m pytest
```

结果：

```text
character library/app/desktop targeted tests=101 passed
art gate/import targeted tests=19 passed
full pytest=825 passed in 157.38s
```

下一步不应进入 optional bundled promotion。建议下一包改为：

```text
P3b-edge-style-repair
```

目标：

- 不重做产品架构；
- 不改默认角色；
- 不手工擦 runtime bundled spritesheet；
- 基于修边 brief 对 v2 candidate 做 edge-style repair 或重新生成 clean-edge candidate；
- 用真实桌宠截图和 `pixel_pet_visual_qa --fail-on-warnings` 共同验收；
- 只有修边通过后才继续 P4 LLM motion mapping 和 P5 optional bundled candidate promotion。

## 13. 2026-06-18 P3b edge-style repair 结果

本节记录 P3b 修边包的当前结果。结论：已得到一个可复现的 ignored clean-edge 候选包，通过自动门禁和桌宠 smoke；但它仍未进入 bundled assets，promotion 前仍需人工美术确认。

### 工具化修边

新增受测工具：

```text
tools/art/clean_pixel_pet_edge_halo.py
tests/test_pixel_pet_edge_halo_cleanup.py
```

工具边界：

- 只克隆一个完整 pixel-pet candidate pack 到新的 output 目录；
- 只处理 `spritesheet.png` 的透明边缘 halo；
- 高饱和红/洋红/紫色边缘像素删除为 `(0,0,0,0)`；
- 贴透明的近黑紫外轮廓重映射为深海军蓝；
- `alpha < 16` 的近透明像素归零，避免 Qt 平滑缩放时从透明 RGB 溢出紫边；
- 更新 output pack 的 `qa_report.json.edge_halo_cleanup`；
- 不修改源 candidate pack；
- 不修改 `assets\companion\xingxi_pixel_pet`；
- 不修改 `original_oc` 默认包或 runtime manifest。

TDD 验证：

```powershell
<PYTHON311> -m pytest tests\test_pixel_pet_edge_halo_cleanup.py -q
```

结果：`3 passed`。

### 当前 clean-edge 候选

已执行：

```powershell
<PYTHON311> tools\art\clean_pixel_pet_edge_halo.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\candidate-pack\xingxi_pixel_pet --output artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\xingxi_pixel_pet --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\edge-cleanup-report.json
```

结果摘要：

```text
ok=true
changed_pixel_count=86106
pass_changed_pixel_counts=[33319, 14887, 2503, 106, 43, 23, 8, 4, 35213]
visual_qa_before.status=ready_with_warnings
visual_qa_before.suspicious_edge_halo_pixel_count=13790
visual_qa_before.suspicious_edge_halo_ratio=0.401047
visual_qa_after.status=ready
visual_qa_after.suspicious_edge_halo_pixel_count=372
visual_qa_after.suspicious_edge_halo_ratio=0.008811
visual_qa_after.warnings=[]
```

输出路径：

```text
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/edge-repair-tool-cleaned-outline-rgb-alpha-20260618/xingxi_pixel_pet
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/edge-repair-tool-cleaned-outline-rgb-alpha-20260618/edge-cleanup-report.json
```

### 自动验证

已验证：

```powershell
<PYTHON311> tools\validate_pixel_pet_pack.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\xingxi_pixel_pet --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\candidate-pack-validation.json
<PYTHON311> tools\validate_character_pack.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\xingxi_pixel_pet
<PYTHON311> tools\art\pixel_pet_visual_qa.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\xingxi_pixel_pet\spritesheet.png --motion-manifest artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\xingxi_pixel_pet\motion_manifest.json --report artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\candidate-pack-visual-qa.json --preview artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\candidate-pack-visual-qa-preview.png --fail-on-warnings
```

结果：

```text
validate_pixel_pet_pack: ok=true
validate_character_pack: ok=true
pixel_pet_visual_qa: ok=true, status=ready, warnings=[]
```

### UI / desktop smoke

已执行：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
<PYTHON311> tools\character_library_qa.py --character-id xingxi_pixel_pet --character-root artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618 --report artifacts\character-library-qa\xingxi-pixel-pet-v2-edge-repair-outline-rgb-alpha-qa.json --screenshot-dir artifacts\character-library-qa\xingxi-pixel-pet-v2-edge-repair-outline-rgb-alpha-screenshots --pet-seconds 0.5
```

结果：

```text
ok=true
candidate_source=user
candidate_pack_path=artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\xingxi_pixel_pet
candidate_backend=sprite
desktop_backend=sprite
errors=[]
```

截图证据：

```text
artifacts/character-library-qa/xingxi-pixel-pet-v2-edge-repair-outline-rgb-alpha-screenshots/xingxi_pixel_pet-character-library.png
artifacts/character-library-qa/xingxi-pixel-pet-v2-edge-repair-outline-rgb-alpha-screenshots/xingxi_pixel_pet-desktop-pet.png
```

人工视觉结论：

- 原先亮洋红外边基本消失；
- 剩余主要是深色像素轮廓和少量发色边缘；
- 该候选可进入 P4 LLM motion mapping 复核；
- 仍不能直接默认推广；
- 若要替换 optional bundled `assets\companion\xingxi_pixel_pet`，需要先由人工确认这版轮廓是否可接受，并重新生成或同步 preview/contact-sheet。

下一步建议：

```text
P4-llm-motion-map
```

前置条件：

- 使用 clean-edge ignored candidate pack 的 `motion_manifest.json` 做 mapping 复核；
- 不修改默认角色；
- 不把 ignored candidate 直接提交到 bundled assets；
- 如果 P4 通过，再单独做 P5 optional bundled candidate promotion 包。

本包最终验证：

```powershell
git diff --check
<PYTHON311> -m pytest tests\test_pixel_pet_edge_halo_cleanup.py tests\test_pixel_pet_visual_qa.py tests\test_character_library_qa_tool.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
<PYTHON311> -m pytest
```

结果：

```text
targeted tests=107 passed
full pytest=828 passed in 138.29s
```

## 14. 2026-06-18 P4 LLM motion mapping 复核结果

本节记录 P4-llm-motion-map 的当前真实结果。结论：clean-edge ignored candidate pack 的 motion family 可承接当前 LLM visual actions；DeepSeek live expression cue probe 在修复连续 JSON 对象解析合同后通过，且没有写入成长、背包、关系、记忆、目标或存档。

### clean-edge candidate 映射复核

复核对象：

```text
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/edge-repair-tool-cleaned-outline-rgb-alpha-20260618/xingxi_pixel_pet
```

已执行：

```powershell
<PYTHON311> tools\pixel_pet_emote_mapping_check.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\xingxi_pixel_pet --json artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-emote-mapping.json --markdown artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-emote-mapping.md
```

结果：

```text
status=ready
missing_motion_ids=[]
unsupported_expression_ids=[]
required_motion_ids=Default, Play, Raised, Sleep, Study, SwitchDown, TouchHead
supported_expression_ids=blink, calm, confused, excited, focus, focused, goofy, happy, joy, neutral, play, sad, sadness, sleepy, smile, study, surprised, tired
```

当前 expression -> motion family 结论：

```text
blink/calm/neutral -> Default
confused/focus/focused/study -> Study
excited/goofy/play -> Play
happy/joy/smile -> TouchHead
sad/sadness -> SwitchDown
sleepy/tired -> Sleep
surprised -> Raised
```

### DeepSeek live probe 问题与修复

首次 live probe 写入：

```text
artifacts/llm_smoke/deepseek-expression-cue-probe-clean-edge-live-20260618.json
```

结果：

```text
ok=false
reason=cue:sleepy:fallback:unsafe_event
passed_count=4
failed_count=1
failed_case=sleepy
state_mutation_check.ok=true
state_mutation_check.changed_fields=[]
```

失败不是状态越权，状态守卫正常；问题是 LLM 在 `sleepy/晚安` 场景下可能输出带 `intent_hint` 的连续 JSON speech 对象，而旧 object-stream parser 的允许字段没有与当前 speech schema 对齐，导致安全回退并丢失表演 cue。

本包按 TDD 修复：

```text
src/guanghe_companion/dialogue_parser.py
src/guanghe_companion/expression_parser.py
src/guanghe_companion/expression_expressor.py
tests/test_ai_expressor.py
tests/test_expression_parser.py
```

修复边界：

- `intent_hint` 仍是只读互动意图，不是状态写入；
- 连续 JSON 对象路径保留 speech schema，后续统一抽取 expression/motion/intent；
- state mutation 字段仍被拒绝；
- overlong/control-character motion 或 intent hint 仍被拒绝；
- 不改养成状态机、背包、关系、记忆、目标或存档。

TDD 验证：

```powershell
<PYTHON311> -m pytest tests\test_ai_expressor.py tests\test_expression_parser.py tests\test_dialogue.py -q
```

结果：

```text
137 passed
```

### DeepSeek live rerun

已执行：

```powershell
<PYTHON311> tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\deepseek-expression-cue-probe-clean-edge-live-rerun-20260618.json
```

结果：

```text
ok=true
reason=
probe_count=5
passed_count=5
failed_count=0
fallback_reason for all cases=
speech_quality.violations=[]
state_mutation_check.ok=true
state_mutation_check.changed_fields=[]
```

case 覆盖：

```text
joy -> expression joy, motion TouchHead/Raised, intent celebrate
sadness -> expression sadness, motion SwitchDown/TouchHead, intent ask_comfort
sleepy -> expression sleepy, motion Sleep, intent offer_rest
focused -> expression focused, motion Study, intent stay_quiet
surprised -> expression surprised, motion Raised
```

本包最终验证：

```powershell
git diff --check
<PYTHON311> -m pytest tests\test_pixel_pet_emote_mapping.py tests\test_visual_actions.py tests\test_presentation_renderer.py tests\test_expression_event_pipeline.py tests\test_llm_smoke.py tests\test_ai_expressor.py tests\test_expression_parser.py tests\test_dialogue.py tests\test_companion_dialogue_policy.py -q
<PYTHON311> -m pytest
```

结果：

```text
P4 targeted tests=179 passed
full pytest=829 passed in 121.77s
```

P4 当前结论：

- LLM 可以作为表现力核心驱动 speech、expression、motion 和只读 interaction intent；
- 当前证据不支持让 LLM 接管成长状态机；
- clean-edge candidate 可以继续进入 P5 optional bundled candidate promotion 评估；
- 进入 P5 前仍不得替换默认 `original_oc`，不得把 ignored candidate 直接提交为默认资产；
- P5 需要单独跑 UI、full pytest、visual QA、release readiness；若涉及冻结包或安装器，再跑 Windows app/installer gates。

## 15. 2026-06-18 P5 promotion preflight 结果

本节记录 P5-optional-bundled-candidate-promotion 的预检进展。结论：clean-edge ignored candidate 的自动门禁已经足以进入人工美术决策，但缺少明确 `manual_qa.json`，因此当前状态是 `needs_manual_qa`，不是可直接替换 bundled assets。

### 新增 preflight 工具

新增受测工具：

```text
tools/pixel_pet_promotion_preflight.py
tests/test_pixel_pet_promotion_preflight.py
```

工具边界：

- 复用现有 `validate_pixel_pet_pack.py`、runtime character-pack validator、`pixel_pet_visual_qa.py` 和 `pixel_pet_emote_mapping_check.py`；
- 将 deterministic checks 与人工 QA 决策分开报告；
- 不复制、不移动、不替换任何 `assets/companion` 文件；
- 不修改 runtime manifest；
- 不把缺人工批准伪装成可推广，只输出 `needs_manual_qa`。

### clean-edge candidate preflight

复核对象：

```text
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/edge-repair-tool-cleaned-outline-rgb-alpha-20260618/xingxi_pixel_pet
```

已执行：

```powershell
<PYTHON311> tools\pixel_pet_promotion_preflight.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet_edge_style_v2\edge-repair-tool-cleaned-outline-rgb-alpha-20260618\xingxi_pixel_pet --report artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-promotion-preflight.json
```

结果：

```text
ok=false
status=needs_manual_qa
deterministic_ok=true
manual_qa_status=missing
character_id=xingxi_pixel_pet
pixel_pack_validation=ready
runtime_character_pack_validation=ready
pixel_visual_qa=ready
llm_emote_mapping=ready
manual_qa_decision=missing
next_action=manual QA decision is required before bundled promotion
```

本包最终验证：

```powershell
<PYTHON311> -m pytest tests\test_pixel_pet_promotion_preflight.py tests\test_pixel_pet_promotion_gate.py tests\test_pixel_pet_pack_validator_tool.py tests\test_pixel_pet_visual_qa.py tests\test_pixel_pet_emote_mapping.py -q
<PYTHON311> -m pytest
```

结果：

```text
P5 promotion/preflight targeted tests=19 passed
full pytest=832 passed in 104.16s
```

P5 当前结论：

- clean-edge candidate 已通过自动 promotion preflight；
- 仍未进入 `assets/companion/xingxi_pixel_pet`；
- 仍未替换默认 `original_oc`；
- 下一步必须先产生明确人工美术 QA 结论和 `manual_qa.json`；
- 只有 `manual_qa.manual_decision` 以 `promotion_gate_candidate` 开头，并且 deterministic checks 全部为 true 后，才可运行 `tools/pixel_pet_promotion_gate.py`；
- promotion gate 通过后仍需要单独执行 bundled asset copy/update、UI smoke、full pytest、release readiness；若涉及冻结包或安装器，再跑 Windows app/installer gates。

## 16. 2026-06-18 P5 optional bundled clean-edge promotion 结果

本节记录 clean-edge Xingxi pixel-pet 从 ignored candidate 晋升为 optional bundled candidate 的真实结果。结论：`assets/companion/xingxi_pixel_pet` 已替换为 clean-edge 版本，仍不改变默认 `original_oc`，并已完成源码包、UI、LLM 映射、Windows app、installer 和 frozen exe smoke 验证。

### 人工/视觉 QA 证据

已人工查看：

```text
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/edge-repair-tool-cleaned-outline-rgb-alpha-20260618/xingxi_pixel_pet/preview/contact-sheet.png
artifacts/pixel-pet-sequence-drafts/xingxi_pixel_pet_edge_style_v2/edge-repair-tool-cleaned-outline-rgb-alpha-20260618/candidate-pack-visual-qa-preview.png
artifacts/character-library-qa/xingxi-pixel-pet-v2-edge-repair-outline-rgb-alpha-screenshots/xingxi_pixel_pet-desktop-pet.png
```

视觉结论：

```text
identity_consistency_ok=true
contact_sheet_rows_readable=true
idle_blink_ok=true
waiting_blink_ok=true
running_direction_readable=true
failed_and_review_expressions_readable=true
waving_readable_but_conservative=true
bright_magenta_halo_removed=true
remaining_dark_outline_acceptable=true
desktop_small_size_readable=true
```

已写入 bundled 包：

```text
assets/companion/xingxi_pixel_pet/manual_qa.json
assets/companion/xingxi_pixel_pet/qa_report.json
assets/companion/xingxi_pixel_pet/provenance.md
```

关键边界：

```text
manual_decision=promotion_gate_candidate_clean_edge_optional_bundled
runtime_manifest_updated=false
default_character_updated=false
distribution_boundary=official_candidate
```

### promoted files

本包替换的 runtime assets：

```text
assets/companion/xingxi_pixel_pet/spritesheet.png
assets/companion/xingxi_pixel_pet/preview/contact-sheet.png
assets/companion/xingxi_pixel_pet/manual_qa.json
assets/companion/xingxi_pixel_pet/qa_report.json
assets/companion/xingxi_pixel_pet/provenance.md
```

复制时未删除角色包中的其他文件；`character.json`、`dialogue_style.json`、`motion_manifest.json`、`shop_items.json`、`LICENSE.md` 和 `item_icons/` 文件集与 clean-edge candidate 对齐，git diff 只显示发生实际内容变化的文件。

### 源码包验证

已执行：

```powershell
<PYTHON311> tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
<PYTHON311> tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-bundled-pack-validation.json
<PYTHON311> tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-bundled-visual-qa.json --preview artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-bundled-visual-qa-preview.png --fail-on-warnings
<PYTHON311> tools\pixel_pet_emote_mapping_check.py assets\companion\xingxi_pixel_pet --json artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-bundled-emote-mapping.json --markdown artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-bundled-emote-mapping.md
<PYTHON311> tools\pixel_pet_promotion_gate.py assets\companion\xingxi_pixel_pet --manual-qa assets\companion\xingxi_pixel_pet\manual_qa.json --report artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-bundled-promotion-gate.json
```

结果：

```text
validate_character_pack=ok
validate_pixel_pet_pack=ok
pixel_visual_qa=status ready, warnings=[]
pixel_visual_qa.suspicious_edge_halo_pixel_count=372
pixel_visual_qa.suspicious_edge_halo_ratio=0.008811
pixel_emote_mapping=status ready, missing_motion_ids=[]
promotion_gate=ok, warnings=[]
```

### UI / desktop smoke

已执行：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
<PYTHON311> tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\xingxi-pixel-pet-clean-edge-bundled-qa.json --screenshot-dir artifacts\character-library-qa\xingxi-pixel-pet-clean-edge-bundled-screenshots --pet-seconds 0.5
```

结果：

```text
ok=true
default_character_id=original_oc
selected_character_id=xingxi_pixel_pet
after_switch_character_id=xingxi_pixel_pet
candidate_source=builtin
candidate_backend=sprite
desktop_backend=sprite
errors=[]
```

### Python tests

已执行：

```powershell
<PYTHON311> -m pytest tests\test_character_pack.py tests\test_character_registry.py tests\test_character_pack_import_tool.py tests\test_character_library_qa_tool.py tests\test_pixel_pet_promotion_preflight.py tests\test_pixel_pet_promotion_gate.py tests\test_pixel_pet_pack_validator_tool.py tests\test_pixel_pet_visual_qa.py tests\test_pixel_pet_emote_mapping.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
<PYTHON311> -m pytest
```

结果：

```text
asset/UI targeted tests=161 passed
full pytest=832 passed in 135.06s
```

### Windows build / installer / frozen smoke

已执行：

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1 -PythonPath <PYTHON311>
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild -PythonPath <PYTHON311>
<PYTHON311> tools\validate_windows_build.py --report artifacts\windows-build-validation.json
```

结果：

```text
Windows app build=ok, dist\E-Moti\E-Moti.exe rebuilt
installer build=ok, dist\installer\E-Moti_Setup_0.1.0.exe rebuilt
validate_windows_build=ok
```

额外验证 optional bundled pack 已进入 frozen dist：

```text
assets/companion/xingxi_pixel_pet/spritesheet.png SHA256 == dist/E-Moti/_internal/assets/companion/xingxi_pixel_pet/spritesheet.png SHA256
assets/companion/xingxi_pixel_pet/manual_qa.json SHA256 == dist/E-Moti/_internal/assets/companion/xingxi_pixel_pet/manual_qa.json SHA256
dist/E-Moti/_internal/assets/companion/xingxi_pixel_pet validate_character_pack=ok
dist/E-Moti/_internal/assets/companion/xingxi_pixel_pet validate_pixel_pet_pack=ok
```

Frozen exe smoke：

```text
dist\E-Moti\E-Moti.exe control panel 5s smoke=ok
dist\E-Moti\E-Moti.exe --pet-mode 5s smoke=ok
```

### final release readiness

已执行：

```powershell
<PYTHON311> tools\release_readiness_report.py --character-pack assets\companion\xingxi_pixel_pet --llm-report artifacts\llm_smoke\deepseek-expression-cue-probe-clean-edge-live-rerun-20260618.json --pixel-pet-emote-mapping-report artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-bundled-emote-mapping.json --pixel-pet-visual-qa-report artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-bundled-visual-qa.json --json artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-bundled-release-readiness-final.json --markdown artifacts\route-scan-20260618\xingxi-pixel-pet-clean-edge-bundled-release-readiness-final.md
```

结果：

```text
ok=true
status=ready
check_count=5
ready_check_count=5
attention_check_count=0
```

P5 当前结论：

- `xingxi_pixel_pet` clean-edge 版本现在是 optional bundled candidate；
- 默认角色仍是 `original_oc`；
- 没有改变 runtime default manifest；
- Ikaros/Nairong 仍不进入开源 bundled assets；
- 下一步只有在明确要做默认角色替换时，才进入单独的 P6-default-promotion 包。
