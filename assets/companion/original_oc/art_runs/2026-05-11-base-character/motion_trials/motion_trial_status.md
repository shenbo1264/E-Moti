# 三行动画试生产状态

## 当前状态

已基于唯一视觉锚点 `lively_bond_companion_v01` 生成三条动作 strip：

- `idle`：6 帧。
- `waving`：4 帧。
- `review`：6 帧。

本阶段没有生成完整 9 行 atlas，也没有接入运行时资源包。

## 生成方式

- 使用内置 `image_gen` 工具生成 raw strip。
- 使用纯 `#00ff00` chroma-key 背景。
- 使用本地 chroma-key helper 去除背景，生成透明 alpha strip。
- 使用 ImageMagick 按目标帧数等分切出 `192x208` review 帧。

## 输出文件

### idle

- raw：`idle/raw/idle_strip_v01.png`
- alpha：`idle/alpha/idle_strip_v01_alpha.png`
- review：`idle/review/idle_frame_01_192x208.png` 至 `idle_frame_06_192x208.png`
- alpha review：`idle/alpha_review/idle_frame_01_alpha_192x208.png` 至 `idle_frame_06_alpha_192x208.png`

### waving

- raw：`waving/raw/waving_strip_v01.png`
- alpha：`waving/alpha/waving_strip_v01_alpha.png`
- review：`waving/review/waving_frame_01_192x208.png` 至 `waving_frame_04_192x208.png`
- alpha review：`waving/alpha_review/waving_frame_01_alpha_192x208.png` 至 `waving_frame_04_alpha_192x208.png`

### review

- raw：`review/raw/review_strip_v01.png`
- alpha：`review/alpha/review_strip_v01_alpha.png`
- review：`review/review/review_frame_01_192x208.png` 至 `review_frame_06_192x208.png`
- alpha review：`review/alpha_review/review_frame_01_alpha_192x208.png` 至 `review_frame_06_alpha_192x208.png`

总览图：

- `motion_trial_contact_sheet.png`
- `motion_trial_alpha_contact_sheet.png`

## 第一轮视觉复核

### 通过项

- 三行动作均保持单角色，没有文字、logo、网格、地面阴影、场景或多角色。
- 角色没有回退成学习工具人、课程助手或任务监督者。
- `idle` 能表达稳定待机、轻微眨眼。
- `waving` 能表达触摸回应和打招呼，互动感较强。
- `review` 使用贴近身体的小型无字道具，没有学习桌、书本堆或任务清单。
- 三行动作在 `192x208` 下可读。
- 透明化后均为带 alpha 的 PNG。

### 风险项

- raw strip 不是最终 atlas 几何规格，只能作为视觉试生产，不应直接合入运行时。
- 自动等分切帧仅用于 review；正式切帧仍需按最终生成 strip 的实际几何重新校准锚点。
- `review` 动作表情偏弱，后续若作为正式动作，可增强轻微点头或思考姿态，但不能加入文字和任务监督元素。
- 后续若继续生成完整 atlas，需要继续锁定星形发夹、单侧耳机、蓝白外套和胸前吊坠，防止跨行动画漂移。

## 结论

三行动画试生产可以作为继续制作完整资源包的参考样本，但尚未达到可直接接入 demo 的最终 spritesheet 标准。

下一步建议：

1. 先人工确认三行动作是否都接受。
2. 若接受，再基于该角色继续生成完整 9 行 atlas 或先补 `jumping`、`waiting`、`failed` 三行。
3. 正式接入前必须重新做几何 QA、透明边缘 QA、contact sheet/GIF 预览和 PySide6 smoke test。
