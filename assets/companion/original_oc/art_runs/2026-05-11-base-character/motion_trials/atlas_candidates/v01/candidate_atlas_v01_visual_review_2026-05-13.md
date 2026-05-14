# 候选 atlas v01 视觉 QA 记录

日期：2026-05-13

## 复核对象

本次复核对象是 atlas 前统一整理后生成的候选版：

- `candidate_spritesheet_v01.png`
- `candidate_spritesheet_v01.webp`
- `preview/contact-sheet.png`
- `preview/gifs/`

本记录只说明候选版视觉 QA，不说明正式运行时接入完成。

## 实际查看结果

已实际打开 `preview/contact-sheet.png` 检查九行总览。

### 通过项

- 九行仍能读成同一个原创 OC，没有变成学习工具人、课程助手、监督者或现有 IP。
- 奶白/浅金短发、头顶小翘发、右侧星形发夹、单侧耳机、蓝白短外套和暖黄色吊坠仍可识别。
- `idle`、`waving`、`review`、`jumping`、`waiting`、`failed`、`running`、`running-right`、`running-left` 的动作语义仍然可区分。
- 统一整理后底部锚点已对齐，跨行视觉重心比原始 review 帧更稳定。
- 未用格保持透明，contact sheet 中未用列没有角色残影。
- 第二次重建后，`running-right` 第 4、5 帧旁边的竖向孤立残片已消失。
- 未见文字、网格、场景背景、地面阴影、多角色、速度线、箭头、舞台偶像元素、书堆、学习桌或任务清单。

### 仍需人工留意的风险

- `jumping` 的第 1 帧天然更矮，这是动作姿态差异，不是几何错误；运行时如果循环节奏显得跳动过强，再只微调该行。
- 侧向跑动行与正面行在脸部角度和服装褶皱上仍有 AI 生成差异；当前可作为候选版保留，但正式接入前最好在 PySide 实机窗口里看一轮动态效果。
- 这版仍是从候选 alpha strip 统一整理得到的候选 atlas，不是人工最终定稿资产。

## 结论

候选 atlas v01 通过本轮视觉 QA，可以作为下一步 PySide smoke test 和运行时接入检查的输入候选。

边界：

- 不能称为正式 atlas。
- 不能声称已经接入运行时。
- 本轮尚未运行 PySide smoke test。
