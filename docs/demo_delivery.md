# E-Moti 桌面伴侣 Demo 交付说明

## 当前定位

E-Moti 是“可养成的 AI 桌面伴侣电子宠物”demo。主角色是原创 OC 桌面电子宠物与伴侣，不是学习工具、课程监督者，也不是“光核”吉祥物。学习、休息、安抚、娱乐等只作为她会进入的动作状态。

当前主角色名为“星汐”。她通过本地状态机、动作动画、反馈气泡、背包和商店闭环回应玩家操作。

## 启动方式

默认控制面板模式：

```powershell
python -m guanghe_companion.app
```

桌宠演示模式：

```powershell
python -m guanghe_companion.app --desktop-mode
```

`--pet-mode` 是同义别名。桌宠演示模式会使用置顶、无边框、透明背景窗口，并隐藏状态、反馈、按钮、商店和背包面板，只保留角色动画区，适合演示“桌面宠物”感。

已验证 Windows 打包产物：

- `dist\E-Moti\E-Moti.exe`
- `dist\installer\E-Moti_Setup_0.1.0.exe`

## 3-5 分钟演示流程

1. 展示首屏：角色动画、状态面板、反馈气泡、主按钮、商店和背包。
2. 点击角色动画区或“轻触”：触发 `TouchHead`，展示状态变化和角色反馈。
3. 点击“共同学习”：展示 focus/charge 消耗、trust/exp/coins 增长，并切换到 `Study`。
4. 用金币购买“热牛奶”：展示商店购买和背包数量变化。
5. 在背包中使用/投喂“热牛奶”：触发 `Eat` 映射动作，展示 charge/mood 恢复。
6. 演示拖拽角色动画区：释放后触发 `Raised`，说明已接入桌宠式直接交互。
7. 在“表达设置”中说明 LLM 只生成结构化表达事件；关闭或配置错误时会走本地 fallback。
8. 在“超能力/语音”区域演示可选增强：
   - 手动屏幕观察：只读截图摘要，注入表达上下文。
   - Web 搜索：只读搜索结果，注入表达上下文。
   - TTS：测试朗读、停止朗读，或自动朗读已通过 typed event 校验的星汐回复。
   - ASR：开始录音、停止并识别，把识别文本填入输入框；开启自动发送时通过 `DialogueRequest(source="asr")` 进入对话。
9. 切换 `--desktop-mode`：展示精简桌宠窗口，说明控制面板模式和桌宠展示模式可以并存。

## 当前已具备

- 5 个状态数值：focus、charge、stability、mood、trust。
- 4 个高层模式：Glow、Calm、Frayed、Overload。
- 6 个主按钮动作：轻触、安抚、休息、共同学习、共同娱乐、拖拽/提起。
- 15 秒 tick 和“立即结算 15 秒”。
- 轻量商店与背包，商品配置来自角色包 `shop_items.json`。
- 原创 OC 角色包与正式运行时 `spritesheet.png`。
- Shinsekai 风格 JSON 事件校验与 fallback。
- `ShinsekaiAIExpressor` 雏形：可构造状态 prompt，可接入外部 LLM client；AI 输出只进入表达事件校验，不允许修改本地状态。
- 能力设置持久化：屏幕观察、Web 搜索、TTS、ASR 均有独立开关和配置，不与养成状态混写。
- 屏幕观察：手动触发或定时触发，使用视觉模型生成只读表达上下文。
- Web 搜索：显式触发搜索，结果只作为表达上下文，不写入状态机。
- TTS：支持 `http_qwen3tts` 与 `windows_sapi`，`http_qwen3tts` 可切换 `qwen3tts_1.6b` 标准版和 `qwen3tts_0.7b` 低参数版。
- ASR：支持 OpenAI-compatible `/audio/transcriptions` 与 Vosk 配置路径；默认录音链路使用 PySide6 QtMultimedia，识别结果只作为玩家输入文本。

## AI 使用边界

运行时规则由本地状态机决定。AI 只能读取状态快照并生成 JSON 表达事件，不能直接修改：

- 状态数值
- 动作结果
- 目标进度
- 解锁内容
- 背包与商店
- 存档

当 LLM 不可用、超时、输出不是合法 JSON，或字段不符合限制时，系统会回退到本地 fallback 事件，保证 demo 离线可演示。

屏幕观察和 Web 搜索结果只能作为只读 expression context 注入。TTS 只能消费已经通过 typed event 校验后的星汐 speech。ASR 只能产出玩家输入文本；自动发送也必须走 `DialogueRequest`，不能绕过控制器状态机。

## 开源吸纳边界

- Shinsekai：参考 AI 角色演出、结构化事件、LLM/TTS/ASR 适配思想和 PySide 桌面 UI 方向。
- VPet：参考桌宠玩法骨架、状态数值、交互动作、动画组织和资源/MOD 思想。
- awesome-codex-pet：参考固定 spritesheet、角色包边界、预览生成和资源校验流程。
- HELPMEEADICE/BANDORI-PET-REV：GPL-3.0 项目，只能参考千问语音方案的产品策略和架构边界，不能复制源码、prompt、素材或角色设定。

本 demo 不直接复制 VPet、Shinsekai、Codex pet、BANDORI-PET-REV、Vocaloid/Miku 或其他现有 IP 的角色设定、造型、动画素材与可识别视觉组合。主角色资产按原创 OC 路线推进。

## 已知风险

- `轻触` 和 `共同学习` 的发色偏白问题仍搁置，不能宣称已完全解决。
- 当前 `Eat`、`Gift`、`Comfort`、`Sleep` 仍主要复用基础 atlas 行，专属增强动画尚未制作。
- 当前 AI 表达层可接入 OpenAI-compatible provider，但演示机仍需要实际 API Key/Base URL 才能展示真实云端表达。
- `http_qwen3tts` 需要本机或局域网 TTS 服务；若服务不可用，应切换 `windows_sapi` 或保持 TTS 关闭。
- ASR 的 OpenAI-compatible 路径需要真实 ASR API Key/Base URL；Vosk 路径需要用户自行提供本地模型目录。
- 麦克风、扬声器、系统权限和云端服务连通性需要在演示机上做人工 QA。
- 桌宠演示模式已具备窗口形态和直接交互，但还没有完整桌面游走、吸附边缘或长期驻留行为。

## 2026-05-23 验证记录

- `python -m pytest`：383 passed。
- `python -m json.tool assets\companion\original_oc\shop_items.json`：通过。
- `powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1`：通过。
- `powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild`：通过。
