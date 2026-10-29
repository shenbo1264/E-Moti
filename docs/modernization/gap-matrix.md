# E-Moti 能力差距矩阵

基线：`b9f200955123790a5c66abcaf4e2567b3659a90e`。本轮目标是建立可靠的个人伙伴记忆／人格闭环，同时保持 Python／PySide6、本地独立运行、角色包和可选插件结构。

**“已实现”“已有测试”“本轮执行验证”“未验证／未实现”分别列出。** 测试文件存在不等于本轮执行通过；最终命令、数量、环境与证据统一见 [verification.md](verification.md)。基线缺陷及源码证据见 [source-audit.md](source-audit.md)。

## 1. 记忆、事实与人格

|模块／目标|固定基线已有实现|基线测试实际覆盖|本轮增量实现与对应验证|剩余差距／未验证|
|---|---|---|---|---|
|Emotional Memory V2：记住与来源|已结算事件 policy、first／milestone 筛选、source IDs、情绪、重要性、固定；显式请求候选 API|事件 eligibility、批次去重、候选确认／拒绝、基础存储往返|显式“请记住”接聊天入口；相册手动记住、完整候选查看／确认／放弃；保留事件来源，模型自述不能直接成为事实。见 `test_memory_lifecycle.py`、`test_memory_prompt_lifecycle.py`、`test_memory_album_lifecycle.py`；终验见 verification|没有普通聊天自动全量事实提取；pending 未跨重启保存；不代表模型能独立核验用户陈述真假|
|纠正、失效、遗忘|supersedes 替代链、deleted 标记；缺少派生同步失效|检查旧条目标 deleted；没有覆盖所有上下文副本|事务更新来源版本、retired IDs／origins、派生 invalidation、context epoch；旧历史／旧库／snapshot 旁路受控；过期触发一次屏障；在途旧表达不再呈现。见 lifecycle、prompt lifecycle、album lifecycle 与38例 benchmark|逻辑遗忘不等于物理清除所有本地备份、历史、音频缓存或远端日志；不能撤回已呈现内容|
|正确召回与排序|中文字符／二元组、英文词，相关性／时间／重要性／情绪／关系／访问加权；top-k|词法相似度、相关旧记忆优先于无关新记忆、pinned抗衰减|先做状态／scope／时间硬门槛；保留离线词法排序，引入可选语义评分 callback 与有来源的 RRF 融合；source fingerprint 排除访问计数。见 `test_memory_fusion.py`、memory lifecycle、benchmark|默认没有 embedding 服务／向量索引；不能把RRF接口等同于实测语义检索提升；复杂改写、共指和多跳召回未评估|
|章节与共同经历|源ID支持的确定性章节拼接、重复 source set 去重、相册章节|source IDs存在、重复consolidation幂等|来源fingerprint＋有效性校验；纠正／遗忘／到期／同ID正文更新会撤销旧章；UI不再显示未实现操作。见 lifecycle、album lifecycle|无常驻后台巩固计划；无跨多周自然叙事质量实测；“章节有来源”不代表模型自由生成的回忆均真实|
|CoreBondProfile 与关系|relationship stage、用户称呼、偏好、边界、仪式、story threads；原字段为无来源字符串|profile往返、小而常驻的context；未测原始事实删除后的画像|增加每项事实证据绑定与有效投影视图；旧「记住称呼」UI接入V2，改名／清空撤销旧源，重启不从state展示副本恢复遗忘事实；关系养成仍由本地规则拥有。见 lifecycle、prompt、benchmark与 `test_controller_memory_compatibility.py`|尚未自动从长期行为建立校准用户模型；细粒度画像编辑界面、冲突解释、自然关系演进实验未完成|
|稳定人格与Character Pack|角色包名称／文案／渲染／声音；有performance profile加载器但未接controller|pack验证、角色切换、素材／声音契约；profile工具级测试|`persona.py` 版本化、只读身份；旧包零迁移可用；可选 `persona.json` 设置表达、traits、偏好、习惯、边界；实际profile接controller，更换LLM设置后仍保留当前角色profile，聊天不能改persona hash。见 `test_persona.py`、controller compatibility、prompt lifecycle、benchmark|人格变化提案与用户审批尚未实现；没有真实模型跨场景人格一致性、幽默或不过度讨好评测；hash只证明配置稳定|

## 2. 上下文、交互与插件

|模块／目标|固定基线已有实现|基线测试实际覆盖|本轮增量实现与对应验证|剩余差距／未验证|
|---|---|---|---|---|
|AI Context Builder／最终Prompt|对话／旧记忆／感知／工具有界清洗；V2与plugin加入中间dict却在request被丢弃|边界截断、无效行过滤、enrich只读；未证明V2到最终prompt|request／expressor加入有界memory、persona、plugin字段；最后prompt实际包含有效事实；旧memory_log／long_term不能旁路；大payload预算测试。见 `test_memory_prompt_lifecycle.py`、`test_memory_prompt_budget.py`、benchmark|截断预算仍为实现级近似；没有真实provider tokenizer／多模型输出质量对照；某些模型可能忽视正确证据|
|跨角色／owner／场景隔离|常规角色目录独立；owner字段未对应物理命名空间；表达切换时存在旧story窗口|正常角色存档路径与恢复；未覆盖owner及带表达切换窗口|owner独立路径＋文档scope验证；切换全部状态就绪后才生成表达；默认companion scope排除work/game。见 lifecycle、prompt lifecycle与benchmark|桌面UI尚未提供多账号功能；外部系统协议、设备会话连续性与真实并发设备未实现|
|主动陪伴／情绪表达|开关、quiet hours、分项与全局cooldown、日限额、拒绝后冷却；focus完成事件可写入|确定性触发、节流、拒绝、focus状态持久化和领域事件|保留原主动层；经新记忆有效性规则构建表达，情绪仍只影响表达／本地养成，不改用户事实。原有测试加记忆入口回归；终验见 verification|未重新设计主动性候选规划器；没有长期自然度、打扰率、用户偏好适应或A/B数据；无需开启工作插件才能使用|
|Plugin Runtime／Plugin Center|manifest、依赖／权限、可撤销贡献、包静态audit、失败计数、reload、host providers、示例插件|加载／卸载、provider、action、权限、隔离失败、示例端到端|补durable／character检查、完整待确认候选、source IDs、真实确认标识、epoch防迟到写与失效后context准入。见 `test_plugin_memory_lifecycle.py` 与既有plugin suite|Python插件仍在同一进程；没有OS sandbox或全hook硬超时；插件自有数据清理与角色scope需其契约负责|
|用户管理与Qt相册|普通卡片固定／纠正／忘记／来源查看；章节部分按钮不匹配实现|controller动作与基础Qt展示|显示待确认内容；用户手动记忆；编辑使用完整正文而非卡片截断预览；epoch校验处理打开窗口后的纠正／遗忘／切角色竞态；source inspector增加版本／时效／scope。见 `test_memory_album_lifecycle.py`|可执行环境中的Qt回归不代替Windows桌面视觉验收；无全库导出／批量物理擦除工作流|

## 3. 模型、多模态、存储、隐私与性能

|模块／目标|固定基线已有实现|基线测试实际覆盖|本轮增量实现与对应验证|剩余差距／未验证|
|---|---|---|---|---|
|LLM 接入|Responses／OpenAI-compatible客户端、provider设置、异常／超时fallback、typed events、只读intent|客户端transport替身、解析、fallback、状态不变、smoke工具结构；PR有历史live记录|新增事实与persona实际输入、源失效后的inflight响应校验；仍复用既有LLM adapter。prompt lifecycle、预算与原有回归；终验见 verification|本轮没有真实模型推理；没有流式首token延迟／成本数据；当前等待路径仍可能阻塞UI|
|ASR|手动录音、转录服务、转为DialogueRequest、显式设置|合成音频／fake transport、返回解析、enabled策略、工具契约|保留现有链路；转录后的显式用户命令共享同一记忆入口；通过原有回归检查兼容性，执行结果见 verification|真实麦克风、噪声场景、VAD、自动barge-in、长时录音未本轮验证|
|TTS|多个provider、voice profile、音频缓存／播放／stop、只消费validated speech|fake HTTP／player、缓存命中、格式校验、profile映射|不重构声音栈；保证新记忆表达仍经原typed speech管线，原有回归结果见 verification|真实扬声器、合成模型质量未本轮验证；已经排队／缓存音频没有完整记忆撤销协议|
|视觉／桌面感知|显式设置、截图resize、内存data URL、只读summary；web/topic来源卡片|fake vision transport、summary清洗、关闭／无配置行为|撤销后旧感知／工具缓存不能继续作为新prompt证据；screen原文仍不自动入长期记忆|真实摄像头／Windows截屏、实时感知、跨设备同步、模型视觉质量未本轮验证|
|本地存储与迁移|养成存档／角色目录；V2三JSON与旧long_term并存；局部atomic replace|往返、角色路径、已有schema存档；缺跨文件撤销事务|标准库SQLite单权威document，同事务提交正文／派生／tombstone／epoch；一次性导入旧V2，旧long_term允许类别受控迁移；公开keyed兼容写入口转发V2，退役key拒绝重放；损坏不回退旧事实。见 lifecycle、controller compatibility与存储review回归；终验见 verification|未将所有养成存档迁为SQLite；旧源文件保留；旧key重放不等于新用户授权，重述需独立明确来源；没有真实断电硬件／Windows杀进程故障演练|
|隐私与用户控制|本地记忆、显式感知／语音设置、角色相册、soft-delete|基本删除flag、原始屏幕事件拒写、配置secret扫描等|推理层撤销闭环、源追踪／版本查看、owner／角色／scope隔离、旧候选／响应防重放；具体覆盖见benchmark与lifecycle|不承诺物理删除备份／历史／音频／远端日志；密钥安全／全盘加密并非本批工作；没有新增后台监听或桌面控制|
|性能与成本|最多若干百条有界JSON扫描、同步context、多种文本长度上限|局部长度／格式限制；没有标准化长期memory性能基准|增加同runner前后对照，本地context＋request＋prompt耗时、字符／字节、明确标估计的token；避免叠加多套memory服务|没有真实响应延迟／token usage／成本测量；SQLite读事务和访问统计仍需大存档profile；不能将新旧不等长prompt时间当公平性能胜负|
|独立运行与可选扩展|不依赖Relay、游戏agent或Body，关闭AI服务后本地宠物可运行|本地controller／插件／renderer与smoke测试|维持本体入口；本轮只改E-Moti，未重构外部项目或固件；角色、存档、界面回归见verification|Relay任务权威／游戏世界状态／Body设备协议仍属未来可选adapter；不能将未来架构写成现成功能|

## 4. 本批完成度的判断方式

最终集成审查增加的 controller 兼容组先运行 **8 failed**，实施后该组全部通过；与 prompt lifecycle、plugin controller 契约合跑为 **21 passed**。这是聚焦回归证据，不能替代 `verification.md` 的最终全量结果。已修复的对象为称呼编辑、旧 keyed 写入口以及 LLM 设置替换时的实际角色 profile。

第一批交付可以证明的是：在受控的显式用户事实与已结算领域事件上，**记住 → 召回到真实prompt → 纠正 → 旧事实失效 → 遗忘 → 派生与旧上下文失效 → 人格配置保持稳定**，并有可复现的本地契约测试。

它不证明“用户可以无限制自然聊天且所有事实都自动正确理解”，也不证明“角色已经形成成熟长期人格”。下一阶段应单独验证抽取质量、语义改写召回、证据充分性、真实模型输出、主动交互节奏和跨设备连续性。

Memory Benchmark 的详细分子／分母、原始bad cases、缺失能力处理和holdout限制见 [benchmark-spec.md](benchmark-spec.md)。所有最终通过数量、跳过项目和真实未验证项目以 [verification.md](verification.md) 的实际执行记录为准。
