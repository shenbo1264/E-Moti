# 真实屏幕观察、联网搜索、TTS/ASR 接入设计

日期：2026-05-23  
目标交付窗口：2026-05-26 前可演示、可复现、可解释  
状态：待评审

## 背景

E-Moti 当前已经具备桌宠输入、Shinsekai 式 JSON 表达解析、对话历史、LLM 表达设置、模型列表、表达规则预览，以及 TTS/ASR 禁用入口。下一步需要把“真实 TTS/ASR、自动屏幕观察、真实联网搜索”从占位能力推进到可演示能力。

本设计参考两个项目的实现思路，但不复制其角色、素材、文案或 GPL 代码：

- Shinsekai：provider/factory、TTS/ASR handler 分离、Computer Use 权限拆分、工具结果进入 LLM 上下文。
- BANDORI-PET-REV：截图缩放后发给视觉模型、web search 工具、HTTP TTS 服务、播放队列、口型/音量反馈、设置页显式开关。

E-Moti 的边界不同：她是原创 OC 桌面电子宠物 demo，不是通用电脑控制代理。屏幕观察、搜索、语音只增强“表达与陪伴感”，不能接管本地养成状态机。

## 目标

- 让玩家在控制面板中配置并启用真实屏幕观察、真实联网搜索、TTS、ASR。
- 屏幕观察可以把截图缩略图发送给配置的视觉模型，得到短摘要并注入下一次 LLM 表达。
- 搜索可以显式触发，返回标题、摘要、链接，作为只读 `tool_results` 注入表达上下文。
- TTS 可以朗读星汐回复，支持本机快速方案和 HTTP TTS 服务方案。
- ASR 可以通过按钮录音识别，识别文本填入或发送到桌宠输入框。
- 所有能力都有 fallback 和错误原因，不影响离线演示。

## 非目标

- 不做鼠标移动、点击、滚动、键盘输入、剪贴板写入。
- 不做插件下载、模型自动下载、后台安装依赖。
- 不复制 BANDORI-PET-REV 的 GPL 源码、角色参考音频、角色设定、prompt 或素材。
- 不接入 Shinsekai 的完整插件/MCP 主体。
- 不让 LLM、搜索、屏幕观察、TTS、ASR 修改 `CompanionState`、背包、商店、关系、回忆、目标或存档。
- 不把屏幕截图保存到仓库或长期落盘；默认只保留运行时最近摘要。

## 架构原则

新增能力按“provider -> sanitize -> context/UI -> typed events”流动。

```text
UI/Settings
  -> CapabilitySettingsStore
  -> ScreenObservationService / WebSearchService / TTSService / ASRService
  -> sanitized perception_summary / tool_results / recognized_text / audio playback
  -> Controller + typed snapshot/events
```

关键规则：

- 屏幕观察和搜索只进入 `ExpressionContextChain` 输出的 `perception_summary` / `tool_results`。
- ASR 只产生用户输入文本，等价于玩家在输入框打字。
- TTS 只消费星汐已经通过 typed events 验证后的 speech。
- Controller 仍是唯一能改变养成状态的入口。

## 设置模型

新增 `src/guanghe_companion/capability_settings.py` 和 `capability_settings.json`，避免继续把 LLM、感知、搜索、TTS、ASR 塞进 `ExpressionSettings`。

运行时路径：

- `%LOCALAPPDATA%\E-Moti\capability_settings.json`
- 源码测试环境仍可通过 `E_MOTI_USER_DATA_DIR` 覆盖。

建议字段：

```json
{
  "screen_observation": {
    "enabled": false,
    "auto_enabled": false,
    "interval_seconds": 60,
    "max_screenshot_width": 1280,
    "send_screenshot_to_vision": true,
    "vision_provider": "openai_compatible",
    "vision_model": "",
    "vision_base_url": "",
    "vision_api_key": "",
    "timeout_seconds": 30
  },
  "web_search": {
    "enabled": false,
    "engine": "duckduckgo",
    "max_results": 3,
    "timeout_seconds": 10,
    "show_sources": true
  },
  "tts": {
    "enabled": false,
    "provider": "windows_sapi",
    "api_url": "http://127.0.0.1:9880/",
    "language": "zh",
    "voice": "",
    "rate": 0,
    "volume": 1.0,
    "auto_speak": false
  },
  "asr": {
    "enabled": false,
    "provider": "openai_compatible",
    "model": "whisper-1",
    "base_url": "",
    "api_key": "",
    "language": "zh",
    "vosk_model_path": "",
    "auto_send": false,
    "max_record_seconds": 12
  }
}
```

所有字符串做长度限制和控制字符清理；API key 只在本地配置中保存，UI 和日志永不打印明文。

## 屏幕观察设计

模块：`src/guanghe_companion/screen_observation.py`

参考策略：

- BANDORI-PET-REV 的 `computer_tools.py`：截图、最长边缩放、base64 data URL、视觉模型摘要。
- Shinsekai 的 Computer Use 设置思路：权限拆分，截图权限独立于鼠标/键盘权限。

E-Moti 第一版只做观察：

- 手动按钮：立即截图并总结。
- 自动观察：用户显式开启后用 `QTimer` 按间隔触发，默认关闭。
- 截图源：优先使用项目已有依赖 `Pillow.ImageGrab.grab(all_screens=True)`；如果 Windows 多屏/权限表现不稳定，再补 `mss` adapter。
- 图片处理：最长边限制 640-1920，默认 1280；转 PNG data URL；不写入文件。
- 视觉模型：OpenAI-compatible multimodal chat completions。请求只包含观察提示和缩略图。
- 输出：短摘要，最大 240 字符，进入 `perception_summary`。

失败策略：

- 截图失败：状态显示“截图失败：原因”，不改变现有上下文。
- 视觉失败：状态显示“视觉摘要失败”，可退化为“已观察但未生成摘要”。
- auto timer 在窗口关闭时停止。

隐私提示必须在 UI 上可见：

- “启用后会把缩略截图发送给配置的视觉模型。”
- “截图不保存到仓库，不长期落盘。”
- “不会自动点击、输入、操作电脑。”

## 联网搜索设计

模块：`src/guanghe_companion/web_search.py`

参考策略：

- BANDORI-PET-REV 的 `local_tools.py`：显式 web_search、搜索源显示、结果作为工具信息进入回复。
- Shinsekai 的 ToolManager 思路：工具结果有 source/title/summary/timestamp，不直接写业务状态。

第一版做显式搜索，不做 LLM 自主无限调用：

- 控制面板搜索框：输入关键词，点击“搜索并提供给星汐”。
- 桌宠输入支持 `/search 关键词` 快捷触发。
- 结果进入最近一次 `tool_results`，下一次 LLM 表达可读。
- UI 显示最近 3 条来源，包含标题、摘要、URL。

选型：

- 优先使用 `ddgs` 包作为 DuckDuckGo 搜索 adapter。
- 如果依赖缺失，UI 显示安装提示，测试中用 fake adapter。
- 后续可以增加 Bing CN / Google / Baidu HTML adapter，但交付前不把多搜索引擎作为必要条件。

结果限制：

- `max_results` 1-5，默认 3。
- title 80 字符、summary 180 字符、url 240 字符。
- 不把网页全文传给 LLM。

## TTS 设计

模块：`src/guanghe_companion/voice_tts.py`

参考策略：

- BANDORI-PET-REV 的 `tts_manager.py`：TTS request worker、播放队列、停止播放、口型/音量状态、HTTP TTS 服务。
- Shinsekai 的 `tts_manager.py` / `tts_adapter.py`：provider factory，GPT-SoVITS / Genie / IndexTTS / CosyVoice 这类 adapter 概念。

第一版支持两个 provider：

1. `windows_sapi`
   - 目标：保证 Windows 本机快速可演示。
   - 实现：优先 `pyttsx3`；缺失时 UI 显示“pyttsx3 未安装”。
   - 支持 rate、volume、voice。

2. `http_qwen3tts`
   - 目标：兼容 BANDORI-PET-REV 这类本地 HTTP TTS 服务。
   - 默认地址：`http://127.0.0.1:9880/`
   - 请求：POST 文本、语言、可选 voice/reference 字段。
   - 响应：接收音频 bytes，写入 `%LOCALAPPDATA%\E-Moti\cache\tts\` 临时文件或内存播放。
   - 播放：优先 PySide6 QtMultimedia；如不稳定再补 `sounddevice/soundfile`。

UI：

- 语音页从“暂未启用”升级为真实配置页。
- 按钮：测试朗读、停止朗读。
- 开关：自动朗读星汐回复。

TTS 只消费已经通过 `EventValidator` 的星汐 speech；不会影响状态结算。

## ASR 设计

模块：`src/guanghe_companion/voice_asr.py`

参考策略：

- Shinsekai 的 `asr_adapter.py`：ASR provider 归一化、Vosk 默认、Whisper 类 provider 可插拔。
- API 设置页的 provider/model/device/language 思路。

第一版只做按钮触发录音，不做常驻监听：

- 点击“开始录音”，录制到内存或临时 wav。
- 点击“停止并识别”，把识别文本填入桌宠输入框。
- 如果 `auto_send=True`，识别成功后自动提交为 `DialogueRequest`。

Provider：

1. `openai_compatible`
   - 目标：快速接入云端 ASR。
   - endpoint：OpenAI-compatible `/audio/transcriptions`。
   - model 默认 `whisper-1`，base_url/api_key 可配置。

2. `vosk`
   - 目标：离线方案。
   - 需要用户填写本地模型路径。
   - 依赖缺失或模型不存在时只显示错误，不崩溃。

录音依赖：

- 优先 `sounddevice` 写 wav。
- 依赖缺失时 UI 显示“录音依赖未安装”。

ASR 输出只作为玩家输入文本，不绕过 typed events。

## UI 设计

控制面板新增或扩展三个页面：

- `感知与搜索`
  - 屏幕观察开关、自动观察开关、间隔、最长边、视觉模型配置、手动观察按钮、最近摘要。
  - 搜索开关、搜索引擎、搜索框、搜索按钮、最近来源。

- `语音`
  - TTS provider、API URL、语言、voice、rate、volume、自动朗读、测试朗读、停止。
  - ASR provider、model/base_url/api_key、语言、Vosk 模型路径、开始录音、停止识别、自动发送。

- `隐私`
  - 保留并更新屏幕观察风险说明。
  - 明确“不会自动点击/输入/写剪贴板”。

桌宠窗口：

- 输入框旁增加麦克风按钮。
- LLM speech 到达后，如 TTS 自动朗读开启，则进入 TTS 队列。
- 屏幕观察和搜索状态不挤占主要演出窗口，只用短状态提示。

## 测试策略

全部实现遵循 TDD，先写失败测试。

单元测试：

- `tests/test_capability_settings.py`
  - 默认全部关闭。
  - API key 脱敏。
  - 超时、间隔、max width、路径、provider 归一化。
  - BOM JSON 兼容。

- `tests/test_screen_observation.py`
  - fake screenshot -> resize -> data URL。
  - fake vision transport -> sanitized summary。
  - 失败时不生成上下文、不写文件。

- `tests/test_web_search.py`
  - fake search adapter -> sanitized tool_results。
  - 依赖缺失 -> explicit unavailable。
  - 结果数量和字段长度限制。

- `tests/test_voice_tts.py`
  - TTS 队列按顺序消费。
  - 停止播放清空队列。
  - fake HTTP TTS 收到正确 payload。
  - action tags / search source JSON 不进入朗读文本。

- `tests/test_voice_asr.py`
  - fake recorder -> fake transcriber -> 文本。
  - openai-compatible ASR 请求不泄露 key。
  - Vosk 模型缺失返回明确错误。

集成测试：

- `tests/test_expression_context.py`
  - 屏幕摘要和搜索结果进入 `ExpressionRequest`。
  - 工具结果数量限制仍生效。

- `tests/test_controller.py`
  - 搜索、屏幕观察、TTS、ASR 不改变 growth state。

- `tests/test_app.py` 与 `tests/test_desktop_pet_smoke.py`
  - UI 控件存在、默认关闭、启用状态、手动观察、搜索、TTS/ASR 按钮。

打包验证：

- 每个 UI 或依赖包结束后跑 `python -m pytest`。
- 功能包合入后重建 `tools\build_windows_app.ps1`。
- 重建 `tools\build_windows_installer.ps1 -SkipAppBuild`。
- 冻结版 control panel / pet mode smoke。

## 实现包顺序

### 包 1：能力设置与 UI 骨架

新增 `capability_settings.py`、runtime path、设置页控件。所有能力默认关闭。  
不接真实 IO，只保存/加载配置并显示状态。

验收：

- 默认配置安全关闭。
- UI 能保存并重新加载设置。
- 全量测试通过。

### 包 2：屏幕观察视觉摘要

实现手动观察和自动观察 timer。截图缩放后发给配置的视觉模型，摘要进入 `perception_summary`。

验收：

- fake vision 测试通过。
- 实机手动观察能得到摘要或明确错误。
- 截图不落盘。

### 包 3：真实联网搜索

实现显式搜索入口和 `/search` 快捷指令。搜索结果进入 `tool_results` 并在 UI 显示来源。

验收：

- fake search 测试通过。
- 实机搜索能返回来源或明确错误。
- 搜索不修改状态/存档。

### 包 4：TTS

实现 `windows_sapi` 和 HTTP TTS 的服务接口、测试朗读、停止朗读、自动朗读星汐回复。

验收：

- fake TTS 和 UI 测试通过。
- Windows 本机 TTS 或 HTTP TTS 至少一条路径可实际播放。
- 朗读文本来自 typed speech。

### 包 5：ASR

实现按钮录音、识别、填入输入框、可选自动发送。优先 openai-compatible，Vosk 作为离线路径。

验收：

- fake ASR 测试通过。
- 依赖缺失时 UI 明确提示。
- 识别文本走 `DialogueRequest`，不直接改状态。

### 包 6：打包回归

重建冻结版和安装器，跑 smoke，更新交付说明。

验收：

- `python -m pytest` 通过。
- `dist\E-Moti\E-Moti.exe` 存在且 smoke 通过。
- `dist\installer\E-Moti_Setup_0.1.0.exe` 存在且时间戳晚于功能提交。

## 风险与缓解

- 依赖安装风险：所有 provider 都要能在依赖缺失时禁用并显示原因；不能阻塞应用启动。
- 视觉模型不支持图片：UI 要区分“截图成功”和“视觉模型不支持/请求失败”。
- 搜索源不稳定：第一版以显式搜索为主；失败时不声称已联网。
- TTS 音频格式不一致：HTTP provider 先支持常见 wav/mp3/ogg 文件播放，流式协议放后续增强。
- 麦克风权限/设备缺失：ASR 按钮显示错误，不进入崩溃状态。
- 隐私风险：屏幕观察默认关闭；自动观察必须用户显式开启；截图不写仓库，不长期保存。
- IP/许可证风险：参考 BANDORI-PET-REV 只借鉴策略，不复制 GPL 源码和 IP 资源。

## 交付口径

可以对外说明：

- 星汐可以在用户授权下观察屏幕缩略图，并用视觉模型生成只读摘要。
- 星汐可以显式联网搜索，并把来源作为表达上下文。
- 星汐可以朗读回复，也可以把玩家语音转为输入文本。
- 这些能力都可关闭，并且不会接管养成状态机。

不能对外说明：

- 不能说她会自动操作电脑。
- 不能说她会在后台长期监控屏幕。
- 不能说她拥有插件下载或完整 Shinsekai/MCP 能力。
- 不能说 `轻触 / 共同学习 发色偏白` 已解决。
