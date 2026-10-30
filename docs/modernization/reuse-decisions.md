# 开源复用与架构取舍记录

核验时间：2026-10-25。许可证必须以被复用版本的实际文件为准；未把网页介绍或旧印象当授权依据。完整源代码、社区反馈与维护状态见 [记忆研究](memory-research.md)、[伙伴研究](companion-research.md)。

## 已实际复用

| 来源 | 固定版本/对象 | 本地位置 | 变化与授权处理 | 代价与验证 |
|---|---|---|---|---|
| Graphiti | `5c27edfa8d3e0f49b2571bcebb4261bcc89ee037` 的 `search_utils.py::rrf` | `src/guanghe_companion/memory_fusion.py` | 保留 Apache-2.0、版权说明、完整 LICENSE；记录输入校验、去重、稳定排序适配；固定版本无独立 NOTICE | 无新运行依赖；单元测试＋实际 retrieval 集成；不等于引入整个 Graphiti |

详见 [第三方说明](../../third_party/graphiti/README.md)。相关代码继续按其 Apache-2.0 许可发布，不把它重新宣称为 E-Moti 的原创 MIT 代码。

## 采用机制、暂不引入整套运行时

| 项目/机制 | 借鉴价值 | 本批取舍及理由 |
|---|---|---|
| Graphiti 双时间、episode 来源 | 明确事实何时成立、系统何时记录；混合排序 | 本批加入有效期和版本，使用既有 occurred/updated；没有声称实现完整时间图和历史 as-of 查询 |
| Hindsight 来源驱动的观察失效 | 先撤销无效归纳，再基于剩余证据重建 | 在既有文档中实现指纹依赖；不接 Postgres/服务进程，避免 Windows 用户部署负担 |
| Letta 当前记忆约束和小型身份上下文 | 保护核心身份、显式可管理的记忆 | 只读人格和受控写入口；不接入新 TypeScript harness 或旧退役 Python server |
| Mem0 抽取、解释性排序、适配器 | 下一阶段可评估提取与检索组件 | V3 ADD-only 与显式 update/delete 分开理解；暂不引入第二套向量库/history 真源 |
| OpenClaw 来源/tombstone/发布版本检查 | 防止后台旧任务回写已撤回事实 | 用本地 epoch 和来源退役约束宿主；不把它的整套工具自主性搬进桌宠 |
| Hermes SOUL 与预算 | 人格与用户记忆分开，控制上下文成本 | 不照搬一整会话冻结的 MEMORY/USER 缓存，因其与即时纠正/遗忘冲突 |
| AIRI 的角色、语音与表现事件 | 多表现端、交互取消、场景边界 | 学习契约，不把 PySide6 重写为 Vue/Electron；WIP 的长期记忆不算现成替代 |
| Open-LLM-VTuber 的听到内容回执 | 用户打断时只保留实际被听见的回复 | 留到语音阶段逐 provider 验收；MIT 主代码、Live2D SDK和模型素材授权分别处理 |
| N.E.K.O. 的 Python 记忆/主动决策 | correction provenance、target epochs、决策与执行拆分 | 借鉴契约与 bad cases，暂不引入多服务情绪/研究执行系统 |
| EverOS 可见真源与可重建索引 | 不把向量库当唯一用户记忆 | 保留 E-Moti 现有角色存档；会话遗忘的未实现边界不作为依赖 |

OpenViking 与 Honcho 在核验版本为 AGPL-3.0；本批只研究架构和公开行为，没有复制其主工程源码。MemOS 功能面广，但类型/文档/Mock 分派测试不能证明所有后端和跨库失效已实现。本批没有为了赶新技术而增加多套同职能记忆库。

## 后续可以复用什么

语义检索优先接入成熟 embedding 库/provider，而不是自训练模型。adapter 应接受当前活动条目，明确模型版本、维度、中文适用性、许可证、缓存 key 和删除传播；embedding 仅是可重建派生物。先在冻结 holdout 上比较 lexical/RRF/embedding/reranker，再决定是否值得默认启用。

语音优先评估现有 provider 与 Open-LLM-VTuber 类似的取消/听到内容契约，不复制 Live2D 资产或整套 UI。任何新第三方代码进入仓库都要记录固定 commit、原文件、LICENSE/NOTICE、改动点及最低验证，不能只在 README 列项目名。
