# running-left 动作试生产复核记录

日期：2026-05-13

## 目标

在 `idle`、`waving`、`review`、`jumping`、`waiting`、`failed`、`running`、`running-right` 已有候选样本后，继续完成最后一行 `running-left`。

目标语义：

- 明确读成向左移动或跟随
- 必须单独生成，不能镜像 `running-right`
- 仍然保住同一角色识别点
- 不能因为方向切换把耳机、星形发夹、外套、吊坠做成另一个角色

帧数目标：`8`

## 本次生成结果

### v01：通过当前阶段 QA

文件：

- raw：`raw/running-left_strip_v01.png`
- alpha：`alpha/running-left_strip_v01_alpha.png`
- review：`review/running-left_frame_01_192x208.png` 至 `running-left_frame_08_192x208.png`
- alpha review：`alpha_review/running-left_frame_01_alpha_192x208.png` 至 `running-left_frame_08_alpha_192x208.png`
- alpha contact sheet：`running-left_alpha_contact_sheet_v01.png`

## 实际验证

已核对：

- `running-left_strip_v01.png` 尺寸：`2172x724`
- `running-left_strip_v01_alpha.png` 尺寸：`2172x724`
- `alpha_review/` 共 `8` 帧，数量符合目标
- `running-left_frame_01_alpha_192x208.png` 与 `running-left_frame_04_alpha_192x208.png` 已实际检查，尺寸均为 `192x208`

## 严格 QA 结论

### 1. 是否仍是同一个角色

结论：通过。

观察结果：

- 奶白/浅金短发、头顶小翘发、星形发夹、单侧耳机、蓝白短外套和暖黄色吊坠都仍能识别。
- 没有发生眼睛改色、服装重设计、偶像化或“另一位角色”式漂移。
- 这组动作虽然是左向侧跑，但整体气质和角色轮廓仍与锚点一致。

### 2. 是否能明确读成向左移动

结论：通过。

观察结果：

- 整组动作明确是向屏幕左侧移动，不会误读成原地活跃或向右跑动。
- 与 `running-right` 构成清楚的左右方向对照。
- 与 `running` 的差异也成立：`running` 是正面原地动态，这组是清楚的左向位移。

### 3. 是否在 192x208 下可读

结论：通过。

观察结果：

- 小尺寸下身体前倾、跑动节奏、抬腿方向都清楚。
- 发夹、耳机、外套和吊坠仍保有识别度。

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

### 5. 是否满足“单独生成，不是镜像偷懒”

结论：通过。

观察结果：

- 这组动作不是简单把 `running-right` 左右翻转后直接塞进来；整体仍保持了单独生成的笔触和节奏。
- 虽然方向反转不可避免会带来侧向可见信息变化，但整体没有出现廉价镜像拼贴感。

## 当前判定

`running-left_strip_v01` 通过当前阶段严格 QA，可以作为完整九行动画中的 `running-left` 候选样本继续保留。

注意：

- 它仍是视觉试生产样本，不是最终 atlas。
- 当前 review 切帧只用于视觉审查，不等同于最终运行时几何。
- 正式接入前仍需统一锚点、统一缩放并进入最终 atlas QA。

## 当前阶段总结果

九行动画试生产样本现已全部具备候选版本：

- `idle`
- `waving`
- `review`
- `jumping`
- `waiting`
- `failed`
- `running`
- `running-right`
- `running-left`

这表示“逐行动画生成 -> 透明化 -> 192x208 review -> 人工严格 QA”的第一轮流程已经跑通。

## 下一步建议

下一阶段不应直接宣称正式 atlas 完成，而应进入“九行候选样本汇总复核”。

建议顺序：

1. 汇总九行 alpha contact sheet，做整体验证。
2. 检查九行之间的比例、底部锚点、风格漂移和识别点一致性。
3. 仅在九行整体验证通过后，再讨论合成 `1536x1872` `spritesheet.webp`。
4. 合成后继续做几何 QA、透明边缘 QA、运行时接入检查和 PySide smoke test。
