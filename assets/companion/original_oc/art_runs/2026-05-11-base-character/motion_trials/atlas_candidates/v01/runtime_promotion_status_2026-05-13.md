# 候选 atlas v01 正式资源位提升记录

日期：2026-05-13

## 当前结论

候选 atlas v01 已提升为正式运行时资源位：

- 候选输入：`assets/companion/original_oc/art_runs/2026-05-11-base-character/motion_trials/atlas_candidates/v01/candidate_spritesheet_v01.png`
- 正式资源：`assets/companion/original_oc/spritesheet.png`
- 正式 manifest：`assets/companion/original_oc/motion_manifest.json`

本次只提升 PNG 到当前运行时实际读取的 `spritesheet.png`。候选目录未删除，候选 WebP 仍保留为候选产物。

## 替换与备份

替换前已备份旧正式资源：

- 备份文件：`assets/companion/original_oc/art_runs/2026-05-11-base-character/motion_trials/atlas_candidates/v01/runtime_spritesheet_backup_before_candidate_v01_2026-05-13.png`
- 备份 SHA-256：`B45AF65D55ACBB0DA4EF66F2FA10030B45B13ED0506D0A0CA36EC936F5B89903`

替换后 hash：

- 候选 PNG SHA-256：`E05AABC6449FD36D41239E16AB11E10DE202E283859271E6DC86ED0F0D317517`
- 正式 `spritesheet.png` SHA-256：`E05AABC6449FD36D41239E16AB11E10DE202E283859271E6DC86ED0F0D317517`

以上 hash 一致，说明正式资源位当前确实使用候选 v01 PNG。

## 真实验证记录

替换前验证：

- `python tools/art/validate_companion_atlas.py --atlas assets/companion/original_oc/art_runs/2026-05-11-base-character/motion_trials/atlas_candidates/v01/candidate_spritesheet_v01.png --manifest assets/companion/original_oc/motion_manifest.json`：通过，输出 `OK atlas 1536x1872 RGBA`
- `python tools/art/validate_companion_atlas.py --atlas assets/companion/original_oc/art_runs/2026-05-11-base-character/motion_trials/atlas_candidates/v01/candidate_spritesheet_v01.webp --manifest assets/companion/original_oc/motion_manifest.json`：通过，输出 `OK atlas 1536x1872 RGBA`
- PySide visible smoke：通过，Qt 平台为 `windows`，通过 monkeypatch 临时指向候选 PNG；14 个运行时 motion 均渲染非空。
- 候选窗口截图：`assets/companion/original_oc/art_runs/2026-05-11-base-character/motion_trials/atlas_candidates/v01/pyside_visible_smoke_window_2026-05-13.png`

替换后验证：

- `python tools/art/validate_companion_atlas.py --atlas assets/companion/original_oc/spritesheet.png --manifest assets/companion/original_oc/motion_manifest.json`：通过，输出 `OK atlas 1536x1872 RGBA`
- `python tools/art/build_companion_preview.py --atlas assets/companion/original_oc/spritesheet.png --manifest assets/companion/original_oc/motion_manifest.json --output assets/companion/original_oc/preview`：通过，已重新生成正式 preview contact sheet 与 motion GIF。
- `pytest`：通过，`41 passed`
- PySide visible runtime smoke：通过，Qt 平台为 `windows`，加载路径为 `assets/companion/original_oc/spritesheet.png`；14 个运行时 motion 均渲染非空。
- 正式运行截图：`assets/companion/original_oc/preview/pyside_visible_runtime_smoke_window_2026-05-13.png`
- 正式运行截图 SHA-256：`AB9D570365A30D8D5E22CCC3557E5659CC1DCAFA20FED46199EB26E8F6351CDA`

## 运行时动作映射

本次 smoke 覆盖的运行时 motion：

- `Default`：row 0，6 帧
- `MoveRight`：row 1，8 帧
- `MoveLeft`：row 2，8 帧
- `TouchHead`：row 3，4 帧
- `Play`：row 4，5 帧
- `SwitchDown`：row 5，8 帧
- `Sleep`：row 6，6 帧
- `Raised`：row 7，6 帧
- `Study`：row 8，6 帧
- `Comfort`：row 6，6 帧
- `Eat`：row 3，4 帧
- `Gift`：row 3，4 帧
- `Shop`：row 4，5 帧
- `Tick`：row 0，6 帧

## 视觉与身份边界

正式运行截图中仍可辨认以下锁定特征：

- 奶白/浅金短发
- 头顶小翘发
- 右侧星形发夹
- 单侧小耳机
- 蓝白短外套
- 胸前暖黄色吊坠
- 明亮亲近的大眼表情
- 2.5 头身 Q 版桌宠比例

角色基础身份仍是原创 OC 桌面电子宠物与伴侣。学习、专注、休息只作为动作状态表达，不作为基础身份。

## 仍需留意的风险

- 本次已完成 PySide visible smoke，但仍属于短时运行验证；长时间循环、真实人工交互节奏和动态体感仍建议继续人工 QA。
- `jumping` 与侧向跑动的节奏在短时 smoke 中未发现空帧或映射错误，但如果后续人工动态 QA 认为跳动过强，可只针对对应行微调。
- UI 文案中仍有“程序化占位 spritesheet”的历史提示，需要后续单独改文案；本次没有改动代码。
