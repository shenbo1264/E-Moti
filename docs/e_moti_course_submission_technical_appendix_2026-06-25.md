# E-Moti 课程提交技术附件

本文是主交付文档的技术附件，用于保存测试证据、配置边界和实现说明。主文档面向导师快速理解产品体验；本附件面向需要复核实现细节的人。

## 1. 验证记录

以下记录均来自 2026-06-25 当前仓库与课程提交包。

| 项目 | 证据路径 |
| --- | --- |
| 课程提交包构建 | `artifacts/final-package-qa/course-submission-package-copy-20260625.json` |
| 导师预览 smoke | `artifacts/final-package-qa/mentor-preview-smoke-course-copy-20260625.json` |
| DeepSeek LLM live smoke | `artifacts/final-package-qa/course-deepseek-smoke-copy-20260625.json` |
| MiMo 屏幕观察 live smoke | `artifacts/final-package-qa/course-mimo-screen-observation-copy-20260625.json` |
| MiMo 主动话题 runtime | `artifacts/final-package-qa/course-mimo-topic-runtime-copy-20260625.json` |
| 三角色模拟游玩 | `artifacts/final-package-qa/simulated-playthrough-20260625.json` |
| 语音服务预检 | `artifacts/final-package-qa/voice-service-preflight-20260625.json` |
| 截图 QA | `artifacts/final-package-qa/submission-screenshot-qa-20260625.json` |
| Windows 构建验证 | `artifacts/windows-build-validation-copy-20260625.json` |

关键结论：

- 全量自动化测试结果为 `1007 passed`。
- Windows app、installer、课程 zip 和导师预览 smoke 均已完成验证。
- DeepSeek live smoke 通过，LLM 输出没有越权修改养成状态。
- MiMo 屏幕观察与主动话题链路通过，感知结果只作为只读表达上下文。
- 星汐、伊卡洛斯、奶龙三角色均完成模拟游玩验证。

## 2. AI 运行边界

E-Moti 的 AI 能力分为表达增强层和本地规则层。

表达增强层可以：

- 生成角色台词；
- 建议表情、动作和语气；
- 读取授权后的只读上下文，如屏幕摘要、搜索结果、近期对话；
- 触发 TTS 读取已验证后的角色 speech。

表达增强层不可以：

- 直接修改状态、金币、背包、关系、目标或存档；
- 绕过 `DialogueRequest`；
- 让 ASR 文本直接改存档；
- 让屏幕观察或搜索结果直接进入养成结算。

养成状态、资源、记忆命名空间和角色切换仍由本地规则与 typed events 管理。

## 3. 角色包结构

当前角色库面向三类信息：

- 运行时桌宠资源：像素序列帧、动作映射、桌宠渲染参数；
- 角色表现资源：角色设定、对话风格、表达规则、voice profile；
- 体验与证明信息：角色详情图、商店主题、独立记忆命名空间、provenance 与 QA 记录。

推荐角色包结构：

```text
character.json
dialogue_style.json
motion_manifest.json
spritesheet.png
preview/contact-sheet.png
provenance.md
qa_report.json
```

这套结构可以兼容 hatch-pet 式像素宠生成工作流，但 E-Moti 会进一步把资产接入角色库、桌宠窗口、对话风格、语音 profile、商店主题和记忆命名空间。

## 4. 感知、搜索与主动陪伴

屏幕观察和搜索功能默认遵守授权边界：

- 屏幕观察只生成摘要，不进行键鼠、剪贴板或窗口控制；
- 搜索结果只作为对话上下文，不修改状态机；
- 主动陪伴受冷却、安静时段和用户设置约束；
- 相关内容进入表达层前会经过本地结构化处理。

这条设计使 AI 可以主动找话题，但不会变成不可控后台代理。

## 5. 语音方案

课程版本使用统一的 voice profile 入口，角色切换时同步切换语音方向。当前联调方向如下：

| 角色 | 语音方向 |
| --- | --- |
| 星汐 | 原创清澈、温柔的 Qwen3TTS 方向 |
| 伊卡洛斯 | GPT-SoVITS 本地训练方向，支持中文显示与日语合成路线 |
| 奶龙 | 偏呆萌、短句反馈的 Qwen3TTS 方向 |

ASR 使用 SenseVoice OpenAI-compatible 服务方向，识别出的玩家文本会进入正常 `DialogueRequest` 流程，再由角色系统回应。

语音服务属于体验增强项。课程包优先保证程序打开、核心玩法、三角色和 AI 对话/感知可演示；完整本地语音服务按演示环境启动。

## 6. 美术路线取舍

已调研和尝试的路线包括：

- Live2D：表现上限高，但课程周期内需要正式分层、绑定、动作制作和模型授权，不适合作为提交主线。
- AI 视频 / LivePortrait：适合探索呼吸、眨眼和头发细动，但目前帧间一致性、边界稳定性和修复成本仍偏高。
- 精细 GalGame 立绘：适合角色详情页和宣传图，但不适合作为小尺寸桌宠主渲染。
- 像素宠物序列帧：最适合课程版桌宠窗口，便于稳定切换角色、映射动作并做自动化 QA。

因此提交版采用“角色卡 CG + 像素桌宠序列帧”的混合路线。

## 7. 已知限制

- 语音服务的完整体验依赖本机演示环境中的服务启动状态。
- Live2D 与 AI 视频路线保留为后续研究方向，不作为本次提交主线。
- 主动陪伴策略已经具备链路，但更细腻的打扰频率、时机判断和话题质量仍是后续优化重点。
- 角色创作工作坊已经有结构基础，但尚未做成面向普通玩家的一键生成界面。

## 8. 推荐演示顺序

1. 打开 `E-Moti.exe`。
2. 展示星汐总览和当前状态。
3. 进行一次互动，展示即时反馈。
4. 打开商店和背包，说明资源循环。
5. 切换星汐、伊卡洛斯、奶龙三角色。
6. 进入桌宠模式，展示真实桌面常驻效果。
7. 打开 AI 表达页，说明 LLM 如何生成台词、表情和动作建议。
8. 打开感知与搜索页，说明授权后的屏幕观察、搜索和主动话题。
9. 如演示环境已启动语音服务，再展示 TTS/ASR。
