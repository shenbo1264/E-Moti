# 正式运行资源微修记录：待机抖动与轻触发色

日期：2026-05-13

## 问题来源

人工动态 QA 反馈两个问题：

- 待机时人物有轻微抖动感。
- 轻触动作中的人物发色相比其他动作偏白。

## 根因核对

基于当前正式 `assets/companion/original_oc/spritesheet.png` 生成诊断图与统计：

- 诊断图：`assets/companion/original_oc/preview/qa_diagnostics_2026-05-13/default_touchhead_frames_contact.png`
- 诊断统计：`assets/companion/original_oc/preview/qa_diagnostics_2026-05-13/default_touchhead_stats.json`

核对结果：

- `Default` 行第 1 帧中心点为 `95.5`，其他多为 `96.0`；第 4 帧顶部为 `13`，其他多为 `12`。这些 1px 级差异在循环播放时会形成抖动感。
- `TouchHead` 行发色采样均值约为 `(244, 230, 218)`，比 `Default` 行约 `(243, 227, 214)` 更亮、更偏白。

## 修复动作

本次只修改正式 atlas 的两行动作：

- `Default` 行：统一待机开眼帧为同一稳定基准帧；第 4 帧保留眨眼表情，但只替换脸部眨眼区域，避免整个人物轮廓和落点变化。
- `TouchHead` 行：仅对上半身浅色暖发区域做轻微降亮与暖色回拉，使发色接近 `Default` 行。

未修改其他动作行。

## 产物与备份

- 微修候选：`assets/companion/original_oc/art_runs/2026-05-11-base-character/motion_trials/atlas_candidates/v01/candidate_spritesheet_v01_runtime_fix_2026-05-13.png`
- 微修预览：`assets/companion/original_oc/art_runs/2026-05-11-base-character/motion_trials/atlas_candidates/v01/candidate_spritesheet_v01_runtime_fix_default_touchhead_preview_2026-05-13.png`
- 覆盖前备份：`assets/companion/original_oc/art_runs/2026-05-11-base-character/motion_trials/atlas_candidates/v01/runtime_spritesheet_backup_before_idle_touch_fix_2026-05-13.png`

hash 记录：

- 覆盖前正式资源 SHA-256：`E05AABC6449FD36D41239E16AB11E10DE202E283859271E6DC86ED0F0D317517`
- 微修候选 SHA-256：`E14EA2FEB039C419E2AF1B7C968FA35D0A79FFC14A62DB658D7BF9A54D61C638`
- 覆盖后正式 `spritesheet.png` SHA-256：`E14EA2FEB039C419E2AF1B7C968FA35D0A79FFC14A62DB658D7BF9A54D61C638`

## 修复后验证

- `python tools/art/validate_companion_atlas.py --atlas assets/companion/original_oc/spritesheet.png --manifest assets/companion/original_oc/motion_manifest.json`：通过，输出 `OK atlas 1536x1872 RGBA`
- `python tools/art/build_companion_preview.py --atlas assets/companion/original_oc/spritesheet.png --manifest assets/companion/original_oc/motion_manifest.json --output assets/companion/original_oc/preview`：通过，正式 preview 已重建
- `pytest`：通过，`41 passed`
- PySide visible runtime smoke：通过，Qt 平台为 `windows`，加载路径为 `assets/companion/original_oc/spritesheet.png`
- 微修后窗口截图：`assets/companion/original_oc/preview/pyside_visible_runtime_smoke_window_idle_touch_fix_2026-05-13.png`

## 后续人工 QA 要点

- 请以重新启动后的正式窗口为准检查待机循环，旧窗口不会自动重载已替换的图片。
- 重点确认 `Default` 待机是否不再抖动，同时眨眼是否仍自然。
- 重点确认 `TouchHead` 发色是否已经接近其他动作，且没有把脸部肤色压暗到违和。
