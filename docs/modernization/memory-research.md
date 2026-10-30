# E-Moti 记忆系统与 Personal Agent 源码调研

核验日期：2026-10-25。依据 GitHub 实时仓库元数据、实际主分支代码、官方文档、维护者与用户 issue。本文为源码审查与选型研究；没有在本机部署这些外部记忆服务，没有复现其完整模型评测。已在 E-Moti 实现并集成的 Graphiti RRF 复用见第 12 节；全工程验证另见本目录的验证记录。

## 1. 结论先行

E-Moti 第一阶段适合保留单一权威存档与现有情感记忆模型，补齐来源、版本、失效传播和上下文入口校验。调研没有发现某个框架能够开箱即用保证“删掉一条记忆后，所有画像、摘要、历史、缓存和在途异步工作永不再次暴露它”。一些最新框架正处理与 E-Moti 同类的问题，整包替换会继承复杂度，同时失去现有角色关系与存档兼容性。

真正值得吸收的三个方向是：

1. Graphiti 的有效时间与记录时间分离、来源关联，以及多路排序融合。
2. Hindsight 的原始事实与归纳观察分离，以及任何来源失效即删除对应观察、重排剩余来源的事务规则。
3. Letta / EverOS 的可检查记忆与异步巩固。对 E-Moti 而言，异步任务应生成待审核派生物，不能直接覆盖稳定人格或让被遗忘来源复活。

## 2. 最新维护状态与许可证

以下 `pushed_at` 是 GitHub 仓库推送时间，不等于发布版本，也不能证明产品质量。固定主分支 tree SHA 记录在配套 [`evidence/memory-research-sources.json`](evidence/memory-research-sources.json)，大多项目仍频繁变化。

| 项目 | 核验时最近推送 UTC | 许可证 | 当前代码路线 | 对 E-Moti 的决定 |
|---|---|---|---|---|
| Letta 旧仓 | 10-18 22:28 | Apache-2.0 | README 指向 letta-code；旧 V1 API server 在 archive | 不依赖已退役 Python 服务 |
| Letta Code | 10-25 14:24 | Apache-2.0 | TypeScript stateful harness、MemFS、dreaming | 借鉴受控记忆块；不替换桌宠运行时 |
| Mem0 | 10-23 18:38 | Apache-2.0 | Python OSS 的 V3 ADD-only 流水线 | 可研究抽取/排序；不接入第二套权威记忆库 |
| Graphiti | 10-25 08:32 | Apache-2.0 | Python 时间图、检索与图驱动 | 实际复用小型 RRF；图后端暂缓 |
| Hindsight | 10-25 14:58 | MIT | Python retain/recall/reflect、Postgres/pgvector | 借鉴来源依赖与失效测试；整体服务暂缓 |
| MemOS | 10-24 15:17 | Apache-2.0 | Python memory OS 与 TS 本地 Agent 插件并存 | 借鉴过滤/接口；首批不引入复杂后端 |
| EverOS，原 EverMemOS | 10-22 12:57 | Apache-2.0 | Python、Markdown 真源、SQLite 状态、LanceDB 派生索引 | 借鉴可重建索引；不替换现有存档 |
| OpenViking | 10-25 10:25 | **AGPL-3.0** | Python context database、分层文件式上下文 | 只作架构比较，不复制主工程源码 |
| Honcho | 10-25 14:44 | **AGPL-3.0** | FastAPI、peer representations、后台推理 | 只作产品/架构参考，不复制服务源码 |

这九个仓库实时元数据均 `archived=false`。已直接读取除 Honcho 外上述主项目 LICENSE；Honcho 的仓库元数据与官方 LICENSE 页面一致。E-Moti 的 MIT 工程可保留 Apache/MIT 第三方代码各自授权与声明；不能把 AGPL 主工程复制后统一标成 MIT。OpenViking 当前许可证与某些历史介绍不同，必须以固定版本文件为准。

元数据来源采用 `https://api.github.com/repos/{owner}/{repo}`；核心仓库入口见各节。

## 3. Letta / MemGPT：从“会修改记忆的 Agent”到完整 stateful harness

最新 [letta-ai/letta README](https://github.com/letta-ai/letta/blob/main/README.md) 明确说明旧 V1 API server 已退役，当前源码位于 [letta-code](https://github.com/letta-ai/letta-code)。后者包含 CLI、App Server、渠道与桌面/Web 共用运行时，MemFS 以 Git 记录记忆上下文，支持后台 dreaming 与跨渠道同一身份。Python 安装包捆绑 Node，并非旧 Python API 的自然延续；AgentFile 导入导出已移除。Windows 的自动客户端 reflection 默认禁用，手动仍可运行，说明本地平台开销和进程生命周期不可忽略。

实际读取 `src/agent/memory-constraints.ts` 与相应 audit tests，存在只读路径约束、文件约束验证和写入检查，值得用于“角色核心设定受保护”的设计。E-Moti 不应照搬任意自改 prompt/harness 的产品哲学：表达风格核心可由角色包/用户设置管理，聊天引起的变化只能是有证据、限幅、可回退的互动习惯。

可借鉴：常驻的小型核心身份、按需外部记忆、后台整理、记忆版本可见。暂不复用整包：会同时引入 Node harness、权限系统与另一套存储/代理循环，与现有 PySide6 与 Plugin Runtime 重叠。Git 历史也不天然满足数据抹除；删除当前文件不等于删除全部历史版本。

证据：[当前 README](https://github.com/letta-ai/letta-code/blob/6f4e4886caa0934341eea75c306fc0364509218e/README.md)、[约束代码](https://github.com/letta-ai/letta-code/blob/6f4e4886caa0934341eea75c306fc0364509218e/src/agent/memory-constraints.ts)、[Sleep-time compute 原始论文](https://arxiv.org/abs/2504.13171)。论文的算力收益是特定实验结果，不直接转换为 E-Moti 的响应延迟承诺。

## 4. Mem0：成熟适配面，不等于完整事实生命周期

[Mem0](https://github.com/mem0ai/mem0) 确实有同步/异步 Python、向量库适配、SQLite history、批量嵌入、混合检索、实体索引与可选 reranker。必须纠正旧印象：当前 `mem0/memory/main.py` 使用 V3 单次 ADD-only 抽取，源码先获取相关旧条目和最近十条消息，再抽取增量记忆；不是过去广为传播的 ADD/UPDATE/DELETE/NOOP 自动变更流程。[2026-04-14 v2.0.0 changelog](https://docs.mem0.ai/changelog/sdk) 与 [V3 API](https://docs.mem0.ai/api-reference/memory/add-memories) 都明确了变化。

源代码审查发现三个需要自己处理的边界：

- `add(timestamp=...)`、`search(reference_date=...)` 在 OSS 中会抛出 Platform-only 错误，不能把云端 temporal 功能直接算到 OSS。
- 显式 `_delete_memory` 删除向量后仍将 `old_memory` 写进 SQLite history；并未在该路径清除最近消息窗口。因此“不可被主检索命中”与“本地不再保存该内容”不同，后续抽取从窗口重读也应独立测试。
- 实体索引清理是非致命路径，源码注释明确 helper 会吞掉错误；多存储一致性需要外围保障。

可直接研究 `mem0/utils/scoring.py` 的语义/BM25/实体加分与 explain 字段，但英语词形还原和预设归一化参数不能直接当中文最优值。第一批更适合保留 E-Moti 的有效性判定，只增加可选检索排序，不同时保留两套长期事实真源。

证据：[主流水线](https://github.com/mem0ai/mem0/blob/2c81af3bbe27d9bccb09c772d583df9e9be72ee5/mem0/memory/main.py)、[history 存储](https://github.com/mem0ai/mem0/blob/2c81af3bbe27d9bccb09c772d583df9e9be72ee5/mem0/memory/storage.py)、[排序实现](https://github.com/mem0ai/mem0/blob/2c81af3bbe27d9bccb09c772d583df9e9be72ee5/mem0/utils/scoring.py)。这些结论为源码审查，没有部署 Mem0 复现。

## 5. Graphiti / Zep：时间图与来源有价值，摘要删除仍需失效闸门

[Graphiti](https://github.com/getzep/graphiti) 是可自行集成的 Python 时间知识图框架；Zep 是商业托管/企业上下文产品，不能混为相同交付。`EntityEdge` 的 `episodes` 保存来源，`valid_at`/`invalid_at` 表示事实在世界中的有效期，`created_at`/`expired_at` 对应记录处理信息。此模式比“新记录覆盖旧字符串”更适合回答“你当时喜欢什么”与“你现在喜欢什么”。

当前 `remove_episode` 已遍历来源列表：只移除一个 episode 的支撑，仍有其他来源的边保留；并从剩余 episode 重建存活实体的摘要。**但摘要重建异常时恢复旧摘要，只写日志。** 因此 E-Moti 必须将受影响派生物先标记不可用，再重建；不能把清洗旧内容的职责交给一次可能失败的 LLM 调用。

社区 [#2034](https://github.com/getzep/graphiti/issues/2034) 报告旧版本的多来源误删、摘要残留与已删除来源造成的失效关系残留；核验时 issue 已关闭，不能继续把所有旧问题说成主分支未修。当前源码已修部分内容，而异常保留旧摘要仍可见；是否撤销先前事实失效还需要明确定义产品语义。删除“我以前住上海”的来源与撤销“我已搬到广州”的更正并不必然意味着旧住所应自动复活。

实际复用：从 [固定 SHA 的 `search_utils.py::rrf`](https://github.com/getzep/graphiti/blob/5c27edfa8d3e0f49b2571bcebb4261bcc89ee037/graphiti_core/search/search_utils.py#L1786-L1802) 复制适配纯 Python 排序融合，见末节。图后端与实体抽取暂缓，因为会增加数据库、embedding、LLM 抽取、迁移与失效传播成本。

证据：[时间边定义](https://github.com/getzep/graphiti/blob/5c27edfa8d3e0f49b2571bcebb4261bcc89ee037/graphiti_core/edges.py)、[`remove_episode`](https://github.com/getzep/graphiti/blob/5c27edfa8d3e0f49b2571bcebb4261bcc89ee037/graphiti_core/graphiti.py)、[原始论文](https://arxiv.org/abs/2501.13956)。

## 6. Hindsight：本批最值得学习的派生记忆处理

[Hindsight](https://github.com/vectorize-io/hindsight) 有真实 retain/recall/reflect 流水线、隔离的 bank、Postgres/pgvector、实体/时间/词法/向量召回与归纳层。[原始论文](https://arxiv.org/abs/2512.12818) 区分世界事实、亲历经验、归纳观察与信念，适合提醒 E-Moti 将“实际发生”与“角色对事件的理解”分开。其 benchmark 为作者指定数据、模型与 grader 下的结果，不能充当对中文桌宠的独立质量证明。

最有价值的代码是 `engine/memories/pg/writes.py::delete_stale_observations`：任何来源事实被删除，该观察整体失效，而非只删 source ID 后保留旧自然语言；剩余共同来源重新排队巩固。该函数要求处于同一事务，记录依赖并按顺序锁行，同时清理 observation_history。`test_memory_curation.py`、`test_delta_retain_orphan_observations.py` 包含编辑、失效、恢复、未改变部分保留、增量重摄取后的孤儿观察回归测试。

不过 [#5937](https://github.com/vectorize-io/hindsight/issues/5937) 在核验时仍 open：部分来源消失的旧观察可能仍被召回，导出还会静默丢掉这些孤儿观察。代码有正确的清理函数，不代表所有历史数据与所有删除入口都覆盖。另 [#6059](https://github.com/vectorize-io/hindsight/issues/6059) 报告“工作项已关闭，但全量知识页刷新仍写未关闭”：旧观察持续有效，宽泛检索未取到后来的关闭事实。报告者也明确最小 synthetic 复现未能稳定重现，需保持该证据等级。

对 E-Moti 的取舍：借鉴依赖生命周期和测试案例；不引入整个服务。可用同一存档内的来源 ID/版本与失效状态实现相同不变量，减少 Windows 部署负担。[#6065](https://github.com/vectorize-io/hindsight/issues/6065) 还报告 Windows zh-CN embedded Postgres 启动问题，属于用户报告，未在本机验证。

代码：[失效传播](https://github.com/vectorize-io/hindsight/blob/fa359876bcf5ed652c001dac5d40bfcc51d1d41d/hindsight-api-slim/hindsight_api/engine/memories/pg/writes.py)、[生命周期测试](https://github.com/vectorize-io/hindsight/blob/fa359876bcf5ed652c001dac5d40bfcc51d1d41d/hindsight-api-slim/tests/test_memory_curation.py)、[增量更新孤儿测试](https://github.com/vectorize-io/hindsight/blob/fa359876bcf5ed652c001dac5d40bfcc51d1d41d/hindsight-api-slim/tests/test_delta_retain_orphan_observations.py)。

## 7. MemOS：功能面广，需要区分 Python 核心与本地插件

[MemOS](https://github.com/MemTensor/MemOS) 的开源 Python 核心有可配置记忆类型、MemCube、文本/偏好/工具/技能检索与编辑删除接口；当前仓库还有 TS 本地插件，部署形态不完全相同。实际 [MemoryHandler](https://github.com/MemTensor/MemOS/blob/adcb9f270c982f2b9ff8db9714792829d3bd6ab8/src/memos/api/handlers/memory_handler.py) 中也存在“Activity/Parameter retrieval not implemented yet”分支，不能把抽象类型存在解释为所有后端能力已打通。

[删除文档](https://github.com/MemTensor/MemOS/blob/adcb9f270c982f2b9ff8db9714792829d3bd6ab8/docs/en/open_source/open_source_api/core/delete_memory.md) 描述 memory/file/filter 及 cube 隔离、向量与图同步清理；实际 [handler 单测](https://github.com/MemTensor/MemOS/blob/adcb9f270c982f2b9ff8db9714792829d3bd6ab8/tests/api/test_memory_handler_delete.py) 覆盖过滤约束、空过滤拒绝、多删除模式拒绝与禁用偏好模块，但使用 Mock，只证明分派，不证明跨数据库事务和模型画像已真正失效。不能直接把文档中“atomic”当成已经验证的分布式原子性。

可借鉴：单一管理 API、显式用户/会话过滤、分能力启用、查看记忆的界面。暂缓：整套框架的后端/依赖/调度与存档转换。[本地插件](https://github.com/MemTensor/MemOS/blob/adcb9f270c982f2b9ff8db9714792829d3bd6ab8/apps/memos-local-plugin/README.md) 的 SQLite 与 Viewer 值得后续单独评估，但不是直接可 import 到 Python 的同一模块。

## 8. EverOS：用户可见真源与派生索引，删除契约尚不完整

[EverOS](https://github.com/EverMind-AI/EverOS) 是 EverMemOS 当前主仓，Python 3.12+、Markdown 持久化、SQLite 队列与 LanceDB 派生索引。Tier 1 只配 LLM 可做抽取/写入/关键词召回；混合搜索、反思/技能等需要额外 embedding/rerank。`memory/cascade/orchestrator.py` 及 handlers 真实实现 Markdown→索引的同步、重建与删除处理，适合学习“索引可以重建，真源只有一份”。

然而官方 [MCP 文档](https://github.com/EverMind-AI/EverOS/blob/5b0979b1b7f3a0cbe235756ff098515ec490753e/docs/mcp.md) 明确 self-hosted `forget_session` 不可用。[#483](https://github.com/EverMind-AI/EverOS/issues/483) 仍 open，讨论会话删除究竟影响哪些 episode、facts、profile、case、skill；MCP 文档里画像和技能可存活，因此不符合 E-Moti 所需的严格派生失效。其 `cascade` 是文件到索引的同步机制，不能自动等同于来源到所有语义派生内容的撤回。

适用性：可以借鉴 memcell/episode 形成阶段回忆、可查看的来源和可重建索引；首批不将用户现有 JSON/角色记忆搬成新的 Markdown+多库系统。仓库演示中的部分场景标注 Coming soon，不计入已交付能力。

代码：[cascade orchestrator](https://github.com/EverMind-AI/EverOS/blob/5b0979b1b7f3a0cbe235756ff098515ec490753e/src/everos/memory/cascade/orchestrator.py)、[画像索引 handler](https://github.com/EverMind-AI/EverOS/blob/5b0979b1b7f3a0cbe235756ff098515ec490753e/src/everos/memory/cascade/handlers/user_profile.py)。

## 9. OpenViking 与 Honcho：新增候选的明确取舍

### OpenViking

[OpenViking](https://github.com/volcengine/OpenViking) 将记忆、资源和技能组织为可浏览上下文层次；`experience_lineage.py` 从工具读操作收集来源 URI，`memory_lifecycle.py` 有访问频率与时间衰减热度。热度只决定优先级，不等于事实有效性；读过某条经验也不等于它是后续结论唯一来源。[能力文档](https://docs.openviking.ai/en/agent-integrations/16-capability-reference) 明示 forget 是删除指定 URI，默认非递归，并不检查 URI 是记忆、资源还是技能。由此不能推出“删除一个事实自动消除所有下游概括”。

当前主工程 AGPL-3.0，不复制进 MIT E-Moti。分层上下文、观测轨迹和引用格式可作架构参考；如果将来独立外部服务集成，应单独核验服务与分发义务，不以插件名义回避许可。

### Honcho

[Honcho](https://github.com/plastic-labs/honcho) 的 peer-based 用户建模与观察视角值得研究：不同角色只根据自己见过的交互形成表示，能避免角色全知。实际 [representation 文档](https://github.com/plastic-labs/honcho/blob/39a53549cb269607dd63fe6a4fc90944efb774dc/docs/v3/documentation/core-concepts/representation.mdx) 包括 conclusions、session summaries、peer cards，以及 observe_me/observe_others。其从行为推断人格的功能应在 E-Moti 中标为“推断”，不得自动当用户明确事实或角色固有设定。

[删除文档](https://github.com/plastic-labs/honcho/blob/39a53549cb269607dd63fe6a4fc90944efb774dc/docs/v3/documentation/features/advanced/deleting-data.mdx) 直接说明：session 删除只在后台清理本会话数据；跨会话 derived conclusions 留在 workspace，继续出现在 representation；单条消息和 peer 不能直接删除；202 不代表完成且没有完成状态接口。该语义不适合作为本批严格遗忘的默认后端。主仓 AGPL-3.0，因此仅借鉴产品概念与评价设计。

## 10. 对 E-Moti 的落地建议与可验证不变量

1. **单一权威存档**：原始事实、经历与状态存现有体系；向量、摘要、画像只做带来源版本的派生视图。
2. **四种状态分清**：纠正是旧版被替代；过期是当前不可引用；遗忘是后续读取禁止；物理删除是内容从存储、日志和备份中的清除范围。不能用一个 deleted 布尔值含糊涵盖所有语义。
3. **读路径也校验**：除了写时传播，context builder、检索、章节、画像和缓存读取时都检查 source/version/status；旧档缺来源时保守禁用不可证明有效的派生文本。
4. **异步任务防复活**：提取/摘要任务携带 scope 与 memory generation；提交前核对 generation，用户删除期间开始的旧任务不能把旧输出写回。
5. **事实与人格分离**：删去喝奶茶的偏好，不应把角色“好奇、会轻吐槽”的固有设定一起删除；角色从事实派生的个别互动习惯应撤回，核心角色设定保留。
6. **外部状态以接口真源为准**：Relay 任务状态、游戏世界状态可有 TTL/observed_at，不能靠语义召回决定任务是否完成；只有确认发生的共同事件才有资格进入 episode。
7. **融合前过滤**：RRF/embedding 是排序机制；状态、角色、场景、来源等资格检查优先于排名。相似但已过时的信息应拿不到候选资格。

这些是由源码问题推导的工程建议，未宣称外部项目均已采用或 E-Moti 已全部实现。

## 11. Benchmark 设计补充

[LongMemEval](https://github.com/xiaowu0162/LongMemEval) 提供提取、多会话、知识更新、时间推理与拒答五类长期记忆任务；[LongMemEval-V2](https://github.com/xiaowu0162/LongMemEval-V2) 当前已存在，扩展到多模态 Web/enterprise 轨迹与动态状态/工作流、同时关注 QA 和查询时延。V2 的大量轨迹适合未来外部 Agent 工作上下文评估，首批无需把整个规模搬到桌宠项目。

E-Moti 本批应优先自建确定性契约数据，再叠加真实模型：

- 同一事实多次纠正，确认最新版本命中、旧版在所有派生块不出现。
- 一个章节引用两个来源，只删其中一个，整个旧章节禁用，再由另一来源重建。
- 在提取/巩固/缓存生成过程中删除来源，拒绝旧任务输出。
- 切换角色、游戏/工作/休息场景、重启读旧存档，确认命名空间和时效。
- 用户只表达愿望/假设/角色台词，不生成既成共同经历。
- 事实删除前后角色核心配置哈希相同；模型说话风格再由盲评/成对比较判断。

最少三组对照：原代码基线、生命周期修复后的词法检索、同一资格过滤加可选混合检索。固定数据、seed、模型与 prompt 版本；报告每类分母、召回/误召回、旧事实引用、遗忘泄露、成本和 P50/P95。无模型运行只能证明上下文选择与状态契约，不能把结果写成模型幻觉率或人格一致性已达标。中文断言可同时使用 forbidden fact IDs、来源 lineage 与输出文本检查；仅搜索旧词不足以检测改写泄露。

## 12. 本次实际代码复用交付

本批实际复用范围：

- `src/guanghe_companion/memory_fusion.py`：复制适配 Graphiti `rrf`，默认 `rank_constant=60`，1-based 排名，每路去重，稳定同分，输出 ID/score 对；不引入新库。
- `tests/test_memory_fusion.py`：9 个参数化后的测试，覆盖空列表、融合共同命中、重复、不稳定同分风险和非法常数。
- `third_party/graphiti/LICENSE`：完整 Apache-2.0；`README.md`：中文出处、固定 commit、代码行、差异与使用边界；确认该版本无 NOTICE。

实际验证：实现前 `python -m pytest tests/test_memory_fusion.py -q` 因模块不存在产生预期 `ModuleNotFoundError`；实现后运行 **9 passed in 0.04s**；`git diff --check` 通过。当前已接入 `emotional_memory_retrieval.py`：使用原有词法评分，并通过可选语义检索回调补充第二路排名；没有模型时保留独立本地运行能力。此处只报告 RRF 模块的独立验证，全量集成与 Memory Benchmark 以本目录对应结果为准。

## 13. 官方入口与证据复核

- Letta 现行迁移： https://github.com/letta-ai/letta
- Letta Code： https://github.com/letta-ai/letta-code
- Mem0 V3 更新： https://docs.mem0.ai/changelog/sdk
- Graphiti 源码与删除问题： https://github.com/getzep/graphiti ， https://github.com/getzep/graphiti/issues/2034
- Hindsight 来源失效遗留： https://github.com/vectorize-io/hindsight/issues/5937
- Hindsight 旧工作状态重现： https://github.com/vectorize-io/hindsight/issues/6059
- EverOS self-hosted 遗忘缺口： https://github.com/EverMind-AI/EverOS/blob/5b0979b1b7f3a0cbe235756ff098515ec490753e/docs/mcp.md
- Honcho 删除语义： https://github.com/plastic-labs/honcho/blob/39a53549cb269607dd63fe6a4fc90944efb774dc/docs/v3/documentation/features/advanced/deleting-data.mdx
- 新版评测： https://github.com/xiaowu0162/LongMemEval-V2


### 固定源码版本

下列提交是本次读取代码时记录的版本，不能理解为承诺这些仓库此后不再变化。推送时间来自 GitHub API，不等同于该提交的作者时间。旧 Letta 仓库只核验了迁移 README 与实时元数据，未记录对应代码提交，因此不补造 SHA。

| 仓库 | 已读取提交 | 证据范围 |
|---|---|---|
| [letta-ai/letta-code](https://github.com/letta-ai/letta-code) | [`6f4e4886caa0`](https://github.com/letta-ai/letta-code/tree/6f4e4886caa0934341eea75c306fc0364509218e) | 主分支源码、许可证、相关测试/文档静态审查 |
| [mem0ai/mem0](https://github.com/mem0ai/mem0) | [`2c81af3bbe27`](https://github.com/mem0ai/mem0/tree/2c81af3bbe27d9bccb09c772d583df9e9be72ee5) | 主分支源码、许可证、相关测试/文档静态审查 |
| [getzep/graphiti](https://github.com/getzep/graphiti) | [`5c27edfa8d3e`](https://github.com/getzep/graphiti/tree/5c27edfa8d3e0f49b2571bcebb4261bcc89ee037) | 主分支源码、许可证、相关测试/文档静态审查 |
| [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) | [`fa359876bcf5`](https://github.com/vectorize-io/hindsight/tree/fa359876bcf5ed652c001dac5d40bfcc51d1d41d) | 主分支源码、许可证、相关测试/文档静态审查 |
| [MemTensor/MemOS](https://github.com/MemTensor/MemOS) | [`adcb9f270c98`](https://github.com/MemTensor/MemOS/tree/adcb9f270c982f2b9ff8db9714792829d3bd6ab8) | 主分支源码、许可证、相关测试/文档静态审查 |
| [EverMind-AI/EverOS](https://github.com/EverMind-AI/EverOS) | [`5b0979b1b7f3`](https://github.com/EverMind-AI/EverOS/tree/5b0979b1b7f3a0cbe235756ff098515ec490753e) | 主分支源码、许可证、相关测试/文档静态审查 |
| [volcengine/OpenViking](https://github.com/volcengine/OpenViking) | [`4ab22a492345`](https://github.com/volcengine/OpenViking/tree/4ab22a4923452362b60aef2826c2083ce36168d2) | 主分支源码、许可证、相关测试/文档静态审查 |
| [plastic-labs/honcho](https://github.com/plastic-labs/honcho) | [`39a53549cb26`](https://github.com/plastic-labs/honcho/tree/39a53549cb269607dd63fe6a4fc90944efb774dc) | 主分支源码、许可证、相关测试/文档静态审查 |

外部 issue 的 open/closed 状态与文档能力陈述均以 2026-10-25 核验时为准。用户报告代表待调查证据；本文明确标出的源码路径才是代码行为依据，未将 issue 的全部推测当作已证实缺陷。除 RRF 外，本批没有复制这些框架源码或新增其服务依赖。
