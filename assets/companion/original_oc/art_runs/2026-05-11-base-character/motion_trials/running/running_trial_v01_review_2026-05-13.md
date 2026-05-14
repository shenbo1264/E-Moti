# running 动作试生产复核记录

日期：2026-05-13

## 目标

在 `idle`、`waving`、`review`、`jumping`、`waiting`、`failed` 已有可继续扩展的候选样本后，继续逐行推进 `running`。

目标语义：

- 表达原地活跃移动或被提起时的动态感
- 必须与后续 `running-right`、`running-left` 拉开语义区分
- 不能被读成横向跑步
- 不能退化成普通 `idle` 或 `jumping`

帧数目标：`6`

## 本次生成结果

### v01：通过当前阶段 QA

文件：

- raw：`raw/running_strip_v01.png`
- alpha：`alpha/running_strip_v01_alpha.png`
- review：`review/running_frame_01_192x208.png` 至 `running_frame_06_192x208.png`
- alpha review：`alpha_review/running_frame_01_alpha_192x208.png` 至 `running_frame_06_alpha_192x208.png`
- alpha contact sheet：`running_alpha_contact_sheet_v01.png`

## 实际验证

已核对：

- `running_strip_v01.png` 尺寸：`2105x747`
- `running_strip_v01_alpha.png` 尺寸：`2105x747`
- `alpha_review/` 共 `6` 帧，数量符合目标
- `running_frame_04_alpha_192x208.png` 已实际检查，尺寸为 `192x208`

## 严格 QA 结论

### 1. 是否仍是同一个角色

结论：通过。

观察结果：

- 奶白/浅金短发、头顶小翘发、右侧星形发夹、单侧耳机均保留。
- 蓝白短外套、暗色短裤、暖黄色吊坠与锚点一致。
- 没有服装漂移、眼睛改色或偶像化重设计问题。

### 2. 是否与 `running-right` / `running-left` 保持语义区分

结论：通过。

观察结果：

- 这组动作仍是正面原地活跃动态，不是侧向位移。
- 身体和抬腿节奏能读出“活跃中”或“被提起时轻快挣动”，而不是朝某一侧前进。
- 因此可以作为后续横向跑动动作的独立语义基底保留。

### 3. 是否在 192x208 下可读

结论：通过。

观察结果：

- 小尺寸下抬腿、手部摆动、笑眼和整体弹跳节奏都清楚。
- 星形发夹、耳机、外套和吊坠仍保有识别度。

### 4. 是否存在禁止元素

结论：通过。

未见问题：

- 文字
- 网格
- 场景背景
- 地面阴影
- 多角色
- 速度线
- 箭头
- 漂浮图标
- 舞台偶像元素
- 学习桌、书堆、任务清单

### 5. 是否适合作为后续资源候选样本

结论：通过。

观察结果：

- 适合作为 `Raised` / in-place move / 原地活跃移动 的候选动作。
- 情绪上仍明亮亲近，没有因为动态增强而滑成演出型角色。

## 当前判定

`running_strip_v01` 通过当前阶段严格 QA，可以作为完整九行动画中的 `running` 候选样本继续保留。

注意：

- 它仍是视觉试生产样本，不是最终 atlas。
- 当前 review 切帧只用于视觉审查，不等同于最终运行时几何。
- 正式接入前仍需统一锚点、统一缩放并进入最终 atlas QA。

## 下一步建议

按既定顺序继续下一行：`running-right`（8 帧）。

目标：

- 明确读成向右移动或跟随
- 保住同一角色识别点
- 不丢失发夹、耳机、外套和吊坠
- 为 `running-left` 的单独生成提供对照基线
