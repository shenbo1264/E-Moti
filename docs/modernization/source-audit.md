# E-Moti 源码审计：固定基线与本轮修复

> **原始审计基线固定为 `b9f200955123790a5c66abcaf4e2567b3659a90e`，简称 `b9f2009`。** 这是 2026-08-20 合并 PR #4 后的 `main`。本文“基线缺陷”均描述该提交，不表示这些问题在本轮升级后仍然存在。后文单列已纳入的修复与剩余边界；最终测试数量、运行环境和证据以 [verification.md](verification.md) 为准。

审计日期：2026-10-25。开始工作时已核对默认分支、分支列表和 PR 状态，未发现待合并 PR。本次审计使用固定提交的独立源码快照，避免开发中的修改污染旧版结论。

## 1. 审计方法与证据层级

实际阅读了 memory model/store/service/policy/retrieval/reflection、记忆相册 controller/Qt、story runtime/bridge、legacy migration、controller/expression request/pipeline/expressor/dialogue policy、character pack/performance profile/session，以及 Plugin Runtime 和语音、视觉、主动交互的主要路径。

证据分四层：

1. **代码存在**：读取真实函数与调用链，模块名或 README 宣称不能代替实现。
2. **测试存在并覆盖什么**：核对断言是否验证最终产品行为，避免只测中间 dict。
3. **本轮实际执行**：运行固定基线的定向测试与缺陷探针，并以同一个 benchmark 对照新旧版本。
4. **尚未验证**：真实模型、Windows 桌面、真实麦克风／扬声器／摄像头、长期用户体验。历史 PR 的测试数或 Windows／DeepSeek 记录只算历史材料，不当成本轮重测。

可重现的对照数据集及原始结果参见 [benchmark-spec.md](benchmark-spec.md) 与 `evidence/memory-benchmark-before.json`。完整验证命令与本轮最终结果参见 [verification.md](verification.md)。

## 2. 基线已有的可保留能力

原项目确实存在以下实现，不能简单删除重建：

- 已结算的 inventory／relationship／memory 领域事件经确定性 policy 转换为记忆，成组事件可去重。
- 对首个重要事件、里程碑和明确用户请求有不同写入规则；未经完成／接受的主动交互和带原始屏幕内容的事件不会自动入长期库。
- V2 记忆具有 ID、角色、owner、source/source IDs、发生／创建／更新时间、情绪、重要性、访问次数、固定状态、用户确认和替代关系。
- 中文字符／二元组与英文词的词法召回，叠加相关性、近因、重要性、情绪、关系和强化权重；无关话题有相关性门槛。
- 用户可在相册查看普通回忆、固定、纠正和逻辑遗忘；纠正使用替代链而非仅覆盖文本。
- 章节以已有 memory IDs 为来源进行确定性拼接；已有角色存档、对话和记忆目录隔离。
- Plugin Runtime 的可撤销注册、依赖排序、权限声明、capability provider、静态审查、失败计数和插件中心均有实际代码。

这些是第一批升级的基础。问题集中在**能力之间没有形成完整有效性闭环**。

## 3. 最重要的基线断点：V2 没有到达真实 Prompt

基线 `memory_integration_bridge.py:28` 把 `emotional_memory` 加入中间 context；`PluginStoryBridge` 同时能加入 `plugin_context`。但 `expression_request.py:147` 的字段白名单只有旧记忆、感知、近期对话、工具结果和玩家消息，丢弃 V2 与插件字段。`expression_expressor.py` 的 `ShinsekaiAIExpressor.build_prompt` 只消费旧 `recent_memory`／`recent_dialogue`／`long_term_memory`。

因此基线可以出现：service `recall()` 返回正确记忆，context enrichment 测试通过，但真正发给模型的 prompt 没有这条记忆。固定基线的 benchmark 正向召回与最终 prompt 交付结果证实了这个差异。

这也是修复顺序的理由：必须在接通实际 prompt 的同时修复失效传播，否则旧摘要、画像和其他正文副本会获得进入模型的路径。

## 4. 基线问题清单与本轮处理

下表中的函数和行号均针对固定基线；本轮代码已改变，定位新版请使用函数名。

|级别|固定基线证据与问题|本轮处理状态|
|---|---|---|
|P0|`expression_request.py:147` 丢弃 V2／插件字段；`expression_expressor.py` 未消费 V2|已加入有界 V2、persona、plugin context，并接到真实 controller → request → prompt；另有最终 prompt 正向交付测试|
|P0|`EmotionalMemoryService.forget` 只设 deleted；`latest_chapter` 无来源有效性核验；纠正也留下旧章|已加入来源 fingerprint、章节读取校验和事务内失效；相册也只读取有效章节|
|P0|`CoreBondProfile` 的偏好／边界／仪式／故事线是无来源字符串，删除原事实不影响投影|已加入字段证据绑定和当前有效视图；旧无来源字段保留存储供审计，但不无条件进入 prompt|
|P0|`controller._expression_context` 同时提供旧记忆库和聊天历史；request 从 snapshot 继续读旧 memory_log|已将 V2 作为推理权威，屏蔽旧库／snapshot 旁路，以 context epoch 隔离撤销前对话和旧感知／工具／插件上下文|
|P0|`migrate_legacy_entries` 对相同 deterministic ID 重新 upsert 可恢复 deleted 状态|已加入迁移完成标识与 retired IDs／来源 tombstone；迁移重放不能视为新的用户授权|
|P1|子类 `switch_character` 在 `super` 生成新角色表达后才更换 story|已调整顺序：先完成角色、story、persona 初始化，再按需生成表达|
|P1|V2 路径无 owner 命名空间；load/save 主要只验 character；profile 读入未核对 scope|已加入 owner 命名空间、character／owner 双重检查与路径 ID 验证|
|P1|“请记住…”的候选／确认方法主要由 tests 使用，聊天入口和 Qt 缺确认流程|已接入显式聊天候选、相册待确认内容、确认／放弃与手动记住入口；pending 仍为当前会话内存状态|
|P1|`CharacterPerformanceProfile` 读取方法没有接入 controller；实际风格主要固定为星汐|已将当前角色包的 performance profile 和版本化 persona 接入；支持可选 `persona.json`；不自动用聊天改写身份|
|P1|章节卡宣称支持“固定／忘记”，实际 controller 只查普通记忆，可能 KeyError|章节只显示已支持的来源查看动作；章节失效随来源变化传播|
|P1|插件待确认只返回 ID；source IDs 丢失；自动提案误标 `user_confirmed=True`|已将完整候选接入确认队列，保留 source IDs／事件 ID；自动领域提案不伪称用户确认；增加 scope／durable／epoch 检查|
|P2|V2 由三个 JSON 文件组成，纠正、遗忘、章节、画像不是同一事务；固定 `.tmp` 无多进程锁|已增量采用一个 SQLite 权威 document，正文与撤销元数据同事务提交；不是引入第二套活跃事实数据库|
|P2|缺少事实版本、置信度、scope、valid_from／valid_until|已增加字段与硬性读取门槛；到期会推进一次失效屏障，避免旧聊天重新带回过时事实|
|P2|旧检索为词法加权，没有语义召回服务|保留离线词法基线，加入可选语义评分接口与 RRF 融合；没有默认部署 embedding 模型或向量库，也没有真实语义效果结论|

“已加入”表示实现已纳入工作树，不代替最终验收状态。对应自动测试、实际执行结果及未验证内容统一参见 [verification.md](verification.md)。

### 本轮集成审查追加的兼容修复

以下是本轮把 V2 接为唯一推理权威后发现的集成回归，**不应归为固定基线已有缺陷**，现已纳入实现：

- 旧「记住称呼」按钮只更新 `state.player_alias`，原来由 relationship tool 进入模型；撤销屏障启用后，新称呼也被挡住。`PluginEnabledCompanionController.set_player_alias` 现在为明确用户编辑建立事实来源与画像绑定，改名／清空撤销旧来源，保留原 UI／存档字段。旧存档称呼只在首次且无撤销历史时导入；重启不能从该展示字段重新生成已遗忘称呼。用户主动重述可成为独立新来源。
- 旧公开 `upsert_long_term_memory` 在初始化之后写入 legacy 文件，曾因只做一次迁移而成为静默无效写入。子类兼容入口现把许可类别直接写入 V2，同 key 修订更新来源版本与失效屏障；不再新增第二个活跃写入目标。退役 key 的重放会明确报错；未获确认的模型来源与临时工作类别不能经此入口写成长期事实。新的明确用户来源不受全局字符串黑名单限制。
- 更改 LLM 设置会替换 expressor，曾丢失已经连接的 performance profile。替换入口现在重新绑定实际当前角色的 profile，也覆盖角色切换过程。

`tests/test_controller_memory_compatibility.py` 的 8 个用例先实际运行得到 **8 failed**，修复后该组全部通过；连同 prompt lifecycle 与 plugin controller 既有契约的聚焦执行得到 **21 passed**。另将旧 archive 旁路测试改为明确注入 legacy service/store，避免把新兼容 API 新建的独立事实误当成旧副本。最终全量验收仍以 `verification.md` 为准。

## 5. 已复现的基线 Bad Cases

### 5.1 遗忘后旧章节仍在

保存“我最喜欢的饮品是咖啡”等三条事实，生成章节，再遗忘饮品事实。单条 recall 已返回空，但章节仍含“最喜欢的饮品是咖啡”。这直接说明“向量或列表里不再召回某条”不足以证明遗忘。

### 5.2 纠正后出现自相矛盾的证据

把饮品从“咖啡”纠正为“茶”。基线 context 同时包含新事实“茶”和旧章节“咖啡”，没有统一的最新有效版本。

### 5.3 画像保留被遗忘偏好

把事实写入 `stable_preferences` 后遗忘源记忆。基线偏好仍长期出现在 `bond_profile`，没有 source IDs 可以追踪并撤销。

### 5.4 迁移复活

旧条目迁移 → 遗忘 → 再次迁移，相同来源被恢复成可召回状态。删除标记必须与来源 replay 防护结合，不能只过滤单次查询。

### 5.5 角色与 owner 隔离

同 root、同 character、不同 owner 的两个 service 实例能互读。另在 `switch_character(..., include_ai_expression=True)` 过程中捕获到新角色 state 与旧角色 bond profile 组合。日常切换的默认 `include_ai_expression=False` 可以掩盖后一问题。

### 5.6 输入／输出链断开

真实 controller 输入“请记住…”后没有候选或对应 memory；直接手工写入 service 后又被 request 白名单丢弃。测试应同时覆盖“记得进去”和“读得出来并到达最终输入”。

### 5.7 Soft-delete 的范围

基线遗忘后 JSON 仍保留正文，这是既有逻辑删除语义，不能称为已经物理擦除。本轮也保留旧迁移源、可读历史和必要的本地审计信息；“后续推理不再使用”与“清除每份磁盘副本”仍是不同操作。不能据此承诺擦除备份、已播放音频或远端模型日志。

### 5.8 开发中发现的时间旁路

首批修复通过初始契约集后，额外检查发现：事实 `valid_until` 已过，但原句仍位于没有同步失效的近期对话。已将这个真实缺口加入第38个 benchmark 用例，并增加到期失效屏障。详见 [benchmark-spec.md](benchmark-spec.md)。

## 6. Plugin Runtime 审计

现有 Runtime 值得继续使用。它提供 contribution 注册与撤销、manifest 校验、依赖关系、权限声明、host capability providers、插件中心与包安装检查、失败计数和 journal。

其“isolation”指异常与生命周期隔离。`plugin_audit.py` 已明确插件在宿主进程内运行，不是操作系统沙箱；`PluginSubsystem._execute` 用 try/except 和失败计数处理异常，不能终止无限循环，也没有跨所有 hooks 的硬超时。

本轮修正了记忆桥的角色 scope、durable 事件、完整 pending candidate、source IDs、用户确认标识、stale epoch 和失效后的上下文准入。仍需明确：

- 插件 Python 代码属于受信任本地扩展；静态审查与权限契约不能证明任意不可信插件安全。
- `requires_user_confirmation` 候选目前没有跨应用重启持久恢复。
- 插件自行拥有的世界／任务数据仍应由插件或外部服务解释。未声明 epoch／character 的旧 context provider 在失效后会被屏蔽，不能靠“相信插件已经更新”继续提供旧数据。
- Stargazing 示例 storage 的 count 是插件级状态；不能据此声称所有第三方插件已经获得角色级存储隔离。
- Relay、Game Companion、Body 的实际 adapter 尚未开发；本轮没有重构这些项目。

## 7. 多模态、主动性与人格的实际边界

### 已有实现

- ProactiveCompanion 有总开关、quiet hours、分种类／全局 cooldown、daily limit 和拒绝后的冷却；Focus companion 的完成事件可以作为受控记忆来源。
- LLM 有 OpenAI-compatible／Responses 客户端、超时和异常 fallback、typed expression events、只读 intents 与本地状态权威边界。
- ASR 走手动录音 → 转录 → `DialogueRequest`；TTS 消费校验后的 speech，支持 voice profile、多个 HTTP／Edge provider、缓存及播放器 stop。
- Screen observation 有 resize、内存 data URL、只读 summary 和显式设置；Web search／TopicScout 有独立上下文。
- Character Pack 已有渲染器、素材、名称、关系文案、voice profile 及角色目录；本体不依赖 Relay 或硬件即可运行。

### 本轮不能宣称完成的能力

- 角色人格随长期经历自动演进：本轮只允许作者／用户配置版本化身份，自动变更仍未实现。
- 自动从普通聊天抽取全部偏好、解决任意语义冲突、自动长期巩固：当前优先完成显式用户事实和已结算事件，`consolidate`／profile 编辑仍主要是受控 API。
- 连续全双工语音、VAD 自动打断、端到端实时流式对话：没有完成。现有 LLM 路径在线程池提交后同步等待，不能因此声称 UI 已完全非阻塞。
- 已排队语音／已生成音频缓存的全链删除：没有完成；新 prompt 的失效控制不等于撤回已产生的媒体。
- 跨桌面／游戏／实体设备的完整会话协议：没有完成；当前只为后续分离权威状态保留接口方向。
- 真实模型对共同经历的事实性、人格一致性、少打扰体验、长周期关系质量：没有本轮实模型／用户研究证据。

## 8. 存储、迁移与性能判断

本轮采用标准库 SQLite 封装一个权威记忆 document，迁移原三份 V2 JSON 后不再把它们作为活跃事实源读取。这个改动解决的是 crash window、并发写锁和撤销原子性；查询仍由 Python 有界扫描，不能宣传成图数据库或大规模向量检索系统。

旧存档和角色目录保留；旧无来源画像保持可审计而不自动被当成可靠事实。迁移失败应明确报错，不能静默退回旧副本恢复被遗忘内容。逻辑养成时钟与 Unix 时间尚未完成统一历史重建，本轮有效期测试使用一致时间坐标；不要把这些测试理解成已完成所有时区／跨版本日期迁移。

当前代码仍有检索访问计数持久化与若干次同步读取。Benchmark 只测有限条目下的本地 context/request/prompt 构造；没有长达数年的存档、设备低功耗、并发压力或 Windows 文件系统故障实测。后续应根据真实 p95 延迟和内容规模，再决定批量访问统计、读取事务优化和语义索引缓存，而不是先加第二套长期库。

## 9. 文档一致性

固定基线 `AGENTS.md` 仍写 `original_oc` 默认、部分角色非 bundled，而代码 `character_pack.py:12` 与 README 已是 `xingxi_pixel_pet` 默认及当前可见角色集合。这是历史文档与代码不一致，不应借此在本批再次更换默认角色或素材。2026-10-29交接已修正根AGENTS的默认角色说明，未修改角色代码或资产；本段继续保留原基线审计事实。

README 和展示材料需要把“模块具备”“主链已接入”“自动测试通过”“真实设备／模型验证”分开写。旧 PR 的发布和 live smoke 记录应保留日期与来源，不能替代此次终验。

## 10. 固定版本源码来源

- [基线提交](https://github.com/shenbo1264/E-Moti/commit/b9f200955123790a5c66abcaf4e2567b3659a90e)
- [V2 模型及存储](https://github.com/shenbo1264/E-Moti/blob/b9f200955123790a5c66abcaf4e2567b3659a90e/src/guanghe_companion/emotional_memory.py)
- [V2 service](https://github.com/shenbo1264/E-Moti/blob/b9f200955123790a5c66abcaf4e2567b3659a90e/src/guanghe_companion/emotional_memory_service.py)
- [ExpressionRequest](https://github.com/shenbo1264/E-Moti/blob/b9f200955123790a5c66abcaf4e2567b3659a90e/src/guanghe_companion/expression_request.py)
- [实际 prompt 构造](https://github.com/shenbo1264/E-Moti/blob/b9f200955123790a5c66abcaf4e2567b3659a90e/src/guanghe_companion/expression_expressor.py)
- [Controller overlay](https://github.com/shenbo1264/E-Moti/blob/b9f200955123790a5c66abcaf4e2567b3659a90e/src/guanghe_companion/plugin_enabled_controller.py)
- [Plugin bridge](https://github.com/shenbo1264/E-Moti/blob/b9f200955123790a5c66abcaf4e2567b3659a90e/src/guanghe_companion/plugin_story_bridge.py)
