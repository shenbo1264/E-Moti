# 原创桌宠基准图生图执行方案

## 目标

本运行包用于生成和筛选第一版原创二次元 Q 版桌面电子宠物伴侣基准图。基准图只负责锁定角色身份，不直接进入完整 `8x9` 或 9 行 atlas 生产。

本阶段的基础角色方向：

- 可爱、漂亮、亲近，能提供强情绪价值。
- 像会回应触摸、陪伴、安抚和休息需求的桌面电子宠物。
- 学习、专注、复盘、休息提醒只作为后续状态或动作出现，不作为基础身份。

本阶段成功标准：

- 产出 3 个可比较的原创角色基准方案。
- 每个方案都能在 `192x208` 单格尺寸下保持清晰轮廓。
- 人工选择 1 个方案作为后续逐行动画 strip 的唯一视觉锚点。
- 选择前不生成完整 9 行 atlas，避免角色漂移和返工。

## 输入文件

```text
candidate_manifest.json
prompts/01_sweet_healing_companion.prompt.txt
prompts/02_lively_bond_companion.prompt.txt
prompts/03_quiet_guardian_companion.prompt.txt
review_checklist.md
```

## 候选方向

| 候选 id | 中文方向 | Prompt 文件 |
|---|---|---|
| `sweet_healing_companion` | 甜感治愈型：柔软、可爱漂亮、温暖补能，适合触摸/安慰/休息回应 | `prompts/01_sweet_healing_companion.prompt.txt` |
| `lively_bond_companion` | 灵动陪伴型：活泼、表情丰富、记忆点强，适合触摸/投喂/礼物/玩耍反馈 | `prompts/02_lively_bond_companion.prompt.txt` |
| `quiet_guardian_companion` | 安静守护型：温柔、可靠、有边界感，适合低状态照顾；专注学习只在后续 review 状态表达 | `prompts/03_quiet_guardian_companion.prompt.txt` |

## 执行流程

1. 逐个使用 `prompts/*.prompt.txt` 生成角色基准图。
2. 每个候选至少生成 2 张，最多 4 张；不要混合候选 prompt。
3. 将原始输出保存到本目录下的 `outputs/<candidate-id>/raw/`。
4. 人工删除明显失败图：复杂/不可移除背景、文字、网格、场景、地面阴影、IP 相似、细节过密。
5. 将剩余图缩放预览到 `192x208`，保存到 `outputs/<candidate-id>/review/`。
6. 按 `review_checklist.md` 打分，每个候选只保留 1 张最佳图。
7. 将最终待选图放入 `outputs/shortlist/`，等待人工确认。

## 验收门槛

基准图通过后才能进入下一阶段。下一阶段只允许基于选定基准图生成 `idle`、`waving`、`review` 三个高频动作试运行，仍不直接批量生成完整 atlas。

## 失败处理

- 如果候选明显像现有 IP，直接废弃，不做修图规避。
- 如果角色像学习工具人、课程助手或任务监督者，退回重生。
- 如果角色在小尺寸下不可读，优先减少配件和服装层次，而不是提高分辨率。
- 如果 AI 输出无法稳定保持透明背景，可以先接受纯色可抠背景，但必须在记录中标注，进入 atlas 前仍需透明化 QA。
