# 下一批开发提示词：以本轮真实代码和证据为起点

这份提示词取代第一批“先做 B3a/B3b”的执行顺序。本轮已实现按需路由、结构化投影、增量向量、来源分层及其评测入口；不能重新生成一套并行记忆系统。先读 `ondemand-gap-matrix.md`、`ondemand-evaluation.md` 和交付清单，确认最新 main/PR 是否已包含这些提交。

## 给 Codex：记忆后端、生命周期、性能与评测

```text
你负责 E-Moti 核心后端。先读取 AGENTS.md、HANDOFF.MD、最新 main、开放 PR、工作分支和未提交改动。
本任务继续独立 Personal Agent 的人格与记忆升级；不优先开发手机 UI、Relay 或硬件。
保留既有 Python/PySide6、角色资产、用户存档和手机源码。不要覆盖 Claude 的产品/前端工作。

必读 docs/modernization/20261101-memory-upgrade/ 的：
README、ondemand-gap-matrix、memory-architecture、retrieval-contract、storage-index-v1、
adr-memory-rag、ondemand-evaluation、ondemand-generation、handoff、evaluation-plan。
先核对先决一致性补丁与本轮增量是否已合入；已实现内容直接复用。
本轮独立留出失败必须先读 retrieval-release-assessment：新策略已是此分支默认路径，
strict仅7/33、recall 0.2121。0/10未知误注入不能抵消误拒。当前候选不应直接合入发布版。
下一包先改语义充分性/歧义路由和验证模式，不再为提高开发分数扩展实体或字段专用关键词。

当前真实接口：
- EmotionalMemoryService.prepare_retrieval / retrieve / build_context：桌面默认按需路径。
- build_legacy_context：固定旧路径对照，不作为新界面默认。
- expand_sources({memory_id: fingerprint}, expected_epoch, now, scope)：验证后的 L2 卡片展开。
- IndexedMemoryQuery/read_indexed_snapshot/finalize_indexed_recall：同库投影、有界读取、最终来源校验。
- current_index_state、index_manifest：generation/revision/epoch 与增量向量同步。
- ExternalStateEvidence：外部权威即时事实，只进入本轮上下文，不自动长期保存。
- maintenance：有界近期来源扫描、来源去重与最多一次章节写入；不声称全库后台调度已完成。

以下编号是工作包边界。优先并行推进第3项质量缺口、第6项真实模型与Claude桌面验收；
第1/2/4项完善状态和来源，第5项依据写瓶颈立项。先核对本轮最终bad cases，不能只看开发集高分：
1. 统一桌面/Host/相册的提交与发布版本契约及明确时钟域。旧桌面逻辑秒不能当Unix，
   新service默认time_basis=logical，Unix档案需显式声明；不要直接将旧存档数值乘倍率猜成日期。
   给出逐来源发生/有效/记录时间、IANA时区与可验证迁移，再开放真实日历查询。
   统一桌面/Host/相册的提交与发布版本契约。区分 input_version、committed_version、request_id；
   自己合法写入导致的 epoch 更新与外部撤销不同。保持 Qt 线程所有权、取消和迟到结果屏障。
2. 建立完整的事实更新状态机：纠正、现实变化、过期、遗忘、物理删除分开。
   现实变化保留合法有效时间区间；撤销旧更正不能借历史查询复活。
   有界JSON fact_value 已支持显式结构化caller更正及遗忘，复用正文逐leaf证明，不重造另一存储。给出实际旧存档迁移和回退测试。
3. 依据保留的开发/回归失败完善路由和证据充分性；冻结后再用新的独立未见故事验收。
   已用于改动的数据不能再称未见测试；第二sealed的首次失败和后续回归分数分开。
   规则仍有口语、数量、隐式关系和任务前提的覆盖边界；仅歧义路径考虑有预算的模型路由或重排。
   不用 cosine 当正确概率。区分资格不合法、明确不匹配、尚未证实、证据充分。
   开放属性不能在语义排序前被全部字面片段硬拒绝；语义补召回也不能放宽已知主体/时间/撤销约束。
   无答案误注入、有答案误拒和全部证据交付必须同时统计。只读 shadow 不能复用有 touch 副作用的 finalize。
4. 为原始会话和执行日志建立 claim/span 绑定 source resolver。不要直接把包含多事实的 original_quote
   塞回 prompt；已忘的一条事实可能藏在同轮其余原文中。按源版本、片段和权限展开，超限停止。
5. 根据真实写入瓶颈评估行式权威迁移。当前 JSON 仍是唯一权威，结构化表是可重建投影。
   先写 ADR 和兼容迁移，不让两个事实数据库相互竞争。FTS/BGE 可从当前权威重建。
6. 连接真实模型执行答案/未知/人格实验。使用 tools/eval_ondemand_generation.py 重放实际最终 prompt；
   保存 provider 返回模型标识、原始输出、usage、耗时和失败。没有 usage 不报 0 token，没有价格不报 0 成本。
   独立中文评审判断正确性、误拒、虚构共同经历与角色自然度，不把自动字符串命中当全域正确。

关键不变量：owner/角色/scope/时间/撤销优先于排序；别名绑定与答案一起复核；
L1 不能产生来源没有的主张；L1/L2 同源不重复；预算后仍需检查实际模型 prompt；
人格核心配置保持稳定，情绪只影响表达；关闭工作插件后仍能完整陪伴。

代码边界：你维护存储、迁移、retrieval_*、ondemand_memory、memory_hierarchy、semantic_memory、
memory_prompt_budget、memory_vector_cache、维护和评测。controller、story runtime、ExpressionRequest 与 Claude 共同约定单写者。
每包交付生产代码、先失败后通过的关键回归、完整 pytest、迁移/性能记录、真实 bad case、文档和剩余风险。
不得用 test double 证明真实模型或设备效果，不为好指标改 gold/排除失败。失败保留分母。
未经明确授权不 push、发 PR、合并或发布 Release；不删除真实用户数据。
```

## 给 Claude：记忆产品、桌面交互、人格体验与行为评测

```text
你负责 E-Moti 产品与前端。先核对最新 main/PR 和 Codex 文件归属，使用独立工作树。
必读 AGENTS.md、HANDOFF.MD 和 docs/modernization/20261101-memory-upgrade/ 的
README、ondemand-gap-matrix、memory-architecture、retrieval-contract、ondemand-evaluation、handoff。
同时读 retrieval-release-assessment。当前新检索未通过泛化验收，不能把“目前未确认”展示成
“你从没说过”；后端unknown/insufficient的语义整改需共同验收。完成UI不等于通过默认发布门槛。

当前优先是独立桌面伙伴的人格和记忆体验。手机已有代码保留，手机扩展排在核心验收之后。
目标角色：好奇、聪明、自然、有判断、偶尔轻吐槽；不谄媚、不虚构亲密、不强求回应，也能安静。
不要把主动性等同于提醒用户工作；关闭所有工作插件后仍是完整的角色。

第一包：接通后端现有能力，不只画新的记忆页面。
- 回忆册区分当前事实、可用历史、计划、共同事件、任务经验和实时外部状态。
- 展示每条事实的主体/字段、来源、发生/记录/有效时间、当前版本和作用域。
  逻辑时间与真实日历分开，unresolved_time_basis_or_date不能显示为具体1970年日期。
- L1 概览使用 memory_overview.claims，点击依据调用 expand_sources 并传 epoch+fingerprint。
  目前可展开有效记忆卡，并非完整聊天原文；不承诺后端未提供的全文来源能力。
- not_needed 是正常闲聊；unknown 是目前没有可靠证据；insufficient 是部分证据或需澄清；
  external_unavailable 是无法查看即时状态；unavailable 是版本变化或并发失效。
  不把它们都变成红色报错，不把部分证据画成“全部已确认”。
- 用户更正/遗忘后同步清掉旧卡片、展开弹窗、编辑草稿和迟到回答；重新联网先处理撤销事件。
- 区分“之前说错了”“现实变化了”“不再记住”“删除原始数据”。完整历史更新 API 尚未完成时，
  显示真实可用能力，不在 UI 上假装后端已经保存双时间历史。
- 记忆更新失败保留用户编辑内容；取消、重试、切角色、睡眠恢复均有可验证状态。

第二包：人格与长期陪伴的真实行为评测。
冻结多个角色的身份、风格、观点和分寸 rubric，并给每一维提供正反例。
分别验证配置 hash 稳定、核心人格实际进入最终 prompt、真实模型多轮行为稳定。
情绪反事实、用户不同意、连续失败、安静状态、无工作插件、已知信息不重复追问均入组。
未知时不编造、不默认逼用户重填，但也不能以一律拒答来追求安全分数。
主动关心有来源、有时机和冷却，接受/拒绝/延期/安静可控；自然度不能只看任务完成率。
与 Codex 用同一套最终 provider prompt、原始生成记录和两名独立中文评审，明确未运行项目。

后续手机平台明确为 Android/HyperOS、iPhone/iOS、华为原生 HarmonyOS，不是 macOS。
共用人格版本、长期事实权威和撤销协议；手机缓存、候选 outbox 与实时观察各有边界。
本包不启动手机界面重做，不修改 Relay 或硬件固件，不新增手机自己的长期事实真相。

交付生产接入、正常/异常/取消/恢复流程、实际桌面录屏或操作记录、行为评分原句、
文档与剩余问题。模型行为未测就写 not_run，不能用 mock 文本或 UI 原型充当真实功能。
不要覆盖角色资产、用户存档或 Codex 正在修改的核心文件。未经授权不发布 Release。
```

## 合包验收

| 门槛 | 责任 |
|---|---|
| 最新基线与 PR 无冲突、已有补丁不重复应用 | 双方 |
| 来源/版本/未知/部分证据/展开契约一致 | Codex 提供接口，Claude 实际消费 |
| 更正、遗忘、到期、角色切换后旧内容不回流 | 后端不变量 + 前端交互共同验收 |
| 实际 provider prompt 与人格必需字段验证 | Codex |
| 真实模型答案与人格自然度盲评 | Claude 组织，Codex 保存可复现数据 |
| 全量测试和本轮真实失败原样留存 | 合包者 |

测试通过不等于产品已经真实使用验证。新一轮改变了规则或数据后，应产生新结果文件，不覆盖本轮固定证据。
