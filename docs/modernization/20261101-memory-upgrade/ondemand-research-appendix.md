# 按需 RAG：本轮官方源码复核与复用取舍

核查日期：2026-11-01。本文补充已有 [memory-research.md](../memory-research.md)，不替代其研究范围和现有第三方声明。已读取官方文档、GitHub 最新主分支代码和实际 LICENSE；未部署这些外部服务，不能把作者的跑分当成 E-Moti 实测。

## 1. 结论与实施边界

本轮采用现有 SQLite 权威文档，加同库可重建结构化/词法投影、可重建 BGE 向量和来源化概览。没有增加独立事实真源、图数据库、Node Agent 循环或远程记忆服务。成熟实现的复用分为三种：使用 SQLite/FastEmbed 等现有依赖；保留已经引入并声明来源的 Graphiti RRF；参考外部系统的生命周期和检索机制，但不复制与许可证或架构不适配的整套代码。

| 项目 | 本轮读取的主分支 SHA | 实际许可 | 具体借鉴 | 本轮不集成的原因 |
| --- | --- | --- | --- | --- |
| OpenViking | `de6a440390f169be83e29b62d26b647eadd86a53` | AGPL-3.0 | 概览后读原文、意图阶段可以产生零查询 | 仓库规则不允许把 AGPL 主工程源码复制到 MIT 工程；目录式上下文和服务栈与现有桌面记忆不等价 |
| Graphiti | `16bf514380de4e44884aed6779bece220e6fe470` | Apache-2.0 | 有效时间/记录时间分离、多来源关系、已有 RRF | 图后端和抽取服务的运维、迁移、失效路径成本；现有规模尚无证明必须引入图数据库的结果 |
| Hindsight | `bc5ea195a0fed1346ff171a5780bbb72a38c89c8` | MIT | 派生观察整体撤回、剩余来源重新巩固、部分证据与充分证据区分 | Postgres/pgvector 与完整 retain/recall/reflect 服务不是可直接替换的本地 SQLite 模块 |
| Letta Code | `ebd590b11bef049884b923da5ed3f5d087af81e0` | Apache-2.0 | 受保护人格核心、可检查记忆、受预算后台维护 | 当前主要为 TypeScript harness，替换会重叠运行时、工具和存储；Git 历史不等于遗忘后的物理抹除 |

许可证证据：[OpenViking LICENSE](https://github.com/volcengine/OpenViking/blob/de6a440390f169be83e29b62d26b647eadd86a53/LICENSE)、[Graphiti LICENSE](https://github.com/getzep/graphiti/blob/16bf514380de4e44884aed6779bece220e6fe470/LICENSE)、[Hindsight LICENSE](https://github.com/vectorize-io/hindsight/blob/bc5ea195a0fed1346ff171a5780bbb72a38c89c8/LICENSE)、[Letta Code LICENSE](https://github.com/letta-ai/letta-code/blob/ebd590b11bef049884b923da5ed3f5d087af81e0/LICENSE)。这些是本次版本，不用于推定其他版本或附属资产的授权。

## 2. SQLite FTS5：为什么先做中文预分词而非直接换算法

[SQLite 官方 FTS5 文档](https://www.sqlite.org/fts5.html) 的关键边界如下：

- 默认 `unicode61` 将连续的 Unicode 字母/数字视为一个词，不能自动把连续中文句子按词切开。
- 内置 `trigram` 支持连续三字符子串；少于三个 Unicode 字符的 MATCH 查询不会命中。这对两字人名、字段和单字偏好尤其重要。
- FTS5 `bm25()` 的排序方向是更小的值对应更好的匹配。分数是相对排序量，不能解释为事实真实性概率。
- 外部内容表不会自动维护索引一致性；插入、更新、删除和重建的责任必须落实到事务和测试，不能只创建一张虚表。

在本环境 SQLite 3.53.1 的独立内存数据库中做过一个小探针：连续句子中搜索两字人名与“牙医”，原始 `unicode61` 和内置 trigram 都未命中，预分词 bigram 命中；只有 bigram 仍漏单字“茶”。同一探针里“我喜欢喝什么”会命中多个饮品偏好，说明改善词法候选并未解决主体、字段或时间正确性。这只是机制验证，不是中文检索准确率跑分。

本项目因此采用应用层中文 unigram/bigram 与 ASCII 词预处理，生成安全索引 token，再交给 SQLite FTS5/BM25。单字、短实体名和结构化字段有自己的查询契约。FTS5 不可用时显式报告扫描回退；候选资格、相关性和充分性仍在其后独立判断。是否优于既有词法排序以本轮同语料对照为准。

## 3. OpenViking：真正可借鉴的分层访问

当前官方 [Context Layers](https://docs.openviking.ai/en/concepts/03-context-layers) 中，L0 和 L1 是目录级 `.abstract.md`、`.overview.md`；普通文件并非每个都复制三份。默认生成正文预算分别为 256 和 4000 字符，且不是存储硬上限。L2 是按需读取的原始文件或解析后的正文。

当前 [Retrieval Mechanism](https://docs.openviking.ai/en/concepts/07-retrieval) 明确实际路径为可选意图分析、全局向量搜索、可选重排。`find` 直接查；带会话的 `search` 可调用模型规划零到多个查询。每条子查询的 limit 不等于全局总预算，合并结果也没有承诺跨查询自动去重。不能根据“文件系统”和“层次”术语，把它描述成已经证明优于其他检索的递归树搜索。

E-Moti 借鉴的是先判断证据需要、先概览后展开、零查询合法、跨意图总预算和去重。具体实现保留一份权威事实；L1 使用可验证的来源摘录，来源变更后重建。首批没有把自由生成的自然语言摘要当新的事实。

## 4. Graphiti：时间与来源值得保留，删除异常必须关闭旧摘要

实际 [EntityEdge](https://github.com/getzep/graphiti/blob/16bf514380de4e44884aed6779bece220e6fe470/graphiti_core/edges.py) 保存来源 episode 列表、`valid_at`、`invalid_at`、`expired_at` 和 reference time。计划在何时被提出，与计划何时可能执行，是不同时间概念。

当前 [`remove_episode`](https://github.com/getzep/graphiti/blob/16bf514380de4e44884aed6779bece220e6fe470/graphiti_core/graphiti.py) 会保留其他 episode 仍支持的边，并重建存活实体摘要。不过摘要重建异常时会恢复 `old_summary` 并记录日志。对需要严格遗忘的 E-Moti，失败后继续提供旧摘要不可接受；受影响派生物应先失效，成功验证后再恢复可见性。

已有 RRF 复用继续沿用原固定来源和第三方声明。本次没有为了名称先进而接入整个图后端。

## 5. Hindsight：来源撤回与证据充分性必须分开

实际 [`delete_stale_observations`](https://github.com/vectorize-io/hindsight/blob/bc5ea195a0fed1346ff171a5780bbb72a38c89c8/hindsight-api-slim/hindsight_api/engine/memories/pg/writes.py) 在源记忆删除前的活动事务内，移除任何引用这些来源的观察及其历史，把仍存活的共同来源重新排队巩固。不能仅从摘要的 source ID 列表移掉一项，却保留仍含该事实的旧正文。

实际 [`evidence_is_sufficient`](https://github.com/vectorize-io/hindsight/blob/bc5ea195a0fed1346ff171a5780bbb72a38c89c8/hindsight-api-slim/hindsight_api/engine/cross_encoder.py) 区分无支持、部分回答、充分回答。其最新 [修复提交](https://github.com/vectorize-io/hindsight/commit/bc5ea195a0fed1346ff171a5780bbb72a38c89c8) 处理判定服务遇到 429 后静默退化的问题。提交中的 LoComo 比例是维护者该次运行的报告，未在此复现。

本轮采用这一机制启示：资格合法、与主题有关、有能力回答所问属性，是三个不同判断；未知不是工具异常；部分证据不应升级为完整答案；扩展有次数和成本边界。首批确定性规则不会因此被包装成通用语义蕴含模型，其覆盖与失败由本地开发集及独立留出集揭示。

## 6. Letta：稳定人格与可变事实分权

当前 [letta-ai/letta README](https://github.com/letta-ai/letta/blob/main/README.md) 已将历史 V1 API server 指向 archive，活跃实现为 Letta Code。实际 [memory-constraints.ts](https://github.com/letta-ai/letta-code/blob/ebd590b11bef049884b923da5ed3f5d087af81e0/src/agent/memory-constraints.ts) 包含只读路径、文件预算与 staged tree 验证约束。

E-Moti 继续由 Character Pack/PersonaProfile 提供核心人格，用户事实通过来源化生命周期改变，情绪仅影响表达。检索拒绝某条事实不应把人格“拒答化”；关系演进只能依据真实共同经历。配置 hash 不变和 persona prompt 正确交付，只能证明配置与请求层稳定。真实人格行为仍要用独立模型回答、盲评与长期使用结果验证。

## 7. 下一阶段依赖判断

| 备选 | 当前决定 | 何时重新评估 |
| --- | --- | --- |
| 独立图数据库 | 暂缓 | 有足够实体关系、多跳难例，结构化 SQL/来源展开无法满足且能证明收益 |
| HNSW/独立向量引擎 | 暂缓 | 真实规模、内存与热查询测量证明精确搜索成为瓶颈 |
| LLM 路由/充分性判定 | 保留接口设计，未作为每句前置条件 | 规则的未见表达错误显著，且校准集证明质量收益大于新增延迟与成本 |
| 自动自由文本章节摘要 | 不作为默认权威 | 有逐主张来源、蕴含验证、撤回失效与后台预算，真实模型评测通过 |
| 全量外部记忆服务迁移 | 不采用 | 独立部署需求明确，存档迁移和生命周期一致性可证明，并能减少而非增加维护总成本 |

最终可复用性不由功能名或宣传跑分决定。需要实际代码、当前授权、完整数据生命周期、适合 Windows/Python 的运行方式，以及同数据/同预算下的对照证据。
