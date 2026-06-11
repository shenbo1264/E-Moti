# E-Moti Current Development Route 2026-06-11

本文档基于 2026-06-11 对当前仓库的实测扫描，不继承未验证的历史结论。

## 1. 实测基线

- 工作目录：仓库根目录
- 当前分支：`codex/demo-worktree-cleanup`
- 路线初始扫描 HEAD：`ac1822f docs: correct art route to pixel pet sequences`
- 路线初始扫描工作区：`git status --short --untracked-files=all` 输出为空，工作区 clean。
- 远端：当前本地 checkout 配置了公开仓库远端和私有备份远端；文档不记录私有远端 URL。
- 测试结果：`python -m pytest` 通过，`754 passed in 117.34s`。
- JSON/角色包校验：
  - `python -m json.tool assets\companion\original_oc\shop_items.json` 通过。
  - `python tools\validate_character_pack.py assets\companion\original_oc` 通过，`ok=true`。
- Release readiness 聚合：`python tools\release_readiness_report.py --full-local-snapshot ...` 返回 `needs_attention`，`15` 项检查中 `8` 项 ready、`7` 项 attention。

## 2. 当前阶段判断

项目不是空架子，也不是只剩美术问题。当前代码层已经有可演示基线：

- PySide6 控制面板与桌宠窗口；
- 系统托盘生命周期；
- 本地养成状态机、商店、背包、关系、记忆、存档；
- 角色库、角色切换、用户角色包导入门禁；
- `sprite`、`portrait`、`live2d_web` 三类呈现后端边界；
- LLM 表达链路、表达事件、视觉动作、交互意图；
- 屏幕观察、搜索、TTS、ASR 的能力设置与运行边界；
- Windows frozen app / installer 校验工具；
- 大量 art / portrait / video / readiness 工具链。

真正的近期问题是产品路线需要收敛：旧的精细 VN portrait / AI-video 路线已经证明容易产生体漂移、边缘光晕、表情集不完整和推广门禁阻断。近期应把主路线收回到 hatch-pet 风格的紧凑像素宠序列帧。

## 3. 路线结论

### 主路线

近期主路线改为：

```text
三角色像素宠候选
-> canonical base 锁形体
-> 每次只做一个动作 row
-> contact-sheet QA
-> 修失败 row
-> 拼装 spritesheet + motion_manifest
-> 角色包校验
-> 本地导入验证
-> 仅星汐可进入开源默认包候选
```

这条路线对应 `docs\pixel_pet_sequence_sop.md`，而不是旧的精细 VN portrait / AI-video-first 路线。

### 暂停路线

以下路线暂不作为近期主线：

- AI-video 直接生成可用序列帧；
- LivePortrait 本地推理；
- Live2D 正式模型制作与运行时接入；
- 精细 VN portrait 资产推广到默认 manifest。

原因来自当前 readiness 报告：

- portrait AI-video workflow：`failed_motion_extraction`、`body_drift_warnings`；
- portrait candidate：未 approved，缺少 `smile/thinking/surprised/sad/sleepy`，缺少 blink frames，并有 `light_edge_halo_risk`；
- LivePortrait preflight：缺少 pretrained weights 和 driving video；
- frame visual QA：`max body drift: 44.72`，超过可接受阈值。

这些不是要删除，而是降级为后续研究线，不能阻塞近期可演示版本。

## 4. 三角色方案

### 星汐

- 定位：项目原创 OC，未来可成为默认开源角色包。
- 路线：基于现有星汐人设与已形成的角色生成 SOP，重制为 hatch-pet 风格像素宠序列帧。
- 分发：通过 QA、provenance、LICENSE、角色包校验后，可以作为可切换的内置候选进入 `assets/companion/`；是否替换默认 `original_oc` 是另一个独立决策。

### 伊卡洛斯

- 定位：UGC 二创代表，用来验证“用户想基于已有二次元角色创建私有角色包”的流程。
- 路线：只验证 workflow、素材隔离、导入门禁、版权提示和角色切换体验。
- 分发：不得作为开源默认资产分发，除非完成权利确认。

### 奶龙

- 定位：UGC 宠物向代表。
- 路线：以 `base_source_v2.png` 锁默认形体，以 `base_source_v5_ref03_goofy.png` 作为特殊傻感表情参考。
- 默认动作族：
  - `idle_breathe`
  - `normal_blink`
  - `small_paw_movement`
- 特殊表情族：
  - `goofy`
  - `confused`
  - `rolled_eye_blink`
  - `tongue_out_mouth_frames`
  - `awkward_arm_drop`
- 分发：不得作为开源默认资产分发，除非完成权利确认。

## 5. 现有架构判断

### 已经相对解耦的部分

- 状态机和 AI 表达已分离：`CompanionController` 仍是状态、背包、关系、记忆、存档的权威入口；LLM 走 typed event / visual action。
- 呈现后端有适配层：`presentation_renderer.py` 把 snapshot 映射到 `sprite`、`portrait`、`live2d_web` frame。
- 角色包边界已经存在：`character_registry.py`、`character_session.py`、导入工具和 UI 能处理内置包与用户包。
- 能力模块可开关：screen observation、web search、TTS、ASR 有设置与 runtime 服务，不直接接管养成状态。
- QA 工具覆盖较完整：测试数已经到 754，且 readiness、portrait、video、character pack 工具链都有自动化报告。

### 仍然偏耦合或容易误导的部分

- 文档口径仍有冲突：`AGENTS.md`、`README.md` 和历史 roadmap 仍强调 Spirit/GalGame 或 VN portrait，而最新路线已转向 pixel pet sequence。
- 美术路线工具过重：portrait/video/readiness 工具链很强，但当前主路线需要的是小像素宠 row production，旧工具容易把工作带回 AI-video 漂移问题。
- 角色资产还没有正式包：三角色目前是 ignored 草稿或方案记录，不是 runtime-ready pack。
- LLM 表达虽然有 smoke 和 QA 报告，但“表现力调优”与“角色动作映射到像素 row”还没有形成稳定闭环。
- `app.py` 仍是较大的集成层，UI、托盘、能力面板、角色库、TTS/ASR、渲染同步都集中在一个窗口类中。近期不应大拆，但后续可以把角色库、能力运行、桌宠窗口同步进一步剥离。

## 6. 下一阶段开发包

### P0-doc-sync：统一公开口径

目标：防止后续 agent 或开源读者继续沿着旧 VN portrait 主线推进。

范围：

- 更新 `AGENTS.md` 的 Current Product Route；
- 更新 `README.md` 中关于主视觉路线的表述；
- 标记历史 Spirit/VN/AI-video 文档为 historical / research path；
- 保留 `docs\pixel_pet_sequence_sop.md` 为近期主 SOP。

验收：

```powershell
git diff --check
python -m pytest tests\test_repository_hygiene.py -q
python -m pytest
```

停止点：

- 不删除历史文档，除非另行确认；
- 不修改运行时代码；
- 不提交 ignored 草稿素材。

当前检查点：`AGENTS.md` 与 `README.md` 已同步为 hatch-pet 风格像素宠序列帧主线，Spirit/GalGame、AI-video、LivePortrait、Live2D 均降级为研究或后续 renderer 路径。已通过 `git diff --check`、`python -m pytest tests\test_repository_hygiene.py -q` 和全量 `python -m pytest`。

### P1-pixel-pack-contract：定义像素宠角色包合同

目标：把 hatch-pet 输出从“草稿图”推进到可校验的候选角色包格式。

建议包形：

```text
character_packs_drafts/<character_id>/
  character.json
  dialogue_style.json
  motion_manifest.json
  spritesheet.png
  preview/contact-sheet.png
  provenance.md
  qa_report.json
```

范围：

- 新增或扩展候选像素宠 pack validator；
- 复用 `validate_companion_atlas.py` 校验 `192x208`、9 行动作、RGBA；
- 明确 UGC pack 只能在本地用户包或 ignored 草稿区流转；
- 不接入默认 manifest。

验收：

```powershell
python tools\validate_pixel_pet_pack.py path\to\character_packs_drafts\<character_id>
python -m pytest tests\test_pixel_pet_pack_validator_tool.py tests\test_art_tools.py tests\test_character_pack.py tests\test_character_pack_validator_tool.py -q
python -m pytest
```

当前检查点：星汐像素宠候选已组装为 ignored 草稿包 `artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\character_packs_drafts\xingxi_pixel_pet`，包含 `character.json`、`dialogue_style.json`、`motion_manifest.json`、`spritesheet.png`、`preview\contact-sheet.png`、`provenance.md` 和 `qa_report.json`。已执行 JSON 校验、`python tools\validate_pixel_pet_pack.py ... --report ...\pixel_pack_validation_report.json`，结果 `ok=true`、`distribution_boundary=official_candidate`、`errors=[]`；定向测试 `38 passed`。人工视觉抽查认为整体身份一致、`idle`/`waiting` 有眨眼、左右跑动为独立生成方向；`jumping` 与 `failed` 有个别帧比例更大，推广前仍需人工 QA。默认 runtime manifest 仍未更新。

### P2-xingxi-canonical-base：星汐默认形体定稿

目标：先把星汐这一个原创角色的 canonical base 做稳。

范围：

- 使用 hatch-pet 思路生成或修正星汐 base；
- 只保留 1 个候选方向；
- 生成 QA 对照图；
- 记录 prompt、provenance、拒绝项；
- 不更新 `assets/companion/original_oc`。

验收：

```powershell
python -m json.tool artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\character_definition.json
python tools\art\review_pixel_pet_base.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\hatch_run\decoded\base.png --character-id xingxi_pixel_pet --prompt artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\hatch_run\prompts\base-pet.md --character-definition artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\character_definition.json --prior-qa artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\first-row-qa.json --decision accepted_for_row_testing --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\base-review-20260611
python -m json.tool artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\base-review-20260611\base-review.json
python -m pytest tests\test_pixel_pet_base_review.py tests\test_art_tools.py -q
git status --short --untracked-files=all
```

`review_pixel_pet_base.py` only approves ignored candidate flow. It records prompt/provenance links, confirms `runtime_manifest_updated=false`, and turns near-`#FF00FF` background pollution into a cleanup warning for the later slicing step rather than runtime approval.

人工 QA：

- 是否像星汐；
- 是否足够小宠物化；
- 是否适合 192x208 序列帧；
- 是否没有跑回精细 GalGame 立绘。

### P3-xingxi-first-row：只做一个动作 row

目标：不要一次生成全套动作，先用 `idle` 或 `Default` 验证序列帧方法。

范围：

- 以星汐 canonical base 为约束；
- 生成 `idle_breathe + blink` 一行；
- 输出 contact sheet；
- 跑 atlas 或局部 frame 校验；
- 视觉不合格只修这一行。

验收：

```powershell
python tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\idle-current-frames --state idle --expected-frames 6 --decision needs_regeneration --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\idle-current-row-review
python tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\idle-blink-regenerated-20260611-frames --state idle --expected-frames 6 --decision accepted_for_row_testing --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\idle-blink-regenerated-20260611-row-review
python tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\running-right-current-frames --state running-right --expected-frames 8 --decision accepted_for_row_testing --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\running-right-current-row-review
python tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\waiting-regenerated-20260611-frames --state waiting --expected-frames 6 --decision accepted_for_row_testing --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\waiting-regenerated-20260611-row-review
python tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\jumping-regenerated-20260611-frames --state jumping --expected-frames 5 --decision accepted_for_row_testing --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\jumping-regenerated-20260611-row-review
python tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\waving-regenerated-20260611-frames --state waving --expected-frames 4 --decision accepted_for_row_testing --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\waving-regenerated-20260611-row-review
python tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\running-left-regenerated-20260611-frames --state running-left --expected-frames 8 --decision accepted_for_row_testing --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\running-left-regenerated-20260611-row-review
python tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\failed-regenerated-20260611-frames --state failed --expected-frames 8 --decision accepted_for_row_testing --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\failed-regenerated-20260611-row-review
python tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\running-regenerated-20260611-frames --state running --expected-frames 6 --decision accepted_for_row_testing --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\running-regenerated-20260611-row-review
python tools\art\review_pixel_pet_row_candidate.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\review-regenerated-20260611-frames --state review --expected-frames 6 --decision accepted_for_row_testing --require-components --output-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\review\review-regenerated-20260611-row-review
python $env:CODEX_HOME\skills\hatch-pet\scripts\finalize_pet_run.py --run-dir artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\hatch_run --skip-videos
python -m pytest tests\test_pixel_pet_row_review.py tests\test_art_tools.py tests\test_motion.py -q
python -m pytest
```

当前检查点：旧 `idle-current` row 已明确保留为失败证据，因为它只能 slot 抽帧且缺少明确 blink；新的九行 Xingxi pixel-pet 候选已通过 component 抽帧、逐行 row review 和 `finalize_pet_run --skip-videos`。最终候选输出在 ignored `artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\hatch_run\final\spritesheet.webp`，QA contact sheet 在 `...\qa\contact-sheet.png`，`runtime_manifest_updated=false`。`waiting` 曾有 motion delta 偏低的行级警告，但整体 finalize review 无错误/警告，肉眼可读为等待眨眼候选。该候选已进一步转成可验证 P1 草稿包；在完整人工 QA 与 runtime import/smoke 前不更新默认 runtime manifest。

### P4-llm-to-emote-map：让 LLM 表达映射到像素动作

目标：AI 是核心，但只负责“选择表演”，不拥有养成状态机。

范围：

- 把 `visual_actions.expression` 映射到像素宠表情或动作族；
- 示例：`goofy`、`confused`、`sleepy`、`joy`、`focused`；
- 为奶龙保留 `v2 default` 与 `v5 goofy` 的双层映射；
- 不让 LLM 写 state、coins、inventory、relationship、memory、goals、save。

验收：

```powershell
python -m pytest tests\test_visual_actions.py tests\test_presentation_renderer.py tests\test_expression_event_pipeline.py -q
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest
```

当前检查点：sprite fallback 已能把 `visual_actions.expression` 中的 `joy`、`focused`、`sleepy`、`surprised`、`goofy`、`confused` 等安全表演标签映射到现有 motion family；显式 `visual_actions.motion` 仍优先。这只发生在 renderer adapter 层，不写 state、coins、inventory、relationship、memory、goals 或 save。

### P5-user-pack-local-import：三角色本地切换演示

目标：形成“官方星汐 + 本地 UGC 包”的演示闭环。

范围：

- 星汐可以作为候选官方包；
- 伊卡洛斯、奶龙只作为本地 UGC pack；
- 角色库 UI 展示 provenance、license、distribution boundary；
- 本地导入前必须确认；
- 每个角色记忆、存档、关系独立。

验收：

```powershell
python -m pytest tests\test_character_registry.py tests\test_character_session.py tests\test_character_pack_import_tool.py tests\test_app.py -q
python -m pytest
```

当前检查点：
- runtime pack 可在 `character.json.distribution_boundary` 声明 `shareable_after_review`、`local_ugc_only` 或 `private_local_fanwork`；
- 角色注册表摘要、导入工具 JSON、角色库详情、导入确认弹窗、状态审查工具统一读取并展示该字段；
- 这只解决“开源候选包”和“本地 UGC / 二创包”的解释边界，不代表伊卡洛斯、奶龙素材可以进入开源默认资产。
- 星汐 P1 草稿包已补齐 runtime user-pack 所需的非美术元数据、`shop_items.json` 和 item icons，并通过 `python tools\validate_character_pack.py artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\character_packs_drafts\xingxi_pixel_pet`。
- 已执行 `python tools\import_character_pack.py ... --target-root artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\local_user_pack_root --force`，导入报告写入 ignored `...\xingxi_pixel_pet_import_report.json`，结果 `ok=true`、`distribution_boundary=shareable_after_review`。
- 已用 `CharacterRegistry` 从 ignored local user-pack root 列出 `xingxi_pixel_pet`，来源为 `user`，preview 存在；已用 `load_character_pack_from_dir` 和 `load_motion_catalog_from_dir` 读取 sprite backend、8 列 9 行 atlas、全部动作映射，并确认未知动作回退到 `Default`。
- 已跑 P5 相关测试 `python -m pytest tests\test_character_registry.py tests\test_character_session.py tests\test_character_pack_import_tool.py tests\test_app.py tests\test_desktop_pet_smoke.py -q`，结果 `132 passed`。
- 已补 `private_local_fanwork` 作为像素宠草稿包 validator 允许的更严格 UGC 边界；`_ugc_` 角色仍会拒绝 `official_candidate`。
- 已记录星汐人工 QA：当前包可保留为本地导入候选，但 `jumping` 与 `failed` 有比例跳变，不能直接推广到默认资产。
- 已为伊卡洛斯与奶龙建立 ignored local UGC 分支边界记录，只写权利与 QA 计划，不生成、不提交、不分发资产。
- 已通过 subagent + `$imagegen` 局部重生星汐 `jumping` 与 `failed` 两行；两个候选均通过 component 抽帧和 row review，重新 `finalize_pet_run --skip-videos` 后整包 validation/review 均 `ok=true`、无 warnings。
- 已刷新 ignored 草稿包和 local user-pack import smoke；`Play` 指向修复后的 `jumping` row，`SwitchDown` 指向修复后的 `failed` row。默认 runtime manifest 仍未更新。
- 已新增并执行 `tools\pixel_pet_promotion_gate.py`；当前星汐候选的 promotion gate 报告写入 ignored `artifacts\pixel-pet-sequence-drafts\xingxi_pixel_pet\promotion_gate\pixel_pet_promotion_gate_report.json`，结果 `ok=true`、`errors=[]`、`warnings=[]`。
- 已按 promotion gate 下一包要求重跑 pixel pack validation、runtime character pack validation、local import smoke、UI smoke 和全量测试；默认资产仍未替换。
- 已新增 `assets\companion\xingxi_pixel_pet` 作为可切换的内置 sprite 候选包，包含 curated `spritesheet.png`、`motion_manifest.json`、角色 metadata、shop items、item icons、contact sheet、provenance、license 和 manual QA summary。
- 当前默认包仍是 `assets\companion\original_oc`；`load_default_character_pack()` 返回 `original_oc`，`CharacterRegistry` 同时列出 `original_oc` 与 `xingxi_pixel_pet`。
- 新内置候选包已通过 `python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet`、`python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet --report ...\bundled_pixel_pack_validation_report.json` 和 `python tools\pixel_pet_promotion_gate.py assets\companion\xingxi_pixel_pet --manual-qa assets\companion\xingxi_pixel_pet\manual_qa.json --report ...\bundled_pixel_pet_promotion_gate_report.json`，结果均为 `ok=true` 且 promotion gate `warnings=[]`。
- 已通过 `python -m pytest tests\test_character_pack.py -q`（`7 passed`）、角色包/注册表/导入/promotion 定向测试（`53 passed`）以及 UI / 桌宠 smoke（`95 passed`）。
- 已刷新全量 `python -m pytest`，结果 `784 passed`。
- 打包过程中发现并修复了一个真实阻断：`tools\build_windows_app.ps1` 原先只 staging `assets\companion\original_oc`，导致新增内置包不会进入 frozen app；现改为 staging 整个 `assets\companion`。
- `tools\validate_windows_build.py` 已按 renderer 类型检查 frozen 角色资产：portrait 包检查 portrait 资产，sprite 包检查 spritesheet、motion manifest、provenance、preview、item icons 和 license。
- 已重新执行 `powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1`、`powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild`、`python tools\validate_windows_build.py --report artifacts\windows-build-validation.json`、`python tools\validate_windows_build.py --character-id xingxi_pixel_pet --report artifacts\windows-build-validation-xingxi-pixel-pet.json`，结果均通过；frozen 控制面板和 `--pet-mode` 5 秒 smoke 均保持运行并被手动结束。
- 已新增 `tools\character_library_qa.py`，可用临时用户数据打开真实控制面板，选择 `xingxi_pixel_pet`，验证 distribution/provenance/license 详情，切换角色，打开桌宠模式，保存角色库与桌宠截图，并输出 JSON 报告。
- 角色库 QA 首轮截图发现详情文本会被按钮区域截断；已将角色详情文本放入可滚动区域并补 `test_character_library_detail_metadata_is_scrollable` 回归。
- 已运行 `python tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\xingxi-pixel-pet-character-library-qa.json --screenshot-dir artifacts\character-library-qa\screenshots --pet-seconds 0.5`，报告 `ok=true`、默认仍为 `original_oc`、切换后为 `xingxi_pixel_pet`、桌宠 backend 为 `sprite`、`errors=[]`。截图显示角色库 metadata 完整可见，桌宠 sprite 正常渲染。
- 已运行 `python -m pytest tests\test_character_library_qa_tool.py tests\test_app.py tests\test_desktop_pet_smoke.py -q`，结果 `98 passed`；`python -m pytest tests\test_character_pack.py tests\test_character_registry.py tests\test_windows_packaging_scripts.py tests\test_windows_build_validator.py -q`，结果 `44 passed`；全量 `python -m pytest`，结果 `787 passed`。
- 已在非 offscreen 环境运行 `python tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\xingxi-pixel-pet-character-library-qa-real-desktop.json --screenshot-dir artifacts\character-library-qa\real-desktop-screenshots --pet-seconds 1.0`，报告 `ok=true`。功能链路可用，但截图仍显示透明背景捕获为黑底，且角色边缘有明显紫色描边/halo；这不阻止候选展示，但阻止默认替换。
- 已新增并运行 `python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --report artifacts\character-library-qa\xingxi-pixel-pet-visual-qa.json --preview artifacts\character-library-qa\xingxi-pixel-pet-visual-qa-preview.png`，报告 `ok=true` 但 `status=ready_with_warnings`，`edge_pixel_count=37202`，`suspicious_edge_halo_pixel_count=13883`，`suspicious_edge_halo_ratio=0.373179`，warnings 为 `suspicious_edge_halo_risk`。
- 已人工查看 `artifacts\character-library-qa\xingxi-pixel-pet-visual-qa-preview.png` overlay：可疑像素主要集中在头发外轮廓与阴影线稿上，说明不能直接做无脑透明擦边，否则会破坏角色轮廓；该报告用于默认推广门禁和人工美术判断，不是自动清理指令。
- 已验证 `python tools\art\pixel_pet_visual_qa.py assets\companion\xingxi_pixel_pet\spritesheet.png --motion-manifest assets\companion\xingxi_pixel_pet\motion_manifest.json --fail-on-warnings` 会返回失败码 `1`，因此该候选在边缘修复或重生前不能走默认推广包。
- 当前默认决策：继续保持 `original_oc` 为默认包，`xingxi_pixel_pet` 作为可切换内置候选；是否默认替换留给真实桌面人工美术 QA 后的独立包。

### P6-release-package-check：演示版打包复核

触发条件：只有在运行时 manifest、默认资产或安装器行为改变后才执行。

验收：

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\windows-build-validation.json
python -m pytest
```

## 7. 不要做的事

- 不要继续围绕失败的 AI-video 方案无意义迭代。
- 不要把伊卡洛斯、奶龙素材放进开源默认资产。
- 不要把 ignored 草稿图直接写进 runtime manifest。
- 不要在没有 TDD 和验收命令的情况下拆 `app.py`。
- 不要让 LLM 修改成长状态、背包、关系、记忆、目标或存档。
- 不要新增鼠标、键盘、剪贴板、窗口控制。
- 不要把 Live2D 作为近期阻塞项。

## 8. 推荐立即执行的下一包

`P0-doc-sync`、星汐 `P1-pixel-pack-contract`、星汐 `P5-user-pack-local-import`、`P5-manual-qa-and-ugc-branching`、`P5-xingxi-row-repair-or-promotion-decision`、`P5-xingxi-promotion-gate-package`、`P5-bundled-asset-promotion-decision`、`P5-character-library-qa-and-default-decision`、以及 `P5-real-desktop-art-qa-edge-gate` 已完成当前验证。建议下一包做 `P5-xingxi-edge-style-decision`：

- 不建议直接对当前 `xingxi_pixel_pet` 做确定性透明擦边，因为 overlay 显示该指标命中了头发外轮廓和线稿；
- 优先做一版新的 hatch-pet 候选或人工重绘候选，要求提示词明确避免红/紫发光边、色边和外圈 halo，同时保留蓝紫发色本体；
- 也可以人工确认接受当前外轮廓作为风格选择，但这必须是明确美术 QA 结论，而不是因为工具通过；
- 每个修复候选必须重新跑 `pixel_pet_visual_qa.py --fail-on-warnings`、角色包校验、角色库 QA、UI smoke 和全量测试；
- 若边缘 QA 与真实桌面人工美术 QA 都通过，再单独决定是否把 `xingxi_pixel_pet` 提升为默认包；当前保持 `original_oc` 默认、像素星汐作为可选候选；
- 伊卡洛斯、奶龙继续保持 local UGC 分支，等用户确认要生成私有草稿时再走 hatch-pet 单行流程；
- 继续保持 AI-video、Live2D、精细 VN portrait 为研究线，不回到无边界迭代。

## 9. 本文档的证据命令

本次扫描实际执行过：

```powershell
git status --short --untracked-files=all
git log --oneline --decorate -12
git remote -v
git branch --show-current
rg --files
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\release_readiness_report.py --full-local-snapshot --json artifacts\roadmap-scan-20260611\release-readiness.json --markdown artifacts\roadmap-scan-20260611\release-readiness.md
```
