# 本轮检索失败：已见回归改善，独立首评无改善

生产冻结为 `63cdf797bc4e966937001c2afba9017c50b37087`。本文件只分析检索与最终证据交付，不评价生成回答、人格或语气。读取的是实际 Flash 证据判断请求、原始回复和宿主最终结果；没有修改生产代码、原始样本、gold 或首评成绩。

## 分母与结论

第九已是开发中看过的回归集。第十由独立代理在未读取本轮生产修复及第七至第九数据/报告的条件下生成，冻结后才用于首评；共 2 个合成档案、16 条来源、12 问，其中有据 8 问、无答案 2 问、无需记忆 2 问，含 2 个跨卡问题、1 个多轮问题。它是小型独立合成检索集，不是外部 `chat-memory-benchmark` 的 714 题成绩，也不验证普通聊天事实抽取。

第十输入 SHA-256：`b1474fa97fb747ab5a37da04f9603e5fe8da0e1ea8a48ba9041cfd536c8c2642`。同档案扩充到 300 条，方法共享原始输入。现在第十已被阅读，只能用于后续回归，不能再称为未见样本。

| 数据/方法 | 严格正确证据交付 / 8 | 无答案误注入 / 2 | 状态正确 / 12 |
| --- | --- | --- | --- |
| 第九旧首评 routed | 4 | 0 | 8 |
| 第九旧首评 layered | 3 | 0 | 7 |
| 第九本轮回归 routed | 7 | 0 | 11 |
| 第九本轮回归 layered | 7 | 0 | 11 |
| 第十修复前 routed，`5032ee6` | 4 | 0 | 8 |
| 第十修复前 layered，`5032ee6` | 4 | 0 | 8 |
| 第十修复后 routed，`63cdf79` | 4 | 0 | 8 |
| 第十修复后 layered，`63cdf79` | 4 | 0 | 8 |
| 第十无长期记忆 | 0 | 0 | 不适用 |
| 第十旧词法 | 4 | 0 | 不适用 |
| 第十旧 BGE + RRF | 4 | 1 | 不适用 |

**第十两条新路线均没有改善。** 修复前后失败的是同四题；两题普通陪伴仍都发起了不必要检索（2/2）。新的零误注入不能抵消有据问题的漏交付。各方法是单次模型运行，不以这组小样本作显著性或全面优越性结论。

## 证据位置

根目录下 `artifacts/codex_handoff/memory-upgrade/followup-benchmark-20261106/`：

- `ninth-after/{routed,layered}-300.json`：已见第九回归。
- `tenth-before/{none,lexical,bge_rrf,routed,layered}-300.json`：独立第十修复前。
- `tenth-after/{routed,layered}-300.json`：独立第十冻结后首评。
- `failure-boundary-diagnostics.json`：使用真实原始响应、原始样本，重放当前 `validate_judgment` 与 `check_eligibility` 的只读诊断。它没有发模型请求、没有写存档，也没有改变正式成绩。

按 `rows[].query_id` 定位问题。实际候选在 `evidence_judgment.requests[0].wire_payload.messages[1].content` 内的 `candidates`；模型原始答案及推理在同请求的 `provider_response.choices[0].message`；最终来源用 `verified_delivered_ids`、`trace` 和 `actual_provider_prompt` 交叉检查。下列失败中 `provider_lost_evidence_ids` 为空，没有发现最终 Prompt 预算裁掉必要证据的原因。

第九旧首评见 [之前的第九失败记录](ninth-retrieval-failures.md)，保留原有成绩。

## 已见第九：修复了哪些，仍失败什么

`v9_scent_q3` 的 s93 身份来源和 s94 物品来源现在一起交付；`v9_scent_q4` 的明确否定 s95 通过；`v9_model_q1` 的 m91 身份与 m92 属性均交付；`v9_model_q2` 的个人记录 m93 不再被外部执行器路由提前阻断。两条路线均只剩 `v9_scent_q2` 失败。

### `v9_scent_q2`：未来日期路由修复，单卡时间基准仍阻断候选

宿主现在已得到 `bounded/as_of`，不再是 `chat`。两次实际请求仍不含 s92，只提供当前 s91 等来源。Flash 明确指出旧名称只到启用日前有效，不能证明新名称；返回空证据是针对已收到材料的合理拒绝。

s92 原文已写下一版名称和启用日期，`valid_from` 也在未来。档案评测声明 Unix，但卡片 metadata 没有 `time_basis="unix"`。日期候选准备把 bounded 转为 fact 后，`check_eligibility` 的未来有效事实例外仍要求卡片本身明确 Unix；否则返回 `not_yet_valid`。因此主要是候选资格与时间基准承接缺口，不能继续称作路由未修，也不能通过放宽所有旧逻辑时间来修复。

原始条目、模型输入及重放结果均保留。没有为了通过这题向来源补写时间基准。

## 独立第十：四题失败的真实链路

四题的必要来源在修复前后、routed/layered 的实际模型输入中均存在。Flash 均认为有直接证据，最终却只交付部分或零来源。这里的 `trace.rows_loaded=0` 不能解释为模型准备阶段没有找到候选。

### `t10_bake_q3`：与亲属“一起”被当成与角色共同经历

问题问与阿栗预约的日期、时间、活动及亲属关系。m1 明示阿栗是表妹岑悦；m4 明示预约日期、时间及活动。修复后两次模型都返回两项 sufficient，计划项为 `claim_use=planned_event`，关系项为 `current_attribute`；最终仅 m1 交付，m4 丢失。

只读重放显示，原路由看到“一起”就设置 `requires_shared_event=True`，没有区分“用户与亲属”和“用户与角色”。该标记被当作不可变约束继承，又使 planned_event 无法转成计划模式。首个拒绝为 `missing_completed_shared_event_evidence`。这不是模型不认识阿栗，也不是昵称来源没有召回。

m4 的计划只在原文及评测顶层 state 中表达，没有生产 metadata 计划标记；因此解除参与者误判后仍需处理来源化计划语义。不能仅凭模型说 sufficient 就跳过真实性与参与者要求。

### `t10_bake_q4`：原文共同经历未满足当前结构证明契约

问题问给第一只面包取的名字。m6 原文明示用户与角色聊天时烤好面包，并共同取名；两次模型均引用完整原文，返回 episode/completed_event/sufficient。最终没有来源。

实际宿主模式是 current，不是历史过期过滤。`grounded_shared_event` 要求特定领域事件来源，或 completed 状态加双方参与者。m6 的 source 是 `synthetic_user_statement`，不是模型来源，也没有被一般可信度检查拒绝；但它不属于函数认可的领域事件来源，metadata 也没有 completed 和参与者。首拒为 `missing_completed_shared_event_evidence`。

这说明目前对“原文明示、结构未标注的共同经历”支持不足。本集没有经过普通聊天提取流程，不能据此断言真实聊天写入一定缺这两个字段；同样不能把未被生产入口识别的合成 source 当作已完成用户确认的领域事件。

### `t10_tank_q3`：明确否定与 completed_event 标签组合仍被误拒

问题问以前是否喂过活饵。m4 原文明示从来没有喂过。修复后两次模型均给完整 quote、`occurrence=explicitly_not_occurred`，但同时选 `route=episode`、`claim_use=completed_event`。最终没有来源。

宿主只有在否定证据配 `current_attribute` 时才转换到当前属性模式；本次组合保留 `history`，资格检查将仍有效的 m4 拒为 `current_fact_not_historical`。模型已正确识别否定，却使用了与宿主恢复逻辑不兼容的标签组合。不能归因于未召回、JSON 语法失败或事实确实不存在。

### `t10_tank_q4`：原文更正后的计划无结构标记

问题要求列出已记下的换水日期、时间和比例。m5 原文清楚标出新日期、原日期被纠正及尚未进行。两次模型都引用 m5，返回 fact/planned_event/sufficient。宿主完成计划模式转换后，因 metadata 没有 `planned`、`plan_status` 或 `event_status`，拒为 `not_a_plan`。

数据顶层 `state="planned"` 是评分标签。现有 `make_entries` 有意不把它写入生产条目；不能把这个标签自动转成系统答案或修改原始输入来提高分数。真实缺口是当前宿主要求结构计划状态，而本次合法原始文本未带这种结构。后续应通过实际写入/提取路径证明计划状态来源，或明确支持带原文证明的计划读取；本轮未实现，也未重跑改标签版本。

## 本次结果能够说明的范围

第十更偏向有来源原文、但缺少事件状态与参与者结构标注的输入；它仍是检索评测，不是从历史聊天抽取到长期记忆的端到端测试。不能把评测 state、gold 或参考答案补进系统 metadata。第九的单卡 Unix 要求、人物“一起”的主体范围、否定事件的标签一致性、原文到结构状态的衔接，是后续需要解决的实际边界。

本文件不增加新的密封题，不修改失败题重算分数，也不以这些检索结果替代正在另行运行的真实生成回答和人格评审。
