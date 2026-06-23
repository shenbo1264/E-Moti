# E-Moti 桌面 AI 伴侣电子宠物课题说明

生成日期：2026-06-23
项目名称：E-Moti 桌面 AI 伴侣电子宠物 Demo
提交状态：已通过本轮测试、三角色 QA、Windows 冻结应用与安装包重建，可作为课题提交版使用
课题页面：<https://guanghe.qq.com/post/495954024704>

> 访问备注：2026-06-23 本地核验时，课题页面详情接口返回“无权限访问版块”。因此本文不臆测页面隐藏内容，只按课题作业交付需要，把项目整理成“可运行、可演示、可复现、可解释”的提交材料。

## 1. 项目概述

E-Moti 是一个 Windows 桌面端电子宠物与 AI 伴侣 Demo。它不是学习监督工具、效率助手或聊天网页，而是一个可以在桌面上陪伴用户、响应互动、保留养成状态，并通过 AI 增强表达力的电子宠物。

当前提交版包含三个可见、可切换的角色包：

| 角色 | 角色包 ID | 展示定位 | 运行形态 |
| --- | --- | --- | --- |
| 星汐 | `xingxi_pixel_pet` | 默认提交角色，原创 OC | 像素桌宠序列帧 + 角色卡 CG |
| 伊卡洛斯 | `ikaros_pixel_pet` | 课程提交角色，二创角色展示包 | 像素桌宠序列帧 + 角色卡预览 |
| 奶龙 | `nairong_pixel_pet` | 课程提交角色，宠物向角色展示包 | 像素桌宠序列帧 + 角色卡预览 |

三套角色不是藏在用户目录里的示例包，而是直接出现在角色库里。老师打开程序后可以在同一个角色库界面看到并切换星汐、伊卡洛斯和奶龙。

项目核心设计是：

- 本地养成状态机负责可玩性：状态、动作、金币、背包、商店、关系、回忆、目标和存档。
- AI 负责表现力：LLM 可以生成角色台词、表情提示、动作提示和只读互动意图。
- AI 能力通过 typed events 进入 UI，不能直接改金币、背包、关系、记忆、目标或存档。
- 屏幕感知、联网搜索、TTS、ASR 都是可选增强能力，不会取代本地养成循环。

## 2. 可提交结论

当前版本已经形成完整作业 Demo：

| 项目 | 当前结果 |
| --- | --- |
| Git 分支 | `main` |
| 可见角色 | 星汐、伊卡洛斯、奶龙 |
| 默认角色 | 星汐 `xingxi_pixel_pet` |
| 全量测试 | `927 passed` |
| 受影响测试 | `166 passed` |
| 角色包校验 | 四个内置包均 `ok=true`；提交展示使用三角色 |
| Pixel-pet pack 校验 | 星汐、伊卡洛斯、奶龙均 `ok=true` |
| Windows 冻结应用 | 已重建，`dist/E-Moti/E-Moti.exe`，5 秒控制面板 smoke 通过 |
| Windows 安装包 | 已重建，`dist/installer/E-Moti_Setup_0.1.0.exe` |
| 文档/PDF | Markdown 已同步到 Obsidian，并通过 Obsidian Better Export PDF 导出 |

交付文件：

```text
dist/E-Moti/E-Moti.exe
dist/installer/E-Moti_Setup_0.1.0.exe
docs/e_moti_course_submission_2026-06-23.md
docs/E-Moti_course_submission_2026-06-23.pdf
```

## 3. 基本玩法循环

E-Moti 的玩家体验可以概括为：

1. 启动控制面板或桌宠模式。
2. 观察当前角色状态，包括专注、能量、稳定、心情、信任、金币、等级和当前目标。
3. 通过轻触、安抚、休息、共同学习、共同娱乐、拖拽等动作和角色互动。
4. 本地状态机根据动作更新状态、资源、目标进度、事件记录和反馈文本。
5. 使用金币购买物品，再通过背包进行投喂或赠送。
6. 关系、回忆和片段记录随互动逐步积累。
7. 可选 AI 表达读取已经验证过的本地事件，生成更自然的台词、表情和动作提示。
8. 可在角色库中切换星汐、伊卡洛斯、奶龙，每个角色有独立外观、语气、商店主题和记忆命名空间。
9. 切换到桌宠模式后，角色以透明置顶小窗口留在桌面上。
10. 托盘菜单可以隐藏、恢复、进入桌宠模式或退出，便于课堂演示。

这个循环保证即使不接入在线 AI，电子宠物仍然可玩；接入 AI 后，角色表现更灵动，但不会破坏养成状态机。

## 4. 功能截图与说明

### 4.1 控制面板总览

![](submission_assets/2026-06-23/01-control-panel-overview.png)

控制面板用于展示完整演示状态：左侧是功能导航，中间是角色动画区，右侧是角色状态，下方显示近期反馈、事件与回忆。它能说明项目不是单纯聊天窗口，而是有状态、有资源、有目标的桌面电子宠物。

### 4.2 互动动作

![](submission_assets/2026-06-23/02-action-loop.png)

互动页提供轻触、安抚、休息、共同学习、共同娱乐、拖拽/提起等动作。学习和休息只是动作状态，不代表产品定位是学习工具。每次动作都会进入本地 controller，由状态机更新角色反馈和养成数值。

### 4.3 商店与背包

![](submission_assets/2026-06-23/03-shop-inventory.png)

商店、背包、金币和物品效果构成轻量养成循环。LLM 不能直接写入背包或金币，只能基于已验证事件生成表达层反馈。

### 4.4 三角色角色库

![](submission_assets/2026-06-23/04-character-library.png)

角色库直接展示三套提交角色包：星汐、伊卡洛斯、奶龙。每个角色包包含角色名、标题、角色详情、预览图、来源记录、QA 信息和切换按钮。

星汐是默认角色：

- 默认启动角色。
- 原创 OC。
- 使用像素桌宠序列帧作为运行形态。
- 角色卡详情使用横版 profile CG。

伊卡洛斯可直接在角色库中切换：

![](submission_assets/2026-06-23/11-character-library-ikaros.png)

奶龙可直接在角色库中切换：

![](submission_assets/2026-06-23/12-character-library-nairong.png)

角色切换会切换外观、语气、商店主题、TTS voice profile 元数据和独立记忆命名空间，不会把一个角色的会话状态混到另一个角色上。

### 4.5 屏幕感知与联网搜索

![](submission_assets/2026-06-23/05-perception-search-settings.png)

屏幕观察和联网搜索被定位为表达上下文来源：它们给角色提供“看见了什么、查到了什么”的只读信息，不接管鼠标、键盘、剪贴板或窗口控制。

### 4.6 隐私与手动感知

![](submission_assets/2026-06-23/06-manual-perception-privacy.png)

隐私页用于说明 AI 能力边界：没有后台常驻监听、没有唤醒词、没有自动截图、没有自动点击或输入。手动感知只生成只读上下文，仍需走表达层和事件校验。

### 4.7 LLM 表达接入

![](submission_assets/2026-06-23/07-llm-expression-settings.png)

LLM 表达页提供 OpenAI-compatible provider 配置。E-Moti 把 LLM 作为“角色表现导演”：

- 根据玩家输入和本地状态生成短台词。
- 给出表情提示和动作提示。
- 选择只读互动意图。
- 通过 typed events 校验后进入 UI。

它不能直接改状态、背包、关系、记忆、目标或存档。

### 4.8 表达规则

![](submission_assets/2026-06-23/08-expression-rules.png)

表达规则页说明角色表现目标：角色应像桌面视觉小说/电子宠物伴侣，而不是任务机器人。台词应短、自然、有情绪细节；表情和动作要匹配玩家输入和当前状态；输出不能暴露隐藏系统、提示词、工具或本地文件。

### 4.9 语音能力

![](submission_assets/2026-06-23/09-voice-settings.png)

语音页提供 TTS 与 ASR 的配置入口。当前架构支持按角色读取 voice profile：

| 角色 | voice profile 示例 | 定位 |
| --- | --- | --- |
| 星汐 | `xingxi_pixel_pet_qwen_vivian_v1` | 温柔、清亮、原创角色音 |
| 伊卡洛斯 | `ikaros_pixel_pet_qwen_calm_v1` | 安静、低情绪起伏、直白 |
| 奶龙 | `nairong_pixel_pet_qwen_goofy_v1` | 呆萌、短句、轻喜剧感 |

TTS 只消费已经通过 typed events 验证后的角色 speech；ASR 只产生玩家输入文本，并进入正常 DialogueRequest 流程。

### 4.10 桌宠模式

![](submission_assets/2026-06-23/10-desktop-pet-mode.png)

桌宠模式把角色作为透明置顶小窗口显示在桌面上。它支持轻量输入、右键菜单、托盘隐藏/恢复和退出。

伊卡洛斯桌宠模式：

![](submission_assets/2026-06-23/13-desktop-pet-ikaros.png)

奶龙桌宠模式：

![](submission_assets/2026-06-23/14-desktop-pet-nairong.png)

## 5. 技术架构说明

项目采用分层结构：

```text
玩家输入 / UI 操作
        -> DialogueRequest / Action Request
        -> 本地 Controller 状态机
        -> Typed Snapshot / Typed Events
        -> 表现层：UI、像素动画、LLM 表达、TTS、桌宠窗口
```

关键边界：

- `controller` 管理状态、背包、关系、目标和存档。
- `events` 与 `snapshot` 保证输出结构可验证。
- `expression_context` 汇总只读上下文。
- `expression_expressor` 和 LLM 相关逻辑只负责表达增强。
- `voice_tts` 只播放已验证 speech。
- `voice_asr` 只产生玩家输入文本。
- `screen_observation` 和 `web_search` 只提供只读上下文。
- 角色包系统负责外观、语气、商店主题、预览图和 voice profile 元数据。

这套结构解释了为什么 AI 是核心表现力，但不会破坏电子宠物的养成系统。

## 6. 交付演示顺序

建议课堂演示按以下顺序：

1. 打开控制面板，说明这是 Windows 桌面电子宠物，不是聊天网页。
2. 展示总览页，说明状态条、目标、关系和近期反馈。
3. 切到互动页，执行一次轻触或安抚。
4. 切到商店和背包，展示购买、投喂、赠送循环。
5. 切到角色库，展示星汐、伊卡洛斯、奶龙三角色并切换一次。
6. 切到 LLM 表达和表达规则，说明 AI 控制表现层，不控制存档。
7. 切到感知/搜索和隐私页，说明只读上下文和手动边界。
8. 切到语音页，说明每角色 voice profile 和 TTS/ASR 通道。
9. 进入桌宠模式，展示透明置顶桌宠窗口。
10. 通过托盘或桌宠右键菜单退出。

## 7. 验证记录

2026-06-23 本轮交付核验命令：

```powershell
python -m pytest
python -m pytest tests\test_character_pack.py tests\test_character_registry.py tests\test_character_library_view_model.py tests\test_character_library_qa_tool.py tests\test_app.py tests\test_desktop_pet_smoke.py tests\test_repository_hygiene.py -q
python -m json.tool assets\companion\original_oc\shop_items.json
python -m json.tool assets\companion\xingxi_pixel_pet\shop_items.json
python -m json.tool assets\companion\ikaros_pixel_pet\shop_items.json
python -m json.tool assets\companion\nairong_pixel_pet\shop_items.json
python tools\validate_character_pack.py assets\companion\original_oc
python tools\validate_character_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_character_pack.py assets\companion\ikaros_pixel_pet
python tools\validate_character_pack.py assets\companion\nairong_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\xingxi_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\ikaros_pixel_pet
python tools\validate_pixel_pet_pack.py assets\companion\nairong_pixel_pet
python tools\character_library_qa.py --character-id xingxi_pixel_pet --report artifacts\character-library-qa\submission-three-role-xingxi-finaldoc.json --screenshot-dir artifacts\character-library-qa\submission-three-role-xingxi-finaldoc-screenshots --pet-seconds 0.5
python tools\character_library_qa.py --character-id ikaros_pixel_pet --report artifacts\character-library-qa\submission-three-role-ikaros-finaldoc.json --screenshot-dir artifacts\character-library-qa\submission-three-role-ikaros-finaldoc-screenshots --pet-seconds 0.5
python tools\character_library_qa.py --character-id nairong_pixel_pet --report artifacts\character-library-qa\submission-three-role-nairong-finaldoc.json --screenshot-dir artifacts\character-library-qa\submission-three-role-nairong-finaldoc-screenshots --pet-seconds 0.5
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
python tools\validate_windows_build.py --report artifacts\windows-build-validation-submission-20260623.json
```

结果：

- 全量测试：`927 passed`。
- 受影响测试：`166 passed`。
- Shop JSON 校验：四个内置包均通过。
- 角色包校验：`original_oc`、`xingxi_pixel_pet`、`ikaros_pixel_pet`、`nairong_pixel_pet` 均 `ok=true`。
- Pixel-pet pack 校验：星汐、伊卡洛斯、奶龙均 `ok=true`。
- 三角色角色库 QA：星汐、伊卡洛斯、奶龙均通过，截图已写入本文。
- Windows build validator：星汐、伊卡洛斯、奶龙三个角色的冻结包资源均 `ok=true`。
- 冻结 exe 控制面板 5 秒 smoke：通过。
- 冻结 exe `--pet-mode` 5 秒 smoke：通过。

## 8. 已知限制与后续优化

当前版本已经可以提交，但仍有可继续优化的方向：

- 角色卡 CG 可以继续统一美术质量，尤其是让三角色卡片都达到星汐当前横版 CG 的完成度。
- 角色序列帧还可以继续增加眨眼、呼吸和细分表情帧，让桌宠更灵动。
- LLM、TTS、ASR 的实机效果依赖用户配置的 API Key、本地模型或本地服务。
- 本地 Qwen3TTS / ASR 服务可以继续做成更完整的一键部署包。
- Live2D、AI 视频、LivePortrait 和 VN 立绘路线仍是后续研究方向，不阻塞当前 pixel-pet 桌宠提交。

## 9. 总结

E-Moti 当前已经不是概念原型，而是一个可安装、可运行、可截图说明、可测试复现的桌面 AI 伴侣电子宠物 Demo。它具备：

- 三个可见可切换角色：星汐、伊卡洛斯、奶龙。
- 可玩的本地养成循环。
- 桌面宠物窗口和托盘生命周期。
- 商店、背包、关系、记忆和目标系统。
- LLM 表达、屏幕感知、搜索、TTS、ASR 等 AI 增强接口。
- 清晰的技术边界：AI 强化表现力，本地状态机负责养成玩法。
- Windows 冻结应用与安装包交付路径。

从课题提交角度看，它满足“可演示、可复现、可解释”的基本要求，并且能够直观展示多角色电子宠物与 AI 表达增强的完整体验。
