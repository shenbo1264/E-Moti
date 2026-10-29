# 多端与长程能力：Coding Agent 交接

日期：2026-10-28（America/Los_Angeles）。本批从本地 `fa19b2c` 开始，开发分支 `codex/multidevice-personal-agent-20261028`。最终提交与补丁基线见交付包 `DELIVERY.json`；生产源码指纹及实际测试记录见 [verification.md](verification.md)。

2026-10-29接手更正：先读[Claude/Codex完整交接](../../handoff/20261029/README.md)。用户指定Claude负责产品/前端，Codex负责后端；手机范围为Android/HyperOS、iOS、华为手机原生鸿蒙，旧macOS任务取消。下表保留内核实现说明，不把历史平台验收范围当成新任务。

## 开始前

重新检查远程 main、分支和 open PR。遵守根 `AGENTS.md`；保留第一批 [记忆不变量](../handoff.md)。当前远程尚未包含这两批本地增量，不能把原 main 当成已升级代码。没有得到明确指令前不要推送、开 PR、改可见性或发布。

用户的新优先方向是 Android/HyperOS 4 手机聊天和远程工作入口，随后逐步增加可选择的活动与屏幕观察。当前没有具体手机型号、完整系统 build、地区包或真机连接；这不阻止先做协议与客户端，但阻止宣称“已兼容用户手机”。

## 本批代码在哪里

| 文件 | 真实职责 | 不承担的职责 |
|---|---|---|
| `src/guanghe_companion/personal_tasks.py` | 单机 SQLite 建议/采纳/发送权/回执/阶段状态与取消记录 | 执行 shell、Relay 调度、登录鉴权、后台 daemon、推送、独立验收 |
| `src/guanghe_companion/device_context.py` | 短期观察门控与快照撤回校验 | 原生采集、敏感内容检测、网络身份认证、模型注入防护、历史/TTS完整撤回 |
| `tools/run_personal_agent_smoke.py` | 临时目录跑真实内核与 typed prompt 序列化 | 真实手机、真实执行者或模型评测 |
| `tests/test_personal_tasks.py` | 27 个任务契约测试 | 远程 exactly-once 或断电证明 |
| `tests/test_device_context.py` | 30 个观测生命周期测试 | Android/iOS/华为手机鸿蒙真机可用性 |

这轮没有改既有生产模块。两个新模块都需要显式调用，没有从 app/controller 自动激活。因此旧桌面角色/存档/插件默认行为保持原有路径。

## 最值得继续做的一条用户闭环

**手机输入 → 已认证的 E-Moti 会话 → 电脑当前角色回复 → 用户明确采纳一条任务建议 → 权威执行者接受 → 手机上查看来源明确的阶段报告。**

先把这个闭环跑通，再增加被动观察。Android 第一版采用 Kotlin/Compose 可以直接管理生命周期、分享与系统授权；不要同时开发三个原生客户端或先迁移整个 Python 应用。可以用简单网页测试协议，但它不能代替原生观察实现。

### 宿主与认证

为现有 controller 写窄 facade，复用 `DialogueRequest`、typed request 和现有记忆管理服务；通过命令队列进入正确线程。一个 owner/角色只保留一个权威会话，避免桌面与网络回调并发写同一存档。手机请求中的身份字段不能直接决定 store namespace。

设备配对、凭据安全存储、scope、撤销、有效期与 TLS 要在暴露远程 API 前完成。当前观察票据只用来废止旧 collector 会话，不是网络登录凭据。Tailscale 可选，不替代应用授权；不要开放 Relay 内部端口冒充 E-Moti API。

### Relay 适配

先只读核实实际 Relay 契约。本批没有新增 Relay 端点，没有复制其私有实现；`simulated_authority` 只是 fixture。需要的最小责任是：能力发现、受控提交、按 command ID 核对、读取任务/事件游标、取消与结果引用。Relay 项目继续独立提供真实调度和权限，E-Moti 保存关联和汇报。

下游不支持 command ID 查询/去重时，不允许通过“超时后重试”宣称可靠。缺失取消能力时显示不可取消/待确认，不把 UI 状态改成已停止。完整结果验收另外核对实际文件与测试，不信任一个证据字符串就宣称完成。

### 观察接入前的必要门禁

原生 collector 的 App 范围、授权、停止回调、采集空窗和 source method 必须可信映射。OS 权限撤回应 revoke 对应票据；记忆纠正/遗忘后先同步 `advance_memory_epoch()`，再接受新票据下的观察。用户切角色时 close 旧 buffer 并创建新实例。

现有桌面对话会保存模型回复，因此不能只加一个 plugin context provider 就开启被动观察。必须给观察衍生聊天记录、摘要、TTS、设备缓存保留来源/有效期；在撤回、过期、切角色或重连时失效。调用模型前和展示前都检查 `is_current()`；已发送到第三方的数据不能由本地撤回。补充实际端到端测试后才能在 UI 打开功能。

## 验证与复现

```bash
python -m pip install -e . pytest
python -m pytest tests/test_personal_tasks.py tests/test_device_context.py -q
python tools/run_personal_agent_smoke.py --output personal-agent-smoke.json
python -m pytest -q
```

Linux headless 可参照验证文件中的 Qt、时区、PYTHONPATH 与 native-library 设置。全量结果是 1390 passed / 1 failed；旧视频导入测试使用 Windows `ffmpeg.cmd` fixture，在 Linux 误选系统 ffmpeg，是本批已在未修改 fa19b2c 再次复现的失败。不能把跳过此测试当成新增代码全平台通过。

本批研究用了固定开源提交与官方资料，但部分华为页面只能读取索引/空壳；OpenHarmony 系统权限证据不是华为手机三方获批承诺。Qt 发布说明与专项文档对 HarmonyOS 成熟度措辞不同。移植时应选择目标 SDK/分发签名后实测，不根据项目名或 README 标签下结论。

## 当前保留的限制

任务 DB 被删除或回滚旧备份后，去重事实可能丢失，必须向权威端对账。观察 buffer 是内存状态，重启不保留授权或内容；未来若持久化授权，仍必须换会话票据并同步撤回信息。派发 API 暂时没有预算/期限/自动重试/真正后台推进器，建议采纳也不意味着下游已经收到。

下一批应保留真实运行证据：APK、目标手机型号/build/API/应用版本、权限撤回行为、电脑休眠/网络切换、跨小时任务报告、取消回执，以及真实模型说错状态的 bad case。不要用新的模拟 fixture 替代这些验收。
