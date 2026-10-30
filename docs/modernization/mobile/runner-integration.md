# 宿主任务监督入口

2026-10-29。实现：`src/guanghe_companion/personal_task_runner.py`。

## 已核查的 Relay

本机独立 Relay 仓库，只读核查 HEAD `ec5563fb709e7db6eef810326d8d80db77c65787`。当时仅有未跟踪 `apps/desktop/src-tauri/gen/`，未修改 Relay。以下路径均相对该仓库。

实际入口为 `apps/desktop/src-tauri/src/main.rs` 的 Tauri commands：

- `workbench_info()`：版本及已实现能力。
- `workbench_command(envelope)`：`protocolVersion="0.1.0"`、`requestId`、可选 `expectedRevision`、`command`。
- `workbench_snapshot()`、`workbench_events(after_seq, limit)`、`workbench_history(...)`。
- `workbench_run_output`、`workbench_run_input`、`workbench_run_changes`。

`schemas/command.schema.json` 已有 `message.post`、`room.start`、`room.stop`、`task.cancel`、`task.review`、`task.retry`。`crates/relay-core/src/coordinator.rs` 的 dispatch 先检查持久化 requestId/payload 回执；`storage.rs` 存在内部 `receipt(request_id)`。这些属于 Rust/Tauri 内部调用，当前未发现供 Python 宿主使用的认证 HTTP/IPC listener，bridge 也没有导出单独的按 requestId 查询接口。不能将 Tauri command 名称拼成 HTTP 路径。E-Moti 没有打开或写入 Relay 的实际数据库。

Relay 需独立提供认证传输及受限权限、提交回执到任务 ID 的关联、command ID 查询、版本化任务/事件、取消与结果访问。协议内 `accepted` / review 语义需按实际权威映射，不能把它直接等同 E-Moti 的 accepted 或独立验收。

## 可运行的监督器

```python
from pathlib import Path
from threading import Event, Thread
from time import time
from guanghe_companion.personal_tasks import PersonalTaskStore
from guanghe_companion.personal_task_runner import PersonalTaskRunner

# 路径位于宿主自己的运行数据目录；不要指向记忆 DB 或 Relay DB。
tasks = PersonalTaskStore(Path("data/host/tasks.sqlite3"),
                          owner_id="local-user", character_id="xingxi_pixel_pet")
runner = PersonalTaskRunner(tasks, Path("data/host/supervision.sqlite3"))
# 认证宿主完成 propose / approve 后，对该 task_id 调用：
# runner.watch(task_id, now=time(), deadline=time() + 3600, max_checks=60)
stop = Event()
worker = Thread(target=runner.run, args=(stop,), daemon=False)
worker.start()
# 关停时 stop.set(); worker.join()，不注册开机启动。
```

默认 executor 映射为空，因此 `authority_unavailable` 是实际结果，queued 不领取发送权。当前没有可调用的 Relay adapter；示例不会执行外部任务。

监督计划持久记录期限、检查预算、下一检查时间、失败退避、阻塞原因及最新阶段事实。`watch` 不能扩大已有预算；预算耗尽或期限届满只停止监督，不谎称远程任务停止。增加预算的用户动作尚未提供。网络失败退避从 60 秒增加到最多 900 秒，正常检查间隔 30 秒。无适配器与等待批准不消耗网络检查预算。

将真实适配器按权威名称放入构造函数 `executors`。`TaskExecutor` 包含：

| 方法 | 要求 |
|---|---|
| `capabilities` | `ExecutorCapabilities` 分别声明 submit / lookup_command / events / cancel |
| `submit(TaskCommand) -> str` | 使用原 command_id，只提交已经领取的命令，返回权威 external_task_id |
| `lookup_command(command_id) -> str \| None` | 只读核对；None 保留未知，不再次 submit |
| `events(TaskSnapshot) -> tuple[TaskEvent, ...]` | 从权威版本映射事件，不把网络到达顺序伪造为权威序号 |
| `cancel(TaskCommand)` | 使用已持久化 cancel command ID；返回不等于 cancelled，等待状态事件 |

每个网络调用必须配置不超过 15 秒的超时；此接口不启动无法取消的无限等待。每个 namespace 由一个宿主 runner 管理。任务 store 仍独立保证一次发送权；检查预算在 I/O 前提交，崩溃后不重送未知 start/cancel。尚未验证多个宿主进程的部署，不能同时为同角色启动两个权威宿主。

## 阶段报告与界面

`step(now=...)` 返回变化的事实报告；`reports()` 在重启后仍能读取最新报告；`status(task_id)` 返回监督状态。报告包含原 task_report 的来源、外部编号、最后观察时间、新鲜度、结果引用与 completion_claim，另附 supervision。

runner 不操作 Qt，也不发送主动提醒。Qt/推送消费端应在自己的线程读取阶段事实，并通过宿主既有 `ProactiveCompanionService` 的安静时段、全局冷却、拒绝退避和每日次数策略再通知；不要把每次轮询当成一条提醒。当前自动通知装配未接入，未建立第二套催促策略。`run()` 持续保存事实，界面读取 `reports()`；手机后台不承担监督。

## 实际验证与未验

先运行原任务/观察测试：57 passed。新增测试首先因模块缺失失败；随后新增阶段报告恢复及期限检查测试分别复现 AttributeError 和期限延迟问题，修正后通过。

`python -m pytest tests/test_personal_task_runner.py tests/test_personal_tasks.py tests/test_device_context.py -q`：67 passed，含新增 10 条。测试实际创建、重开 SQLite，覆盖不可用 Relay 不领取、已领取的未知发送不重派、期限、预算不可悄然扩大、namespace、未知 schema 保留、取消终态及阶段事实恢复。没有模拟执行者，测试未声称验证 adapter 的真实网络行为。

未验：真实 Relay 提交/查询/取消、跨小时任务、电脑睡眠、真实断网恢复、真实任务结果独立验收、主动阶段通知。依赖真实认证桥接后补充端到端验证；当前实现不提供 Relay 联通成功结论。
