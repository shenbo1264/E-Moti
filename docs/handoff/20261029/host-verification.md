# 宿主后端实际验证

用户日期 2026-10-29，Windows、Python 3.11.9、PySide6 6.11.0、pytest 9.0.3。共同基线 `09c048b`，以下测试覆盖本批尚未提交的后端工作树。没有访问真实用户存档，数据库测试使用独立目录；报告在忽略目录 `artifacts/codex_handoff/`。

## 已运行

| 检查 | 结果 |
|---|---|
| 修改前 memory/controller/voice/task/device 聚焦回归 | 81 passed |
| 修改前本机完整基线 | 1384 passed、6 failed、1 skipped |
| 新 controller 对话生命周期及相关回归 | 119 passed |
| 新 task runner 加已有 task/device | 67 passed |
| 最后完整回归 | **1425 passed、1 skipped**，124.00 秒 |
| 最后宿主时钟同步小修正的补充聚焦检查 | 16 passed |
| 原 memory benchmark | **38/38**；检索11/11，prompt交付11/11，遗忘暴露0/10 |
| 独立 holdout 本地预检 | 10 条轨迹；检索3/3、prompt交付3/3、禁止片段排除5/5 |
| Git whitespace 检查 | passed |

完整回归命令：`$env:PYTHONUTF8='1'; python -m pytest -q -rs --disable-warnings --junitxml=artifacts/codex_handoff/pytest-host.xml`。唯一跳过是原 `test_persona.py` 符号链接测试，本机无相应能力。两条警告来自已安装 websockets 的弃用提示。

完整回归期间最后调整了宿主定时失效检查，使其与既有 controller 使用同一逻辑时钟；该变动另执行 `tests/test_host_service.py tests/test_host_dialogue.py`，16 项通过。没有将不同时间坐标混用于失效与后续召回。

基线六项失败中，四项为系统 cp1252 无法输出工具的中文，使用本次测试进程的 PYTHONUTF8 解决，未改系统环境。另两项先复现后修正：静音跨日 fixture 改用明确本地日期；旧 hygiene 词匹配命中文档普通措辞，修改该措辞，未放松断言。旧 Linux FFmpeg fixture 失败在本次 Windows 环境未出现。

## 实际网络与进程边界

`test_host_transport.py` 启动真实 Uvicorn socket，httpx 从独立线程请求，Qt 主线程执行已有 controller；没有替换网络、控制器、记忆库或模型供应商响应。模型关闭时使用现有本地表达并标记 local。覆盖一次配对、身份字段篡改拒绝、聊天、明确记忆添加、来源查询、纠正、遗忘、旧响应清除、旧版本拒绝、重复写入去重、凭据撤销和无 TLS 外部绑定拒绝。

纠正后从真实 controller 构造 prompt 验证新事实存在、旧事实消失；遗忘后新事实也不再进入 prompt。网络正文长度曾允许超过领域240字上限，新增失败测试复现后统一上限并以422拒绝，避免静默丢失后半段。

`test_host_process.py` 启动并终止独立 Python 宿主进程，再次启动同一测试数据目录：配对凭据及记忆保留，旧 session 请求返回 session_changed。它验证进程重启边界，不代替电脑睡眠或跨小时任务。

## 尚未完成或未验

- Claude 尚需装配桌面 snapshot_changed/TTS 刷新及手机协议；本批没有编辑 app.py，也没有 APK、IPA、HAP 或真机联通验收。
- TLS 参数门禁已测；真实局域网证书信任、手机系统权限与安装未验。
- Relay 只有已核查的内部 Tauri 入口，缺供 E-Moti 使用的认证传输与按 command ID 回执查询；没有执行真实 Relay 任务、跨小时监督、断网/睡眠或远程取消。
- runner 提供实际持久检查与阶段事实，自动提醒尚未装配，不绕过已有安静时段/节流去发通知。
- 环境未提供 EMOTI_HOLDOUT_API_KEY；真实回答正确率、人格行为、provider token 与模型延迟均 not_run。embedding 和自动人格演进未加入。
- 被动观察保持关闭，完整观察来源到手机缓存/音频撤回尚未接入。独立宿主必须使用隔离目录或在关闭旧桌面后使用其数据；旧桌面本身尚未共享独立宿主的进程锁。

代码、接口、启动与客户端规则见 [host-integration.md](host-integration.md)；真实 Relay 缺项见 [runner-integration.md](../../modernization/mobile/runner-integration.md)；评测口径见 [holdout.md](../../modernization/holdout.md)。
