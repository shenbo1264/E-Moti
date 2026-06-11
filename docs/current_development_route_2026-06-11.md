# E-Moti Current Development Route 2026-06-11

本文档基于 2026-06-11 对当前仓库的实测扫描，不继承未验证的历史结论。

## 1. 实测基线

- 工作目录：`D:\学工文档\光核\电子宠物\E-Moti_demo`
- 当前分支：`codex/demo-worktree-cleanup`
- 当前 HEAD：`ac1822f docs: correct art route to pixel pet sequences`
- 当前工作区：`git status --short --untracked-files=all` 输出为空，工作区 clean。
- 远端：
  - `origin` -> `https://github.com/shenbo1264/E-Moti.git`
  - `private-origin` -> `https://github.com/shenbo1264/E-Moti_demo.git`
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
- 分发：通过 QA、provenance、LICENSE、角色包校验后，可以考虑进入 `assets/companion/`。

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
python -m pytest tests\test_art_tools.py tests\test_character_pack.py tests\test_character_pack_validator_tool.py -q
python -m pytest
```

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
python -m pytest tests\test_art_tools.py -q
git status --short --untracked-files=all
```

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
python tools\art\validate_companion_atlas.py --atlas <candidate_spritesheet.png> --manifest <candidate_motion_manifest.json>
python -m pytest tests\test_art_tools.py tests\test_motion.py -q
python -m pytest
```

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

## 8. 推荐立即执行的第一包

建议第一包做 `P0-doc-sync`。

理由：

- 当前代码与测试基线稳定，直接大改运行时代码收益不高；
- 当前最大风险是路线口径不统一，新 agent 容易继续回到 Spirit/VN/AI-video 路线；
- 文档同步可以把后续执行包压到低耦合状态；
- 不碰素材、不碰 manifest、不碰状态机，风险最低。

完成后再进入 `P1-pixel-pack-contract`，把三角色草稿从“图和 prompt”推进到可验证 pack 合同。

## 9. 本文档的证据命令

本次扫描实际执行过：

```powershell
git status --short --untracked-files=all
git log --oneline --decorate -12
git remote -v
git branch --show-current
rg --files -g '!AI不用看.md'
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\release_readiness_report.py --full-local-snapshot --json artifacts\roadmap-scan-20260611\release-readiness.json --markdown artifacts\roadmap-scan-20260611\release-readiness.md
```

