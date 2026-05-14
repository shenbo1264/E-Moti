# 正式运行资源微修记录：轻触与共同学习发色

日期：2026-05-13

## 问题来源

第二轮人工动态 QA 反馈：

- 待机已经不抖。
- `轻触` 和 `共同学习` 的发色仍然偏白。

## 根因核对

基于微修后的正式 `assets/companion/original_oc/spritesheet.png` 再次生成诊断图与统计：

- 诊断图：`assets/companion/original_oc/preview/qa_diagnostics_2026-05-13/default_touchhead_study_color_contact_before_second_fix.png`
- 诊断统计：`assets/companion/original_oc/preview/qa_diagnostics_2026-05-13/default_touchhead_study_color_stats_before_second_fix.json`

核对结果：

- `Default` 待机行发色采样均值约为 `(243, 227, 214)`，且待机抖动修复保持有效。
- `Study` 行发色采样均值约为 `(244, 229, 218)`，相比待机更亮、更白。
- `TouchHead` 行数值已接近待机，但人工窗口观看仍有白感，因此需要更强的视觉回拉，而不是只依赖均值。

## 修复动作

本次只修改两行动作：

- `TouchHead`：对上半身浅色发丝区域做更明确的暖化和轻微降亮。
- `Study`：对上半身浅色发丝区域做更明确的暖化和轻微降亮，使其接近 `Default` 行。

未修改 `Default` 待机行，也未修改其他动作行。

## 产物与备份

- 颜色微修候选：`assets/companion/original_oc/art_runs/2026-05-11-base-character/motion_trials/atlas_candidates/v01/candidate_spritesheet_v01_runtime_color_fix_2026-05-13.png`
- 颜色微修预览：`assets/companion/original_oc/art_runs/2026-05-11-base-character/motion_trials/atlas_candidates/v01/candidate_spritesheet_v01_runtime_color_fix_preview_2026-05-13.png`
- 覆盖前备份：`assets/companion/original_oc/art_runs/2026-05-11-base-character/motion_trials/atlas_candidates/v01/runtime_spritesheet_backup_before_touch_study_color_fix_2026-05-13.png`

hash 记录：

- 覆盖前正式资源 SHA-256：`E14EA2FEB039C419E2AF1B7C968FA35D0A79FFC14A62DB658D7BF9A54D61C638`
- 颜色微修候选 SHA-256：`F7D54DE26CF4E69F24F6B6B8F5757A5398DB4BADEA80CBB5DA4610B7CEAF4A07`
- 覆盖后正式 `spritesheet.png` SHA-256：`F7D54DE26CF4E69F24F6B6B8F5757A5398DB4BADEA80CBB5DA4610B7CEAF4A07`

## 修复后验证

- `python tools/art/validate_companion_atlas.py --atlas assets/companion/original_oc/spritesheet.png --manifest assets/companion/original_oc/motion_manifest.json`：通过，输出 `OK atlas 1536x1872 RGBA`
- `python tools/art/build_companion_preview.py --atlas assets/companion/original_oc/spritesheet.png --manifest assets/companion/original_oc/motion_manifest.json --output assets/companion/original_oc/preview`：通过，正式 preview 已重建
- `pytest`：通过，`41 passed`
- PySide visible runtime smoke：通过，Qt 平台为 `windows`，加载路径为 `assets/companion/original_oc/spritesheet.png`
- 微修后窗口截图：`assets/companion/original_oc/preview/pyside_visible_runtime_smoke_window_touch_study_color_fix_2026-05-13.png`

## 后续人工 QA 要点

- 请重新启动正式窗口后检查，旧窗口不会自动重载 atlas。
- 重点复看 `轻触` 和 `共同学习` 的发色是否已接近待机。
- 同时确认 `轻触` 的脸部肤色、星形发夹和蓝白外套没有被误压暗。
