# chat-memory-benchmark 接入评估（2026-11-06）

## 结论与当前状态

建议采用这个外部公开基准，补充 E-Moti 的“原始聊天进入记忆、跨时间独立答题”验证。它不能替代独立密封样本、人格体验、来源撤销与桌面生命周期验证。当前只完成源码审查和上游离线工具验证，**没有完成 E-Moti 的 714 题模型作答或评分，也没有可报告的 E-Moti 基准成绩**。

固定上游版本为 [`07a11f4074cde1106c5fed9f627e662ff1a3abc1`](https://github.com/Ornn8/chat-memory-benchmark/tree/07a11f4074cde1106c5fed9f627e662ff1a3abc1)。本地只读副本在忽略目录 `artifacts/codex_handoff/chat-memory-benchmark-upstream/`。审查读取方法、接入、评分实现和测试；没有向开发模型展示正式题目、答案或证据。完整性测试程序会读取正式文件进行校验。正式数据已经公开，即使本轮开发未阅卷，也只能称外部公开测试，不能称新密封样本。

## 适用范围

正式卷包含六名合成人物、714 个问题实例，面向每天约两轮、最长半年的低频个人聊天。27 类考点包含人物关系、事实纠错、现实变化、相似事件、相对日期、计划与假设、转述、信息不足和隐私边界，适合暴露 E-Moti 当前提取与检索之间的遗漏。

上游要求既有用户消息和助手回复按时间进入系统原生记忆流程；考试只能使用截止点前的记忆，不把全历史附给作答模型，不重生成历史助手回复，不把考试题和回答写入后续历史。相比当前预置卡片的检索评测，这增加了真实提取、更新及长期维护环节。详见固定版本的[测试方法](https://github.com/Ornn8/chat-memory-benchmark/blob/07a11f4074cde1106c5fed9f627e662ff1a3abc1/docs/methodology.md)。

同一事实在不同间隔反复提问，问题实例不是彼此独立的事实样本；考点标签存在重叠，不能将各组分母相加。上游不评分角色语气，也不覆盖 Qt 线程、跨设备缓存撤销、在途取消、真实重启与万条存储性能。E-Moti 原有评测仍需保留。

## 评分实现核查

[`grading/grade.py`](https://github.com/Ornn8/chat-memory-benchmark/blob/07a11f4074cde1106c5fed9f627e662ff1a3abc1/grading/grade.py) 负责离线准备和汇总，不调用模型，也不独立理解语义：

1. `prepare` 合并题目、判据、原始来源、实际回答与回答/判据哈希。
2. 人或模型根据每项必需条件和禁止错误填写判断文件。
3. `score` 校验 ID 对应、哈希、字段类型和逐项数量，再汇总通过率。

必须保留裁判版本、逐项判断与理由，不能把脚本成功当作语义正确。评分允许少于三件无关旧事且无不当隐私披露时通过相关性条件；因此不能用这个分数代替 E-Moti 对多余建议、套话和角色语气的验收。

上游不同系统使用不同嵌入模型、短期窗口、维护开关、调用渠道和裁判；部分对照复用此前输出。比较 E-Moti 时应声明自己的 Flash、BGE、预算及近期窗口，使用同卷共同已答题，不将公开排行榜当作同配置架构消融。详见[测试配置与局限](https://github.com/Ornn8/chat-memory-benchmark/blob/07a11f4074cde1106c5fed9f627e662ff1a3abc1/docs/tested-configurations.md)。

## 已实际运行的离线检查

在固定上游副本、`PYTHONUTF8=1` 下执行：

| 命令 | 实际结果 |
| --- | --- |
| `python demo/read_exam.py --verify-all` | 108 个输入通过 SHA、时间顺序和精确截止点校验 |
| `python datasets/natural-timegrid-20261101-v2/read_exam.py --verify-all` | 714 个输入、9 个 manifest 文件通过；网络调用 0 |
| `python -m unittest discover -s tests -v` | 17 项通过，2.242 秒 |

正式读题器仅输出原始消息字段，验证人物范围、历史路径、SHA、带时区时间、连续回合及截止点；答案仅应进入评分阶段。离线检查没有验证模型效果。

公开示例最早考试为 `PUB01-C001/d00`，截止第 **5** 轮，考试时间 `2026-01-07T19:10:01+08:00`。可以用这一小段先验证回放与答题边界。由于只有五轮且是当天问题，答案可能直接存在近期窗口；单题成功不能证明长期记忆。

## E-Moti 原生接入约束

当前 `tools/eval_ondemand_memory.py` 使用预置卡片评测检索。正式接入不能依据上游答案或事实证据生成“正确卡片”，也不能外挂另一套检索补答案。

`DesktopDialogueService.submit()` 会重新生成助手回复；设 `include_ai_expression=False` 又跳过模型抽取。两者均不能直接代替固定历史回放。上游也没有提供现成的 E-Moti 或通用社区系统适配器，详见[接入说明](https://github.com/Ornn8/chat-memory-benchmark/blob/07a11f4074cde1106c5fed9f627e662ff1a3abc1/docs/integration.md)。

工具级试跑应复用现有实现：

1. 每个人物使用隔离的 `PluginEnabledCompanionController` 和测试存档。按回合推进可信测试时钟，不修改系统时钟。上游 ISO 时间有明确时区，测试副本可以明确选用 Unix；不得将旧真实存档的 `time_basis=logical` 推断成日历时间。
2. 在 controller 所有者线程调用 `_prepare_host_memory(DialogueRequest)`，复用 quiet、显式候选、本地普通事实和来源失效路径。
3. 与 `DesktopDialogueService` 相同，仅在 `ignored/clarify` 且 `should_extract` 时调用 `chat_memory_extraction.prepare`、真实 `extract_memory`、`apply`。保留真实模型提议及拒绝，epoch 变化调用已有 `_on_memory_invalidated`。不能将被原生流程忽略的叙事、计划或开放属性用答案补写。
4. 通过 `append_dialogue_exchange` 保存原用户消息和原助手回复，再调用 `dialogue_history_store.save` 与原持久化方法；保留 speaker 和 epoch，不把助手推测升格为用户事实。记录本工具调用原生内部入库方法，并非重新执行整段桌面对话生成。
5. 到考试节点，从隔离副本走原生检索与表达入口，声明近期窗口。考试题与回答不得污染后续回放主档；仅清理最终 prompt 不足以保证历史隔离。
6. 先冻结回答，再在单独评分步骤读取上游答案与证据。保存提取结果、候选、实际最终 provider prompt、原始输出、模型版本、usage、耗时和失败状态，分别区分未存入、未召回、未交付和生成错误。

优先用公开示例证明接入正确，再运行正式卷。公开集上的修复结果属于公开回归；新的泛化结论仍需未参与开发的密封数据。

## 许可

上游代码、文档和合成数据采用 [MIT 许可](https://github.com/Ornn8/chat-memory-benchmark/blob/07a11f4074cde1106c5fed9f627e662ff1a3abc1/LICENSE)，版权为 `Copyright (c) 2026 Ornn8`。复制或分发其实现、数据时保留版权和许可。当前仅在忽略目录保留固定副本，不把题库加入生产存档或应用启动数据。
