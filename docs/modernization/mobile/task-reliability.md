# 可持久化任务监督：本批实现与可靠性的含义

日期：2026-10-28（America/Los_Angeles）。实现为 [`personal_tasks.py`](../../../src/guanghe_companion/personal_tasks.py)，回归为 [`test_personal_tasks.py`](../../../tests/test_personal_tasks.py)。本文描述 E-Moti 本体的增量代码，不代表已连通手机、Relay、Codex 或 Claude。

## 1. 任务边界

E-Moti 可以提出建议、等待用户采纳、保存已采纳的指令、跟踪外部执行者的回执并展示阶段性结果。实际执行者继续拥有调度、工作区权限、进程、工具及自身任务状态。E-Moti 的任务记录是一个带来源的本地镜像和发送前记录，不替代执行者的任务数据库。

本批提供标准库 SQLite 薄模块，尚未接入桌面控制器，也没有网络监听、后台轮询、开机启动、模型自主执行、真实 Relay 适配器或手机端。模块仅由显式调用驱动，所有时间由调用方传入；测试没有睡眠、网络或真实执行动作。任务记录与 Emotional Memory 的用途不同，不向情感记忆、关系或人格文件写入。

一次建议中的 `authority`、标题和指令在创建后保持不变。修改建议应创建新建议，并重新采纳；重复手机请求可以带同一个 `proposal_key`。同一 owner、角色下，同 key 同内容返回原任务，同 key 不同内容报冲突，避免一次批准被挪用给另一件事。

## 2. 状态与事实分开

| 状态 | 可以确认的事实 | 不能据此声称 |
|---|---|---|
| `proposed` | 存在一条待采纳建议 | 用户已经授权或执行者已经开始 |
| `queued` | 用户已通过宿主入口采纳原建议 | 网络已经发送成功 |
| `dispatching` | 发送权及唯一 `command_id` 已经提交本地数据库 | 外部执行者一定收到了请求 |
| `delivery_unknown` | 调用方报告发送结果未知 | 请求失败，所以可以重新执行 |
| `accepted` | 对应执行者回执提供了 `external_task_id` | 工作已开始或已完成 |
| `running` / `blocked` | 外部执行者上次报告正在进行或受阻 | 长时间无更新后仍然处于同一实时状态 |
| `cancel_requested` | 用户提出取消；是否停止尚待执行者确认 | 取消按钮已经终止远程工作 |
| `succeeded` | 执行者报告完成且给出结果引用 | E-Moti 独立核验了产物、用户已经验收，或所有工作目标必然达成 |
| `failed` / `cancelled` | 收到对应终态，或未发送的任务已被本地取消 | 之前发生的外部副作用一定已经回滚 |

`task_report()` 同时返回记录状态、执行者名称、外部任务 ID、checkpoint、结果引用、最后来源观察时间、最后本地接收时间和 `freshness`。过期的 `running` 会带 `freshness="stale"` 与 `needs_reconciliation=true`；未来界面和模型表达必须据此说“上次报告正在进行，当前待核对”，不能单独读取 state 后描述实时运行。

`due_for_check(now, stale_after)` 只返回需要核对的任务，不会自行联网。未来 poll runner 可以用它查询权威执行者。读回旧缓存不能更新来源时间；完全相同的重复事件不刷新接收时间，也不重复产生阶段事件。一次本地“取消请求”同样不能伪装成新进度。

## 3. 已实现的可靠性约束

### 3.1 先记录发送权，再交给适配器

`claim_dispatch()` 在 `BEGIN IMMEDIATE` 事务内将任务从 queued 改为 dispatching，并保存唯一 command ID。事务成功后返回不可变的 `TaskCommand`。同一任务只能领取一次；重启或第二个 store 实例不会使已经领取的指令再次变为可发送。

这提供的是**不自动重复执行未知结果请求**的本地保证，不是分布式 exactly-once 保证。网络中断可能发生在执行者已接收、E-Moti 尚未保存回执的窗口；也可能发生在真正发出前。两种情况都不能根据本地超时直接区分。

未来适配器应让权威端支持 `command_id` 幂等和按该 ID 查询。查询到已接收时调用 `record_dispatch_receipt()`；查询不到或权威端不具备可信查询能力时保留未知状态，交给用户核对。本批没有提供“把未知任务重新排队”的自动重试方法，也没有宣称所有现有执行器已支持这套协议。

### 3.2 用户批准与外部回执有不同入口

`approve()` 是供可信宿主处理已认证用户动作的入口。模型可以提出建议，但不能把文本里的“已确认”或外部事件中的某个布尔值当成授权。该模块自身不是登录、设备配对或网络鉴权系统；未来手机路由必须先完成身份和能力授权，再选择绑定 owner、character 的 store。

外部适配器负责绑定实际来源。JSON 自报的 `authority` 不构成来源认证。代码仍逐项核对 owner、角色、authority、原始 start command ID 和 external task ID，防止连接层的映射错误把别的执行者或旧 attempt 的结果写到当前任务。

### 3.3 事件去重、版本顺序与终态

每个任务的执行者事件携带 `event_id` 和单调递增的 `sequence`。同 ID 同内容是幂等重放；同 ID 内容不同报 `TaskConflict`。落后于当前 sequence 的新事件不覆盖当前状态。事件与任务状态在一个事务中提交，避免看到“日志已完成、任务仍运行”的部分提交。

已经进入终态的任务不接受另一个更晚的新状态事件；冲突显式报 `TaskTransitionError`，等待人工或未来的对账入口处理。代码不会用“最后一个包获胜”来覆盖取消或完成事实。`sequence` 由未来适配器根据权威执行者的可靠版本映射，不能随意把网络到达序号当作原始状态版本。

### 3.4 取消不是立即完成的事实

尚未派发的建议或 queued 任务可以直接本地取消，之后无法领取 start 指令。已经派发的任务进入 cancel_requested；获取 external task ID 后，支持取消的适配器可以通过 `claim_cancel()` 领取一次独立 cancel command。

若取消发送回执未知，同样不重新领取。后续任务状态事件仍引用原 start command ID，表示同一执行 attempt 的权威结果；cancel command ID 用于传输层对取消请求去重。收到 cancelled 终态才确认停止。

若真实成功事件先于取消生效，保留成功结果和取消意图，并在报告中给出 `cancellation_outcome="completion_won_race"`。这说明任务已经完成、取消未赶上；不丢掉真实产物，也不假装用户取消已成功。

### 3.5 完成需要引用，验收仍需后续实现

`succeeded` 必须附带至少一条有限长度的结果引用。例如适配器可给测试报告、代码 diff、执行记录或构建产物的引用；本批仅检查结构和来源归属，不访问或验证引用所指的内容。报告明确标记 `completion_claim="reported_by_authority"`。

未来“可靠伙伴”的完整验收还要加入：任务验收条件、必要检查、产物可访问性、风险动作权限、预算与期限，以及用户需要介入的明确原因。先把收到、运行、报告完成和验收通过分开，再添加实际可验证的检查。不能用一个更自信的模型总结替代这些事实。

## 4. 接入示例

下面的 authority 和回执是演示数据，不对应任何现成 Relay 端点。模块不会执行 `instruction`。

```python
from pathlib import Path
from guanghe_companion.personal_tasks import PersonalTaskStore, TaskEvent

tasks = PersonalTaskStore(Path("runtime/tasks.sqlite3"),
                          owner_id="local-user", character_id="original_oc")
proposal = tasks.propose(
    proposal_key="phone-request-42", authority="demo-executor",
    title="检查测试结果", instruction="运行已授权项目的测试并提供报告。", now=100,
)
# 仅由已认证的用户采纳动作调用，不由 LLM 输出直接调用。
tasks.approve(proposal.task_id, now=101)
command = tasks.claim_dispatch(proposal.task_id, now=102)
assert command is not None

# 未来 adapter 将 command 发送给执行者；这里仅演示保存回执。
tasks.record_dispatch_receipt(
    proposal.task_id, command_id=command.command_id, authority="demo-executor",
    external_task_id="executor-task-1", now=103,
)
tasks.apply_event(TaskEvent(
    task_id=proposal.task_id, owner_id="local-user", character_id="original_oc",
    authority="demo-executor", command_id=command.command_id,
    external_task_id="executor-task-1", event_id="executor-event-1", sequence=1,
    status="succeeded", checkpoint="演示执行者报告完成。", observed_at=104,
    evidence_refs=("artifact:demo-report",),
), now=105)
report = tasks.task_report(proposal.task_id, now=106)
assert report["completion_claim"] == "reported_by_authority"
```

## 5. 存储与当前限制

新模块创建独立 `tasks`、`task_events` SQLite 表，schema version 1，事务使用 `synchronous=FULL`。没有任务内容时不涉及原有角色或记忆存档迁移；不应把它指向已有情感记忆数据库。未知版本、已有不认识的表以及缺表的已初始化数据库均拒绝覆盖。

任务指令和阶段性文本属于用户数据；本批没有云同步、应用层加密、删除 UI、自动清理、备份合并或跨设备数据库多主写入。建议由电脑端作为唯一任务镜像权威，手机通过未来的已认证接口读取和发起用户动作。物理删除数据库或恢复旧备份会丢失幂等记录；本模块不具备在历史丢失后从外部恢复发送事实的能力，必须先向权威执行者核对。不能拿一份旧数据库立即重发未见回执的任务。

此外，未实现队列重试调度、有限预算执行、定时阶段汇报投递、用户验收、网络连接、真实模型或真机测试。本批的“持久化”验收是重开数据库后记录和单次领取保护仍在；未进行拔电、磁盘损坏、Windows 多进程压力或远程协议一致性试验。

## 6. 本批测试证据

遵循仓库 TDD：先新增测试并实际运行，确认因 `guanghe_companion.personal_tasks` 尚不存在而 collection 失败；实现后运行相同测试文件。首次完成记录：**27 passed in 0.88s**，Python 3.12、pytest 9.1.1，未使用网络执行者。最终集成成绩以本批总验收记录为准。

有意义的回归包括：未采纳不可派发、同 key 冲突、重启后未知请求不可重发、两个 store 不能二次领取、接收回执不等于开始工作、事件去重与乱序、同 ID 不同 payload、五项身份/attempt 错配、无证据完成、取消两阶段与完成竞态、终态冲突、外部时间过期、跨 owner/角色隔离、非法事件不部分提交、未知数据库版本保持不动，以及不创建人格/情感记忆文件。
