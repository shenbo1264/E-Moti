# 角色基准图生成与筛选执行方案

日期：2026-05-11

## 当前结论

下一步不直接生成完整 9 行 atlas。先生成 3 个原创二次元 Q 版桌面电子宠物伴侣基准方案，让人工选择唯一视觉锚点，再进入 `idle`、`waving`、`review` 三行动画试生产。

本轮方向已修正：基础角色的身份不是“桌面学习搭子”，而是可爱、漂亮、亲近、能提供强情绪价值的桌面电子宠物与陪伴者。学习、专注、休息只作为后续动作状态或场景反馈出现，例如 `review` 状态、低状态安抚、触摸回应，不应写成基础身份。

先做基准图的原因是：完整 atlas 的最大风险不是几何切图，而是角色在不同行之间漂移。基准图先行可以先锁定发型、服装、配色、配件和小尺寸可读性。

## 产物位置

本次可执行生图运行包位于：

```text
assets/companion/original_oc/art_runs/2026-05-11-base-character/
```

核心文件：

```text
candidate_manifest.json
README.md
review_checklist.md
generation_runbook.md
outputs/review_status.md
prompts/01_sweet_healing_companion.prompt.txt
prompts/02_lively_bond_companion.prompt.txt
prompts/03_quiet_guardian_companion.prompt.txt
```

## 三个候选角色方案

### 方案 A：甜感治愈型

候选 id：`sweet_healing_companion`

Prompt 文件：

```text
assets/companion/original_oc/art_runs/2026-05-11-base-character/prompts/01_sweet_healing_companion.prompt.txt
```

方向：视觉柔软、甜美、可爱漂亮，像会回应玩家触摸、安慰和休息需求的桌面电子宠物。重点是温暖补能、贴近、被陪伴感，而不是学习任务。

优点：最适合作为默认 `idle` 与触摸安抚反馈；小尺寸下可以靠圆润轮廓、暖色点缀和亲近表情建立第一眼好感。

风险：如果糖果感或光效过重，会变成普通萌系贴纸；需要严格控制配件数量和背景干净度。

### 方案 B：灵动陪伴型

候选 id：`lively_bond_companion`

Prompt 文件：

```text
assets/companion/original_oc/art_runs/2026-05-11-base-character/prompts/02_lively_bond_companion.prompt.txt
```

方向： lively、表情丰富、记忆点强，适合触摸、投喂、礼物、玩耍和短时互动反馈。角色应像会主动靠近玩家的小伙伴，而不是功能型工具。

优点：适合 3-5 分钟 demo 展示，能快速表现轻触、赠礼、挥手、跳跃等情绪反馈，角色更容易被记住。

风险：动态感过强时容易带出速度线、漂浮特效或舞台偶像感；需要保留单角色、低细节、高可读的桌宠轮廓。

### 方案 C：安静守护型

候选 id：`quiet_guardian_companion`

Prompt 文件：

```text
assets/companion/original_oc/art_runs/2026-05-11-base-character/prompts/03_quiet_guardian_companion.prompt.txt
```

方向：安静、温柔、可靠，有边界感，能表达低状态照顾和不打扰的陪伴。专注/学习可在后续 `review` 状态中表达，不写成基础身份。

优点：最适合做低状态关怀、休息提醒、等待、失败安抚等状态；角色气质稳定，后续动作可以更克制。

风险：如果过度强调时钟、便签或工具属性，会变成学习助手或提醒器；需要把“守护感”落在表情、姿态和亲近感上。

## 推荐生成流程

1. 每个候选 prompt 生成 2-4 张基准图。
2. 原始输出放入：

```text
assets/companion/original_oc/art_runs/2026-05-11-base-character/outputs/<candidate-id>/raw/
```

3. 删除一票否决图：IP 相似、非单角色、文字、logo、水印、网格、场景、地面阴影、复杂背景、细节过密。
4. 将保留图缩放到 `192x208` 做小尺寸检查，放入：

```text
assets/companion/original_oc/art_runs/2026-05-11-base-character/outputs/<candidate-id>/review/
```

5. 按 `review_checklist.md` 评分，每个候选只保留 1 张。
6. 最终候选放入：

```text
assets/companion/original_oc/art_runs/2026-05-11-base-character/outputs/shortlist/
```

## 验收标准

一票否决：

- 像 Hatsune Miku、Vocaloid 或其他现有 IP。
- 有文字、logo、水印、网格、场景或地面阴影。
- 不是完整单角色。
- 缩到 `192x208` 后表情、身体和配件不可读。
- 配件超过 2 个核心识别点，后续动画难以复现。
- 基础身份被画成学习工具人、课程助手或任务监督者，而不是电子宠物伴侣。

打分项：

| 项目 | 目标 |
|---|---|
| 小尺寸可读性 | `192x208` 下轮廓、脸和配件仍清楚 |
| 原创性 | 与现有 IP 没有明显相似 |
| 动画可拆性 | 能做 idle、waving、review、jumping、failed、running |
| 角色记忆点 | 1-2 个稳定识别特征 |
| 情绪价值 | 可爱、漂亮、亲近，像会回应玩家的桌面电子宠物伴侣 |
| 技术干净度 | 背景可移除，边缘清晰，无漂浮碎片 |

低于 20 分不进入 shortlist。

## 下一步建议

优先执行方案 A、B、C 的基准图生成。人工选定唯一基准图后，只先试做三行动画：

```text
idle
waving
review
```

这三行分别覆盖常驻待机、轻触反馈和后续专注/学习动作状态。三行通过视觉 QA 后，再扩展到完整 9 行 atlas。
