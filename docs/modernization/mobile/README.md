# E-Moti 多端 Personal Agent 增量

日期：2026-10-28（America/Los_Angeles）。在上一批记忆/人格提交 `fa19b2c` 上继续，新增手机互通、主动建议、长程监督与平台权限研究。当前仍是桌面项目；本批交付可测试的 Python 基础模块，没有发布手机 App 或远程服务。

2026-10-29范围更正：用户此前macOS指的是iOS手机，鸿蒙指华为手机原生系统。当前开发请从[Claude/Codex交接](../../handoff/20261029/README.md)进入；旧macOS研究保留历史来源，不再构成Mac桌面任务。新增[iOS官方研究](../../handoff/20261029/ios-research.md)。

## 已完成

- 官方 Android/小米、Apple、华为/OpenHarmony 与 Qt 文档核查；ActivityWatch、Mobilerun、Open-AutoGLM、Mobile-Agent、scrcpy、Shizuku、screenpipe 的实际代码/许可证取舍。
- 任务建议与明确采纳、持久发送前记录、未知结果恢复、外部进度/证据、取消回执与过时状态报告。
- 默认关闭的 RAM 观测缓冲区：能力/App/用户/角色范围、会话票据、有效期、重放、撤回与迟到视图检查。
- 新增 **57 项测试**；全量 **1390 passed, 1 failed**。唯一失败在未修改的上一批提交上同环境再次复现。
- 可运行演示 **18/18** 检查通过，手机/执行者明确为模拟输入；真实 Python/SQLite/typed prompt 路径参与运行。

## 阅读顺序

| 文档 | 内容 |
|---|---|
| [architecture.md](architecture.md) | 产品决策、主机与手机分工、可靠性定义、隐私派生链与 M0—M4 开发顺序 |
| [android-research.md](android-research.md) | Android/HyperOS 4 权限、root/ADB/Shizuku、实际开源源码与许可证 |
| [platforms-research.md](platforms-research.md) | 历史macOS资料、华为手机鸿蒙相关证据、Qt材料差异和长程执行参考 |
| [iOS研究与平台更正](../../handoff/20261029/platform-scope.md) | 当前Android/iOS/华为手机实施范围与真实权限条件 |
| [task-reliability.md](task-reliability.md) | 已实现任务 API、状态含义、回执/取消/未知结果语义 |
| [verification.md](verification.md) | 实际命令、结果、已复现 bad case、未验证项 |
| [handoff.md](handoff.md) | 下一位 Coding Agent 的边界、接入点和验收门禁 |
| [android-sources.json](android-sources.json) / [platforms-sources.json](platforms-sources.json) | 官方来源、固定源码提交、读取方式与未验证范围 |

## 直接运行

在已安装项目依赖的 Python 3.11+ 环境：

```bash
python -m pytest tests/test_personal_tasks.py tests/test_device_context.py -q
python tools/run_personal_agent_smoke.py --output personal-agent-smoke.json
```

演示仅使用临时目录，不访问个人存档、不向外发送命令。报告中的 `fixture:` 结果引用是明确的模拟产物，不能用于声称真实模型或真实 Relay 已完成工作。

## 当前尚未完成

Android APK / iOS应用 / 华为手机HarmonyOS HAP、设备配对与认证、远程传输、真实 Relay adapter、持续 runner、推送、采集器、真实模型，以及手机观察衍生聊天历史/语音/离线缓存的全链路撤回。观测模块尚未自动挂入现有桌面 UI；原因与接入门禁见架构文档。历史验证文件保留当时的检查范围，不据其中macOS未验项生成新任务。

本轮不改变默认角色、角色资源、存档格式、插件启动行为或现有桌面输入流程。没有 root、ADB、系统授权、开机启动、端口开放或真实设备配置操作。代码未推送，未开 PR，未发布 Release。
