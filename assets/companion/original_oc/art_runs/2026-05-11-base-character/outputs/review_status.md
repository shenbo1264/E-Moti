# 基准图筛选记录

## 当前状态

已生成真实候选图片，并完成第一轮 `192x208` 小尺寸 review 预览与人工筛选。

本轮已将候选方向修正为：

- `sweet_healing_companion`：甜感治愈型，强调可爱漂亮、温暖补能、触摸/安慰/休息回应。
- `lively_bond_companion`：灵动陪伴型，强调表情丰富、记忆点强、触摸/投喂/礼物/玩耍反馈。
- `quiet_guardian_companion`：安静守护型，强调温柔可靠、有边界感、低状态照顾；专注学习只作为后续 `review` 状态。

当前产物：

- 每个候选方向已生成 2 张原始基准图，共 6 张。
- 每张原始图已生成 `192x208` review 预览。
- 每个候选方向已 shortlist 1 张最佳图。
- 本阶段仍未生成完整 9 行 atlas。

## 待记录模板

```text
候选 id：
保留文件：
总分：
主要优点：
主要风险：
人工选择结论：通过 / 退回重生 / 废弃
```

## 一票否决复核项

- 是否像 Hatsune Miku、Vocaloid 或其他现有 IP。
- 是否出现文字、logo、水印、网格、场景、地面阴影或复杂背景。
- 是否不是完整单角色，或出现多个角色。
- 是否把基础身份画成学习工具人、课程助手、任务监督者或效率工具。
- 是否缩到 `192x208` 后脸、身体和配件不可读。
- 是否配件超过 2 个核心识别点，导致后续动画难以复现。

## 2026-05-11 本次复核记录

已完成：

- `pytest` 已重新运行，结果为 `41 passed`。
- 当前 HEAD 已核对为 `bae09b4 test: prove motion catalog uses configured spritesheet`。
- 关键文档、三个 prompt、manifest、runbook、checklist、输出目录均已核对存在。
- `candidate_manifest.json` 已通过 `python -m json.tool` 语法校验。
- 旧候选方向、旧问题词条和不支持的动作命名已完成复核；本记录不再逐字列出历史词条，避免搜索复核时被本文件自匹配。
- `generation_runbook.md` 中 6 条候选生图命令已执行 dry-run 校验，均指向 `/v1/images/generations`、`gpt-image-2`、`1024x1024`、`medium`、`png`。
- ImageMagick 已确认可用，后续可按 runbook 生成 `192x208` review 预览。
- 仓库内 atlas 预览与校验工具位于 `tools/art/build_companion_preview.py` 和 `tools/art/validate_companion_atlas.py`，但本阶段尚未生成 atlas，不执行完整 atlas 校验。

当前仍然阻塞真实生图：

- 本会话没有可调用的内置 `image_gen` 工具。
- `OPENAI_API_KEY` 未设置，CLI fallback 只能 dry-run，不能真实生成图片。

结论：

- 本次没有生成任何真实候选图片。
- `outputs/<candidate-id>/raw/` 和 `outputs/<candidate-id>/review/` 仍只包含占位 `.gitkeep`，没有可评分图像。
- 解除阻塞后仍应按既定边界执行：每个候选生成 2 张基准图，共 6 张；先生成 `192x208` review 预览并人工筛选，不直接生成完整 9 行 atlas。

## 2026-05-13 本次复核记录

已完成：

- `pytest` 已重新运行，结果为 `41 passed`。
- 当前 HEAD 已核对为 `bae09b4 test: prove motion catalog uses configured spritesheet`。
- 关键文档、三个 prompt、manifest、runbook、checklist、输出目录均已核对存在。
- `candidate_manifest.json` 已通过 `python -m json.tool` 语法校验。
- 本会话未暴露可调用的内置生图工具。
- CLI fallback 脚本存在：`C:\Users\19970\.codex\skills\.system\imagegen\scripts\image_gen.py`。
- ImageMagick 可用，版本为 `7.1.2-18`，后续可生成 `192x208` review 预览。
- 6 条候选基准图 CLI 命令已重新执行 dry-run 校验，均指向 `/v1/images/generations`、`gpt-image-2`、`1024x1024`、`medium`、`png`，输出路径分别落在三个候选的 `raw/` 目录。

当前仍然阻塞真实生图：

- `OPENAI_API_KEY` 未设置，CLI fallback 只能 dry-run，不能真实调用生图 API。

结论：

- 本次没有生成任何真实候选图片。
- 三个候选的 `raw/`、`review/` 目录和 `shortlist/` 目录仍只有占位文件，没有可评分图像。
- 解除阻塞后仍应按既定边界执行：每个候选生成 2 张基准图，共 6 张；先生成 `192x208` review 预览并人工筛选，不直接生成完整 9 行 atlas。

## 2026-05-13 真实基准图生成与筛选记录

生成方式：

- 使用本会话可调用的内置 `image_gen` 工具生成真实图片。
- 每个候选生成 2 张，共 6 张。
- 为便于后续抠图，生成 prompt 使用纯 `#00ff00` chroma-key 背景约束；本轮筛选只做基准图视觉审核，未进行透明化处理。
- 原始图片保存到各候选 `raw/` 目录，`192x208` 小尺寸预览保存到各候选 `review/` 目录。
- 已生成总览图：`outputs/review_contact_sheet.png`。

### 候选一：sweet_healing_companion

候选 id：`sweet_healing_companion`

生成文件：

- `outputs/sweet_healing_companion/raw/sweet_healing_companion_v01.png`
- `outputs/sweet_healing_companion/raw/sweet_healing_companion_v02.png`

保留文件：

- `outputs/shortlist/sweet_healing_companion_v01.png`
- `outputs/shortlist/sweet_healing_companion_v01_192x208.png`

总分：25 / 30

主要优点：

- 小尺寸下脸、身体比例和胸前配件仍然清楚。
- 甜感、柔软、亲近感成立，适合 `idle`、`waving`、`waiting`、`comfort` 等动作延展。
- 没有学习工具人、课程助手或任务监督者倾向。

主要风险：

- 视觉记忆点偏温和，后续动画需要保留头顶发束、暖色胸前结饰和柔软披肩轮廓。
- 仍需后续 chroma-key 抠图和透明边缘 QA。

人工选择结论：通过，进入 shortlist。

### 候选二：lively_bond_companion

候选 id：`lively_bond_companion`

生成文件：

- `outputs/lively_bond_companion/raw/lively_bond_companion_v01.png`
- `outputs/lively_bond_companion/raw/lively_bond_companion_v02.png`

保留文件：

- `outputs/shortlist/lively_bond_companion_v01.png`
- `outputs/shortlist/lively_bond_companion_v01_192x208.png`

总分：27 / 30

主要优点：

- 表情明亮，星形发夹和单侧耳机形成稳定记忆点。
- 小尺寸下轮廓和动作空间清楚，适合 `waving`、`jumping`、`running`、投喂和礼物反馈。
- 互动感最强，适合 3-5 分钟 demo 的第一眼展示。

主要风险：

- 动态感强，后续动画 prompt 要继续禁止速度线、舞台偶像元素和复杂漂浮特效。
- 配件需要严格锁定在星形发夹和单侧耳机，不再增加装饰。

人工选择结论：通过，进入 shortlist。

### 候选三：quiet_guardian_companion

候选 id：`quiet_guardian_companion`

生成文件：

- `outputs/quiet_guardian_companion/raw/quiet_guardian_companion_v01.png`
- `outputs/quiet_guardian_companion/raw/quiet_guardian_companion_v02.png`

保留文件：

- `outputs/shortlist/quiet_guardian_companion_v01.png`
- `outputs/shortlist/quiet_guardian_companion_v01_192x208.png`

总分：26 / 30

主要优点：

- 安静、温柔、可靠的气质成立，适合 `waiting`、`comfort`、`failed` 和低状态照顾。
- 小尺寸下披肩、胸前坠饰和柔和表情仍然可读。
- 没有计时工具、提醒器或学习监督者倾向。

主要风险：

- 相比灵动方案，演示时的即时反馈感较弱；如果选为主锚点，需要在 `waving` 和 `jumping` 动作中补足情绪亮度。
- 后续动画需要避免把胸前小挂饰误生成复杂钟表或日程工具。

人工选择结论：通过，进入 shortlist。

## 第一轮建议

三张 shortlist 均可继续作为人工决策输入。若优先考虑 demo 记忆点和互动反馈，建议优先选择 `lively_bond_companion_v01` 作为唯一视觉锚点；若优先考虑情绪补给与低状态照顾，可在 `sweet_healing_companion_v01` 和 `quiet_guardian_companion_v01` 之间二选一。

在人工选定唯一视觉锚点前，不生成完整 9 行 atlas。下一步只建议基于选定锚点试做 `idle`、`waving`、`review` 三行动画。

## 2026-05-13 人工最终选择

人工最终选择：`lively_bond_companion_v01`

选择理由：

- 互动感和 demo 记忆点最好。
- 表情明亮，适合快速展示轻触、投喂、礼物、玩耍等反馈。
- `sweet_healing_companion_v01` 保留为温暖治愈方向参考。
- `quiet_guardian_companion_v01` 保留为低状态照顾方向参考。

唯一视觉锚点文件：

- `outputs/selected_anchor/lively_bond_companion_v01_selected_anchor.png`
- `outputs/selected_anchor/lively_bond_companion_v01_selected_anchor_192x208.png`

后续动画禁止变化项：

- 保持奶白/浅金短发、头顶小翘发和整体 2.5 头身比例。
- 保持右侧星形发夹、单侧小耳机、蓝白短外套和胸前暖黄色吊坠。
- 保持明亮亲近的大眼表情和小身体、大表情的桌宠比例。
- 不新增漂浮复杂配件、速度线、舞台偶像元素、麦克风、学习桌、书本堆、任务清单或监督工具。
- 不改成双马尾、青绿色长发、Vocaloid 服装结构或任何现有 IP 可识别轮廓。
- 学习/专注只允许在后续 `review` 动作状态中表达，不写回基础身份。

下一步边界：

- 只基于该唯一锚点试做 `idle`、`waving`、`review` 三行动画。
- 三行动画通过视觉 QA 后，再决定是否扩展完整 9 行 atlas。
