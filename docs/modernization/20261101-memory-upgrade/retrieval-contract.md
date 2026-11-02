# Retrieval Contract

对应生产代码：`retrieval_contract.py`、`retrieval_router.py`、`retrieval_evidence.py`、`ondemand_memory.py`。本契约用于 Codex 后端、Claude 产品/前端和评测工具。外部文本只能作为数据，不获得写入人格、存档或工具权限。

## 调用顺序

```python
future = memory.prepare_retrieval(
    message, now=logical_time, history=current_epoch_user_window,
)
if future is not None:
    # 桌面通过异步信号等待，不能在 GUI 主线程等待推理。
    future.result()
result = memory.retrieve(
    message, now=logical_time, history=current_epoch_user_window,
    scope="companion", top_k=4, layered=True,
)
payload = result.bundle.to_prompt_payload()
receipt = result.trace.to_dict()
```

`prepare_retrieval` 负责需要时的后台 embedding 准备；`retrieve` 使用已准备评分和当前 SQLite 证据。未准备/未启用语义模型时仍可运行词法及结构化路径，trace 会标明实际情况。不能在 benchmark 中无条件给闲聊调用 prepare，再把该额外成本算成新路由的必要成本。

`build_context` 是返回 bundle 的便利 API，生产默认走新路径；`build_legacy_context` 是保留的旧快照对照。`recall` 保持原低层兼容语义，新的交互产品应优先调用 retrieve 并处理状态。

## 输入与隔离

| 输入 | 含义与限制 |
|---|---|
| query | 当前用户文本；本地规划最多处理 1200 字符，仍受桌面消息自身限制 |
| history | 当前角色、当前 epoch 的近期窗口；支持 role + text/content；仅用户文本用于指代 |
| now / time_basis | 宿主明确时间；service 默认 logical 兼容旧桌宠。只有保证全部相关有效时间为 Unix 秒的档案才显式 time_basis="unix"；不猜测旧时间 |
| owner/character | 绑定 service/store 实例；调用者不能借 query 覆写 |
| scope | 默认 companion；显式任务经验路由进入 task_experience；外部实时状态独立读取 |
| top_k/budget | 共同控制候选数、意图数、展开次数、最终来源数和字符预算；token 数另测 |

默认最多 4 个意图，每意图第一轮词法与语义候选合计最多 64 条（语义最多占一半），整次请求最多一次额外 64 条的扩展，最终最多 8 个来源（通常 top_k=4）。资格/来源依赖可额外读取，但有独立边界。字符预算不是 tokenizer token 数。评测显式固定相同 6000 字符记忆上下文上限，最终还经过同一 ExpressionRequest 和 8192 字符 provider 总 prompt 预算。

## 路由

| route | 典型问题 | 读取行为 | 不允许的退化 |
|---|---|---|---|
| chat | 闲聊、一般知识、创作 | persona、近期窗口、小型有效 bond profile | 为显得亲切而全库找往事 |
| fact | 用户姓名、偏好、某人的职业 | 主体/别名、字段、有效时间；必要时查可信旧字面事实 | 把相近人物或不同字段作为答案 |
| episode | 个人或共同的过去经历、阶段回顾 | 已发生事件候选、L1/L2、来源校验；原问明确共同参与时核查双方依据 | 把计划或模型故事当发生过，或把个人经历说成共同亲历 |
| task | 上次部署/导出/备份经验 | task_experience，应用/版本/前提/结果 | 用其他应用或版本的经验替代精确问题 |
| live | Relay 任务现在完成了吗 | 有来源、有版本、有时效的外部状态接口 | 用昨天的经验推断当前状态 |
| bounded | 未明确但可能需要回忆 | 有限 FTS/BGE 候选及严格证据检查 | 无限检索或把最相似项强行当答案 |

同一问题可以有多个意图，chat 子意图保留在 trace 中，但不发起候选检索。最终来源预算按意图轮流分配，避免第一个子问题吃完上下文。无法回答的子问题保留为不足状态。主体续接不能把 live/task/episode 改写为另一个人的职业事实。

## 输出状态

| status | 含义 | Claude 侧建议表现 |
|---|---|---|
| not_needed | 本轮无需长期候选检索 | 正常聊天；不展示“没有记忆”的错误提示 |
| sufficient | 本地证据策略认为已覆盖请求 | 用有效证据自然回答，按需提供“记忆依据”入口 |
| unknown | 查找后没有支持该具体问题的合法证据 | 简短自然地说明目前不清楚，不默认要求用户重填信息 |
| insufficient | 有部分证据、指代歧义、冲突或预算不足 | 只说有依据部分，明确还缺什么，不把部分答案补全 |
| external_unavailable | 实时权威未配置、过期或不可用 | 说明暂时无法查看当前状态，不能声称任务成功/失败 |
| unavailable | 来源持续并发变化，或用户展开的概览版本已失效 | 提示记忆正在更新，刷新有效概览后重试 |

`semantic_status` 独立于答案状态。词法或结构化证据足够时，语义服务不可用不必使回答失败；没有语义评分也不能谎称执行过 BGE。

## 资格 → 相关性 → 充分性 → 扩展

1. SQLite 预筛 owner、角色、scope、撤销、置信度和有效时间；候选正文随后再次验证。
2. 可识别主体和字段采用硬约束。别名先解析为唯一主体，并带上绑定来源。歧义不随意选人。
3. 经历必须有已发生来源。任务经验需 outcome，并检查应用和版本。计划以 planned 明示。
4. 查询具名作品、人物、具体原因/颜色/数量等时，来源必须支持所问属性；仅主题相关不足以回答细节。
5. 原始候选不够时进行一次有界补查，不放松主体、字段、时间和撤销规则。允许返回零条。
6. 选中来源及实体解析依赖在最终事务再次核对。失败最多重试 3 次，不发布混合 epoch 的上下文。

开放字段不要求预注册固定 schema：已有字段优先精确查询，陌生 predicate 用主体约束 + 有界 FTS 候选，再核验正文的字面值、所问属性和全部物件限定词。数字/false 使用与更正相同的完整字面边界，0/false 不等于无值。语义相似不能绕过证明；同类型物件的东/西等差异也不能当成小的排名扣分。

显式复合人物（如某人的助理）只有完整有效别名可解析，绑定撤销后不能退回到较短的上级人物。一个明确别名只需一个有效来源，优先复用本轮已交付的答案来源；resolution_evidence 仅发送源指纹及 alias→subjects 绑定，不附带该来源中无关的全部事实正文。绑定仍进入最终来源认证与遗忘评测。

任务的 sufficient 只针对过去证据。提出当前复用、适用或成功保证时返回 applicability=requires_current_validation，并保留有依据的历史卡片；未核实当前设备/版本/前提，不保证照做成功。任意自由文本前提的完整逻辑推理和真实外部验证仍未实现。

本地规则仍会有表达覆盖缺口。它不是通用 NLI，也不是事实正确概率模型。改进规则应使用开发/验证集，最终留出集错误应进入下一轮回归，不能继续称为未见测试。

## 时间

`current` 只用当前有效事实。`history` 只用已过期但未撤回的合法历史，`as_of` 将档案 IANA 时区的日/月转换为 UTC 半开区间 `[as_of, as_of_end)`；事实按有效区间重叠判断，事件/任务按 occurred_at 判断，并把日期窗推入 SQL 后再截候选，`timeline` 对照当前/历史并保留区间，`planned` 只表示计划。计划同时有日期窗时，宿主核查来源原文的计划日期及有效区间，不把记录时间当计划发生日；同段多个不同日期无法确定用途时拒绝猜测。更正旧版本和显式遗忘从不因时间查询恢复。历史条目不能作为当前 profile、别名或语义缓存的依赖。

旧桌面 self.now 来自游戏/互动逻辑计数，不能冒充 Unix 日期。默认 logical 档案遇到日历查询返回 insufficient / unresolved_time_basis_or_date，保留当前/逻辑历史读取。显式 Unix 档案支持缺省年份的月日（以传入 now 推断）、月窗口及非法日期拒绝；不回退机器当前日期。本次已实现档案时间基准、IANA 时区/DST 与写入来源的发生/记录时间标注；旧逻辑时间仍保持 logical，没有将旧桌宠存档整体转换为日历时间。

## 来源、分层与 trace

L1 的 `memory_overview.claims` 与 L2 的 `shared_memories` 都是正式交付证据。评测必须检查真实 prompt 中的字段，不能看到 trace.selected_memory_ids 就认定模型收到了答案。`resolution_evidence` 是多跳别名解析的有效辅助来源，应计入来源覆盖，不能混成新的用户事实。

概览显式展开接口为 `memory.expand_sources({memory_id: fingerprint}, expected_epoch=epoch, now=now, scope="companion")`，返回相同的 `RetrievalResult`，route 为 `source_expansion`，evidence_level 为 L2。调用不能超过 `max_source_entries`；缺少绑定或超限报参数错误。不同角色、已过期、已撤回、指纹变化的正文不能展开；过期客户端 epoch 返回 unavailable。此入口直接读取有效卡片，不进行全局检索，不调用 embedding。它尚未提供会话全文/外部日志 resolver。

当 provider 总预算需要丢弃证据时，按完整来源主张删除，重算概览计数/时间段，删除不再需要的别名绑定，并将受影响结果标成 insufficient/budget_limited。不得截断事实文字或留下无来源的“已充分”状态。人格必需字段不能通过裁剪证据来更改；必需固定材料本身超限会显式失败。

Trace 记录路由、各意图状态、资格/字段/主题拒绝原因、候选总量、实际解码行数、索引版本、epoch、展开次数、是否使用语义评分、重试次数和阶段耗时。`retrieval_calls=0` 表示没有候选检索，不等于零次 SQLite 元数据访问；人格与 profile 仍有廉价读取。`rows_loaded` 统计真实条目正文解码，不是数据库内部扫描行数；索引复杂度另由 EXPLAIN/VM-step 和规模实验测量。

## 外部实时接口

`ExternalStateEvidence` 包含 authority、summary、observed_at、valid_until、source_id、character_id、owner_id、version。当前实例、当前时间验证通过后仅加入本轮上下文，不写长期记忆。接口失效返回 external_unavailable。当前提供可接入契约及受控集成测试；没有伪造实际 Relay、手机或游戏在线调用的验证成绩。

接入方必须在自己的 worker/网络层实现超时、取消和状态缓存，不能让同步 reader 在 Qt 主线程无限等待。当前 reader 合约不替外部 SDK 实现网络调度；真实连接时需单独验收端到端 deadline。

## Claude 验收重点

- 不把 unknown 显示为崩溃，不把 not_needed 显示为“记忆失败”。
- 点击依据时区分用户事实、历史事实、计划、共同事件和外部实时状态。
- 纠正/遗忘提交后立即清除旧卡片、旧展开内容和旧回答候选；重连先撤销后使用缓存。
- 对“有记录但未覆盖问题”的情况展示缺失属性，而不是显示一个看似肯定的绿色“已记住”。
- 人格编辑与用户事实编辑保持不同入口；检索状态不改变角色性格。


## 最终预算与在途时效

服务、ExpressionRequest 和实际 provider prompt 分别有界，裁剪以完整证据卡/完整摘录主张为单位。被裁去的证据不能继续留下 `sufficient` 或孤立的别名证明；`trace.intent_status` 与服务实际交付的状态一致。预算后无证据是 `insufficient`，不能冒充数据库中没有记录。人格核心优先保留。

旧存档存在明确用户原话但无结构字段时，有一次有界 FTS 展开与原文验证：只接受可信明确保存来源，以完整属性或完全一致的情境和对象匹配，不靠相似人物或一个主题词判断。该验证不反写新的权威 metadata，未支持的句式仍拒绝；它不能替代通用事实抽取。

桌面完成回答前同时核查角色、当前 `context_epoch` 和仍在上下文中的每份外部证据 TTL。即使本地记忆没有改动，实时接口的证据也会过期；生成期间跨过 `valid_until` 的旧答案不得发布。这里沿用 controller 逻辑时钟，不混用墙钟。旧 writer 修改/删除已有来源也会补进 epoch，具体见存储说明。
