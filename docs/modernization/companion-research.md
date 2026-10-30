# E-Moti：Personal Agent、Companion、人格与多模态调研

调研日期：2026-10-25。方法：使用 GitHub 连接读取实时仓库元数据、固定提交的源码、官方技术文档和 issue；商业产品仅据官方帮助文档分析可见交互，不推断未公开内部机制。开源代码均为阅读验证，**本调研没有运行这些第三方完整项目，也没有验证真实语音/模型表现**。Issue 是有待独立复现的工程反馈，不能视为所有版本必现。更新时间与近期 push 不是质量证明。

## 1. 本轮最有价值的判断

1. **E-Moti 的重点不应是再接一个聊天壳或平行记忆服务。** AIRI 对角色、多模态、语音事件和外部场景的分离值得借鉴；OpenClaw 对来源继承、失效与删除边界的处理更接近本轮关键问题；新发现的 N.E.K.O. 对 Python 陪伴产品的检索、记忆证据和主动性机制最值得细读。三者都不适合整套搬入 PySide6 应用。
2. **持久化的人格、可纠正的用户事实、角色的当前情绪是三个不同的可变性域。** Hermes 的 SOUL 与临时任务分离提供清晰先例。人格应来自角色配置；对话不能直接覆写配置；用户事实的删除也不能抹掉角色的基本表达方式。
3. **删除应作用于信息的传播链。** 事实、来源消息、章节、画像、召回索引、正在生成的摘要、模型请求快照与跨设备同步都可能存有副本。OpenClaw 已有 source lineage、session tombstone、index revision；N.E.K.O. 的公开 issue 说明仅删当前数据还会被旧异步任务写回。
4. **主动陪伴需要候选、准入、生成、投递和反馈，而不是定时提示词。** 情绪可影响语气、话题和表现，但不应成为“你不理我所以扣关系值”或默认监督工作。工作、游戏是可关闭的能力域。
5. **记忆和语音能力不能独立勾选后假定组合正确。** Open-LLM-VTuber 的默认代理有打断后截断已听回复的代码，但 Letta 代理的 `handle_interrupt()` 为 `pass`，图像也没有实际转发给 Letta。必须测试“模型 × 记忆代理 × 语音输出 × 打断”的真实组合。

## 2. 开源项目核验与复用取舍

### 2.1 项目状态快照

| 项目 | 本轮读取的版本 | 维护证据 | 许可证与适配 | 判断 |
|---|---|---|---|---|
| [AIRI](https://github.com/moeru-ai/airi) | `74ddd90c04deed806eaef1e89a2b7ecaac529ba9` | GitHub `pushed_at=2026-10-25T15:27:54Z`，未归档 | MIT；主要 TypeScript/Vue/Electron，Python 直接移植成本高 | 借鉴角色/场景隔离、后台任务、语音生命周期；不替换现有渲染器与记忆存储 |
| [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) | `992309c0aa19845960228f880013d4685fde93b5` | `pushed_at=2026-05-15T07:18:04Z`，未归档；不能称近期持续维护 | 源码 LICENSE 为 MIT；Live2D 样例另受 LICENSE-Live2D.md 管理；主要 Python | 对 ASR/TTS/LLM 适配和中断语义有参考价值；不要整套换入 |
| [OpenClaw](https://github.com/openclaw/openclaw) | 当日 main 源码；随后读取 head `3f199f0208d0233a14fc3c3d51b89f6ead25c419` | 当日 push，未归档 | MIT，TypeScript/Node、网关/多渠道系统较重 | 借鉴来源、墓碑、修订栅栏；对接为能力插件而不是人格核心 |
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | 当日 main 源码；随后读取 head `1d0dbb87faa08490b26c0ec5313a2d5592ebb8bd` | 当日 push，未归档 | MIT，Python；其代理工具、会话状态、网关有较多耦合 | 借鉴稳定 SOUL、受限记忆预算、按来源过滤；不复制冻结缓存语义 |
| [N.E.K.O.](https://github.com/Project-N-E-K-O/N.E.K.O) | `b4821ecb003dd913a4f592b2296616cd8ea7e870` | `pushed_at=2026-10-25T12:27:39Z`，未归档 | Apache-2.0；Python/FastAPI + 浏览器/Electron | 重点研究窄模块算法和协议；不复制多服务/多 JSON 状态存储 |

数据源为各仓库 `https://api.github.com/repos/{owner}/{repo}` 与 `git/trees/main`/`branches/main`。OpenClaw/Hermes 单个文件是在读取 head 前从 main 读取，**不宣称所有已读文件均固定在表中后取的 head**。实际复用时应按目标文件 blob 固定来源。

E-Moti 当前为 MIT。MIT 代码可保留版权与许可证后复用；Apache-2.0 代码可以作为带原许可证、版权/NOTICE 与修改说明的组件纳入，不能把被复制部分的 Apache 义务简单抹成 MIT。角色模型、声音、素材与训练数据必须另看许可证，仓库根许可证不等于所有资源许可。本报告列举的 AIRI、Open-LLM-VTuber、OpenClaw、Hermes 和 N.E.K.O. 五个项目仅用于架构与实现研究，没有从它们复制代码。整个升级另有 Graphiti 小型排序融合函数的实际复制适配，保留 Apache-2.0 许可证；具体范围见 [Graphiti 来源记录](../../third_party/graphiti/README.md)。不要将研究参考与已发生的代码复用混为一谈。

### 2.2 AIRI：交互与生命周期进展明确，但记忆 CRUD 不等于可靠长期记忆

核验文件：

- [memory.ts](https://github.com/moeru-ai/airi/blob/74ddd90c04deed806eaef1e89a2b7ecaac529ba9/packages/stage-ui/src/stores/memory.ts)
- [2026-10-10 ADR](https://github.com/moeru-ai/airi/blob/74ddd90c04deed806eaef1e89a2b7ecaac529ba9/docs/ai/adr/2026-10-10-skills-automations-and-memory.md)
- [语音中断类型](https://github.com/moeru-ai/airi/blob/74ddd90c04deed806eaef1e89a2b7ecaac529ba9/packages/core-agent/src/voice/interruption.ts)
- [聊天中断协调](https://github.com/moeru-ai/airi/blob/74ddd90c04deed806eaef1e89a2b7ecaac529ba9/packages/stage-layouts/src/composables/use-chat-interruption.ts)

实际记忆结构为 `name/description/body/persona?/updatedAt`，本地存储中按角色归属；模型可读写/遗忘自己角色的条目，只有用户能把条目提升成所有角色可见的 general。每次运行注入索引，按需读正文。这是低成本、可管理的事实笔记，而非有置信度、时效、来源链和派生失效的记忆系统；源码 `write()` 是按名字覆盖，`forget()` 是数组删除，没有在此模块内实现版本或墓碑。

值得借鉴的是后台任务独立会话、结果以带来源 notice 回流而不是伪装成用户说话，以及将“声音已经停下”和“中断通知已持久记录”作为两个完成状态。角色切换时，应明确停止哪个 session/turn 的播放，不能用一个全局 stop 标志误伤其他会话。

ADR 虽标 Accepted，也明确真实模型、Discord、speech 未完成 live checks，并列出 scene prompt 读取所有共享 context 等隐私未完成项。仓库里有测试文件不等于这部分已真机验证。公开 [#2671](https://github.com/moeru-ai/airi/issues/2671) 截至本轮仍 open，报告云同步后删除的聊天消息在角色切换时复活；[#2778](https://github.com/moeru-ai/airi/issues/2778) 报告某 beta 版本 MCP 连接成功但工具没有进入 LLM 请求。两者都适合作为验收情景，不应据此认定当前 head 必现。

**E-Moti 取舍：** 学 index/detail、角色归属、后台结果来源、播放回执协议。继续复用 E-Moti 原有 Character Pack 与渲染器。不要为借用 AIRI 而引入 Electron 和另一套 localStorage 事实库。

### 2.3 Open-LLM-VTuber：适配层可读，组合能力必须逐项验收

核验文件：

- [BasicMemoryAgent](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/blob/992309c0aa19845960228f880013d4685fde93b5/src/open_llm_vtuber/agent/agents/basic_memory_agent.py)
- [LettaAgent](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/blob/992309c0aa19845960228f880013d4685fde93b5/src/open_llm_vtuber/agent/agents/letta_agent.py)
- [官方快速上手](https://open-llm-vtuber.github.io/en/docs/quick-start)
- [LICENSE](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/blob/992309c0aa19845960228f880013d4685fde93b5/LICENSE)

BasicMemoryAgent 的“memory”主要是聊天历史列表，具备工具调用、文本切句、表情动作抽取、TTS 清理和显示处理。`handle_interrupt(heard_response)` 用已听见的内容替换最后一条 assistant 历史，避免模型误以为整段都已说出。LettaAgent 是另一路服务器适配：`handle_interrupt()` 没有实现，`_to_messages()` 的图像分支只构造文本。官方文档亦提示 Letta 会增加交谈延迟。

公开 [长期记忆讨论 #260](https://github.com/orgs/Open-LLM-VTuber/discussions/260) 提及本地模型的速度与工具输出稳定性问题；这只是个体配置反馈，不是可比较性能测试。[#219](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/issues/219) 描述 sherpa-onnx CUDA 安装困难，说明 provider 支持名单不足以证明 Windows 用户能直接运行。

**E-Moti 取舍：** 后续语音轮次管理优先研究其 `conversations/tts_manager.py`、切句 transformers 与 provider 接口；以独立适配器实现，并单独测试中断/超时/晚到音频。不要为了接入 Letta 再建立与 Emotional Memory V2 并列的权威记忆服务。不要复制 Live2D 样例资产。

### 2.4 OpenClaw：记忆治理比“Markdown 记忆”标签更值得研究

核验资料：

- [Memory overview](https://docs.openclaw.ai/concepts/memory)
- [Provenance and deletion](https://docs.openclaw.ai/concepts/memory-provenance)
- [memory-session-tombstones.ts](https://github.com/openclaw/openclaw/blob/main/extensions/memory-core/src/memory-session-tombstones.ts)
- [memory-entry-origins-delete.ts](https://github.com/openclaw/openclaw/blob/main/extensions/memory-core/src/memory-entry-origins-delete.ts)
- [Heartbeat migration](https://docs.openclaw.ai/gateway/heartbeat)

当前文档将 USER、长期摘要、每日观察、dream diary 分开，索引默认仍可用 SQLite；更关键的是，自动吸收的记忆记录来源会话，合并/替代时继承所有父来源。`forget` 按来源定位派生条目，记录 forgotten session，使后台 ingestion 不再从旧 transcript 重建。源码会在事务中记录 session tombstone 并推进 index revision，避免删除前准备的影子索引在删除后发布。

这不是全盘擦除承诺。文档明确不覆盖原始会话全文、任意自由编辑、外部副本；没有 lineage 的旧笔记不能可靠追溯；混合多个来源的条目可能整条移除；失败时可能部分清理。其价值是明确覆盖范围和失效责任，而不是声称“forget 即彻底抹除”。

截至本轮，旧 heartbeat 已迁移为普通 automation job，删除 monitor 后不会因重启再生成，保留一次性 provisioning receipt。E-Moti 无需跟进其整套网关，但可吸收“用户关闭后的状态是持久选择”和“没有新信息就不发送”的产品契约。不能继续照搬早期博客里的 HEARTBEAT.md 定时循环当成最新架构。

**E-Moti 取舍：** 在当前存储增加 lineage、有效状态、修订栅栏与可解释删除报告；不要同时创建 Markdown、向量库和图谱三套权威事实。OpenClaw 可作为外部执行能力，E-Moti 本体负责人格与交互连续性。

### 2.5 Hermes Agent：稳定身份与记忆预算有参考价值，冻结缓存与即时遗忘冲突

核验资料：

- [Personality & SOUL.md](https://hermes-agent.nousresearch.com/docs/user-guide/features/personality)
- [Persistent Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)
- [memory_tool.py](https://github.com/NousResearch/hermes-agent/blob/main/tools/memory_tool.py)
- [session_search_tool.py](https://github.com/NousResearch/hermes-agent/blob/main/tools/session_search_tool.py)
- [memory_manager.py](https://github.com/NousResearch/hermes-agent/blob/main/agent/memory_manager.py)

SOUL 在实例目录加载，定位为跨项目身份，任务约束放其他上下文文件。这很适合 E-Moti 的稳定 Character Pack。官方文档说明内置 MEMORY/USER 有字符预算，满额时拒绝写入并要求整理；源码会按来源过滤 subagent/tool/kanban 会话并降低 cron 结果优先级，以避免自动化噪声压过用户互动。MemoryManager 限制同时注册的外部记忆 provider，避免重复后端与工具列表膨胀。

**不应照搬其冻结 system prompt。** 文档明确为 prefix cache，在 session start 固定 MEMORY/USER 快照，会话内改动只写磁盘，下次会话才重建。对于 E-Moti 的即时遗忘目标，记忆修订后必须停止/丢弃旧上下文的在途生成，并重建后续请求；不能让“已经从记忆管理页删除”与“当前 prompt 仍含旧事实”并存。

### 2.6 N.E.K.O.：高度相关的 Python 同类，但复杂度已远超首批升级所需

核验资料：

- [记忆架构](https://project-neko.online/architecture/memory-system)
- [hybrid_recall.py](https://github.com/Project-N-E-K-O/N.E.K.O/blob/b4821ecb003dd913a4f592b2296616cd8ea7e870/memory/hybrid_recall.py)
- [persona/corrections.py](https://github.com/Project-N-E-K-O/N.E.K.O/blob/b4821ecb003dd913a4f592b2296616cd8ea7e870/memory/persona/corrections.py)
- [主动交互纯决策](https://github.com/Project-N-E-K-O/N.E.K.O/blob/b4821ecb003dd913a4f592b2296616cd8ea7e870/main_logic/proactive_chat/decisions.py)
- [用户情绪](https://github.com/Project-N-E-K-O/N.E.K.O/blob/b4821ecb003dd913a4f592b2296616cd8ea7e870/main_logic/activity/master_emotion.py)

值得学的具体实现：

- 前台落原始消息与 recent，后台抽事实/反思；反思关联 source fact IDs；人物配置生成的条目标记 protected。纠正时保留原有 provenance/version history，并显式使 token/embedding 缓存失效。
- `hybrid_recall.py` 用 BM25 与可选本地 embedding 的排名通过 RRF 融合，前置硬过滤；persona 已在普通上下文，不重复作为检索结果。检索热路径不再加一次 LLM rerank，降低等候。
- 主动候选选择、忙碌/隐私/游戏路由准入、生成、投递提交与成功后记账分离；输出可说明为何静默。
- 用户 valence/arousal 和角色表情分析是两个管道。用户情绪当前只保存最新读数，长期聚合在源码明确为 deferred，不可宣称已实现长期情绪人格发展。

不应整套复制：它目前有独立记忆服务、SQLite 原文、多个 JSON/NDJSON 派生视图、outbox、event reconciliation、身份合并和跨端传播，维护成本高。官方文档还说明记忆浏览器主要编辑 recent，并非所有事实/反思/画像的通用管理界面；自动摘要等处理仍会调用配置的外部模型，“本地优先”不等于全部不出设备。其 anti-slack/工作监督子流程不符合 E-Moti 此次定位，不纳入默认人格。

公开 [#3405](https://github.com/Project-N-E-K-O/N.E.K.O/issues/3405) 给出跨身份清除时持久 `target_epochs` 缺失导致旧写入复活的边界；[#3502](https://github.com/Project-N-E-K-O/N.E.K.O/issues/3502) 讨论后台任务继承已过期 RPC deadline 的回归；[#3430](https://github.com/Project-N-E-K-O/N.E.K.O/issues/3430) 明确 deep research 尚有 adapter/编排/真实接线未完成，不能把路线图当已上线功能。均在本轮查询时 open。

## 3. 商业产品：可以借鉴的可见体验

| 产品 | 公开、可核验交互 | 适合 E-Moti 的部分 | 不应推断的能力 |
|---|---|---|---|
| [Kindroid](https://kindroid.ai/v2/docs/memory/) | 帮助页 2026-10-13 更新，区分 backstory/key memories、chat、cascaded、long-term、journals；[人格设置](https://kindroid.ai/v2/docs/customizing-personality/) 可调表达与设定 | 稳定角色设定独立于用户事实；关键回忆与按需记忆不同优先级；让用户可编辑 | “infinite memory”是产品描述，不证明召回完整或删除无派生泄露 |
| [Character.AI](https://blog.character.ai/memory/) | 2026-05-21 公布 Story Memory、可编辑 Facts、按 Persona/Character/side character 分页、memory usage；新会话可选择复制 Facts | 明确实体归属、用户锁定关键事件、记忆预算可视化；新场景默认是否继承由用户决定 | 虚构剧情 Facts 不等于现实用户事实；公布 rollout 不证明所有账号当前相同 |
| [Replika](https://help.replika.com/hc/en-us/articles/37208679176077-How-does-Replika-s-memory-work) | Memory tab 可手动加记忆，官方说明还存在由对话模式形成的更深层记忆 | 低负担管理页，记忆来源和纠正动作应易找到 | 可见记忆删除不代表后台画像和历史完全删除，公开文档不足以验证 |
| [Nomi](https://nomi.ai/updates/september-9th-update-proactive-messages/) | 官方 2024-09-09 功能页仍可访问，主动消息可按 Nomi 启停，当前页面列四档频率 | 角色级开关、低频模式、表达方式独立配置 | “它在想什么/做什么”是拟人化文案，不证明后台真实活动或自主认知 |

商业样本在此承担交互设计证据，不承担算法效果证据。没有创建付费账户、实际对话测试或内部代码审计，因此不能排名“谁最像真人”或“谁的长期记忆最好”。

## 4. 建议的 E-Moti 人格与交互边界

### 4.1 稳定人格是只读配置输入

保留 `character.json`、`dialogue_style.json` 与 `CharacterPerformanceProfile`。本轮已在 [persona.py](../../src/guanghe_companion/persona.py) 实现可选只读 `persona.json`：表达风格、偏好、互动习惯、幽默/吐槽边界；缺失时由已有角色 name/title/description/style 导出，不会把所有老角色强改成同一种“聪明吐槽型”。输入带配置 hash/version，用于追踪配置变更。不要把 memory record、当前心情或用户临时一句“你变成另一个人”保存为角色配置。

未来成长先走 proposal：共同经历提出小幅改变建议 → 显示证据与前后差异 → 用户接受 → 新版本。本轮只实现稳定配置边界与自动化回归，没有实现自动修改人格；配置 hash 稳定也不等于真实模型的人格行为已通过盲评。

### 4.2 外部状态只作为短时证据

Relay、游戏 Agent、Body 返回事件/观察信封：`source_system, event_id, subject/character, scene, observed_at, expires_at, revision, provenance, payload`。来源系统保有权威状态；E-Moti 缓存只为当前交互；过期或断线应显示“上次观察”，不能装成实时事实。屏幕 OCR/游戏对话/小说文本都不是用户自述，不得自动写入现实用户画像。

值得长期保留的是用户认可的共同经历：“我和你一起打过这场游戏”需要真实回合/游戏事件证据；模型说“我昨晚替你看完论文”没有任务运行与产物证明，不能入库。人格可共用，场景事实不默认共用。关闭全部外部插件仍保留聊天、表情、静默陪伴、个人事实管理。

### 4.3 主动性成为可解释的决策

候选可以来自用户之前提过的话题、可证实共同事件、用户主动允许的日程、低频闲聊。代码先做安静时段、会话忙碌、冷却、频率配额、近期忽略次数、场景与传感器权限过滤。模型负责在剩余候选里选择自然表达或选择不说。

生成结束后再查一次状态：用户已经切角色、关闭插件、进入安静模式、纠正记忆时，旧候选不能仍然弹出。只有成功投递才记“已主动说过”，被取消不消耗关系事件。忽略后退避，不降低亲密度，不指责用户离开。工作任务不应占据所有主动候选。

### 4.4 语音与跨端的共同时间线

文本生成、TTS合成、音频排队、实际播放、打断是不同状态。以 `character_id/session_id/turn_id/output_revision` 关联；取消需阻止晚到音频继续播放。对话历史记录已发送/已听见的部分，不能将尚未播放的整段合成文案写成双方共同经历。Body 是输入输出 surface，不能私自另维护一套用户人格库；设备断线不改变关系。

## 5. 具体复用计划与工程代价

| 来源组件 | 复用方式 | 必需适配 | 首批决定 |
|---|---|---|---|
| AIRI memory index/detail 与角色归属 | 设计参考；TypeScript 不直接粘贴进 Python | E-Moti Memory API + Character Pack | 保留既有存储，不纳入运行依赖 |
| Open-LLM-VTuber heard_response/tts queue | 后续选择少量 Python 函数或适配器并保留 MIT 来源 | QThread/asyncio 生命周期、UI 播放回执 | 后续语音专批；本轮仅给契约 |
| OpenClaw origins/tombstones/revision | 机制参考；使用 E-Moti 数据模型与事务 | 事实→章节/画像来源链，异步提交比对修订号 | 本轮已实现来源失效与 epoch 栅栏；没有复制其网关或源码 |
| Hermes SOUL 与有界记忆 provider | 设计参考；不要复制 prompt 冻结策略 | persona JSON只读、hash、已有 performance profile | 本轮已实现稳定人格模块与表达链路接入 |
| N.E.K.O. `hybrid_recall.py` 中 BM25/RRF | 设计参考；未复制其实现 | CJK分词、有效性过滤、阈值验证、来源/许可证记录 | 当前保留词法检索，已提供可选语义分数接口；实际 RRF 适配来自 Graphiti，尚无默认 embedding provider |
| N.E.K.O. proactive decisions | 学函数式决策与投递再检查 | 去掉其工作监督领域规则，接现有主动陪伴 | 后续独立小改，保持不打扰默认体验 |

“借鉴设计”与“复制代码”要在 THIRD_PARTY_NOTICES/ADR 分别记录。现阶段可沿用 Python 标准库与本项目模型，不必为了证明复用而迁入大框架。如果后续复制源文件，应记录上游 commit、文件、许可证、改动范围、上游测试，以及为什么它比现有实现维护成本更低。

## 6. 可直接转成 E-Moti 验收用例的真实风险

这些是外部已披露边界或源码观察，不是本报告宣称已在 E-Moti 复现的缺陷：

1. **遗忘后的在途写回**：旧 summary 任务启动 → 用户遗忘 → 任务完成。应拒绝旧 revision，即使重启重放也不能恢复（N.E.K.O. #3405、OpenClaw tombstone）。
2. **删除后角色切换/同步复活**：A角色删除记忆 → B角色 → 返回A → 重启/同步；无旧事实（AIRI #2671）。
3. **本会话仍带旧冻结画像**：删除事实后直接问、不先新开会话；不得继续读取冻结 system prompt（Hermes documented behavior）。
4. **功能组合缺口**：选择长期记忆代理后打断语音、发送图片；应有端到端证据或明确降级，不能仍显示全功能可用（Open-LLM-VTuber LettaAgent）。
5. **人格与现实混淆**：游戏角色说“我住在上海”、助手即兴说“上周一起旅行”；不能写成现实用户事实或已经发生的共同经历（商业角色剧情产品不提供这类现实保证）。
6. **工具连接成功但不会被调用**：adapter 自测成功后还要检查实际 LLM 请求/trace 与返回结果显示，不能只验设置页（AIRI #2778）。
7. **后台噪声挤掉真实互动**：自动任务产生1000条重复记录，用户重要偏好只一条；召回应按来源与场景筛选，不让 cron 词频主导（Hermes session_search 源码）。

## 7. 本报告与本轮代码的关系

本报告是截至 2026-10-25 的研究快照。上面的“值得借鉴”不表示全部已经集成；跨设备协议、语音完整打断和更自然的主动性仍需独立验收。

本轮实际升级以 E-Moti 的既有情感记忆、角色包和 PySide6 相册为基础，新增记忆修订与派生失效、稳定人格输入、最终 prompt 接线和用户确认入口。具体阶段、源码入口与未完成项见 [产品定位与分阶段路线图](product-roadmap.md)；基准的定义及真实模型未验证范围见 [Memory Benchmark](benchmark-spec.md)。

本轮已发生的外部代码复用是 [Graphiti RRF 小算法适配](../../third_party/graphiti/README.md)，不是 Graphiti 整套图数据库服务接入，也不是 N.E.K.O. 检索器移植。后续复用任何 provider、切句器或语音队列，仍须逐文件固定上游版本、保留许可、记录改动，并执行与 E-Moti 实际运行组合相符的测试。
