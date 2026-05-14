# running-right 动作试生产复核记录

日期：2026-05-13

## 目标

在 `idle`、`waving`、`review`、`jumping`、`waiting`、`failed`、`running` 已有候选样本后，继续逐行推进 `running-right`。

目标语义：

- 明确读成向右移动或跟随
- 保住同一角色识别点
- 不能退化成正面原地活跃 `running`
- 不能丢掉发夹、耳机、外套、吊坠这些稳定识别点

帧数目标：`8`

## 本次生成结果

### v01：通过当前阶段 QA

文件：

- raw：`raw/running-right_strip_v01.png`
- alpha：`alpha/running-right_strip_v01_alpha.png`
- review：`review/running-right_frame_01_192x208.png` 至 `running-right_frame_08_192x208.png`
- alpha review：`alpha_review/running-right_frame_01_alpha_192x208.png` 至 `running-right_frame_08_alpha_192x208.png`
- alpha contact sheet：`running-right_alpha_contact_sheet_v01.png`

## 实际验证

已核对：

- `running-right_strip_v01.png` 尺寸：`2172x724`
- `running-right_strip_v01_alpha.png` 尺寸：`2172x724`
- `alpha_review/` 共 `8` 帧，数量符合目标
- `running-right_frame_01_alpha_192x208.png` 与 `running-right_frame_04_alpha_192x208.png` 已实际检查，尺寸均为 `192x208`

额外处理：

- 初版 review 切帧出现左边缘孤立小碎片。
- 已仅对 `review/alpha_review` 做后处理，移除孤立小连通块，不修改 raw strip 本体。

## 严格 QA 结论

### 1. 是否仍是同一个角色

结论：通过。

观察结果：

- 奶白/浅金短发、头顶小翘发、右侧星形发夹、单侧耳机均保留。
- 蓝白短外套、暗色短裤、暖黄色吊坠与锚点一致。
- 没有眼睛改色、服装漂移或偶像化重设计问题。

### 2. 是否能明确读成向右移动

结论：通过。

观察结果：

- 整组动作明显是朝屏幕右侧前进的侧向跑动，不会被读成原地活跃跑。
- 与 `running` 的差异已经成立：`running` 是正面原地动态，这组是明确侧向移动。
- 也没有误读成向左跑动。

### 3. 是否在 192x208 下可读

结论：通过。

观察结果：

- 小尺寸下跑动方向、抬腿节奏和身体前倾都清楚。
- 发夹、耳机、外套、吊坠仍保有识别度。

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

### 5. 是否适合作为 `running-left` 的对照基线

结论：通过。

观察结果：

- 这组动作已经足够稳定，可以作为下一步单独生成 `running-left` 的对照基线。
- 同时也进一步验证了：侧向动作下角色识别点仍能保住。

## 当前判定

`running-right_strip_v01` 通过当前阶段严格 QA，可以作为完整九行动画中的 `running-right` 候选样本继续保留。

注意：

- 它仍是视觉试生产样本，不是最终 atlas。
- 当前 review 切帧只用于视觉审查，不等同于最终运行时几何。
- 正式接入前仍需统一锚点、统一缩放并进入最终 atlas QA。

## 下一步建议

继续最后一行：`running-left`（8 帧）。

关键约束：

- 必须单独生成，不能镜像 `running-right`
- 仍要保住同一角色识别点
- 不能因为方向切换把单侧耳机和星形发夹做成另一个人
