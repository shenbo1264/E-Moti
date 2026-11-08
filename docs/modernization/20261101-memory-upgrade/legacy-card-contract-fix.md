# 旧明确记忆卡片的最终 Prompt 交付修复

同一 `tools/memory_benchmark.py` 和未修改的 38 条开发合同，分别运行于独立包基线 `2f3978f` 与本轮修复前代码，均为 29/38 通过；有据检索 11/11，最终 Prompt 仅 2/11 交付。这是包内已有断链，不是本轮新增的九项退化，也不是评测误用了旧上下文接口。工具实际调用 controller、bridge、当前按需检索和 ExpressionRequest。

原因包括省略主语的字段标题被当成通识或人名、旧明确卡片没有外部事件 ID 被字面验证拒绝，以及原文与标题可以证明的属性未形成只读事实视图。更正后的当前原话也存在这个缺口。

本次复用既有 `read_fact_view`，增加当前更正文的明确偏好语义、字段标题与原话完全绑定的属性、英文自述，以及第一人称正在进行的活动目标的只读解析。标题和原话不一致时不推导；原文未标所有者的字段，不推断成用户本人。未向权威存档写入这些派生字段。已确认的明确用户卡片可以作为自身原始证据，不强制另有外部事件 ID；最终来源指纹、角色、owner、scope、时效及撤销约束继续使用原通路。

短字段标题走有界事实检索，定义、通识解释和建议请求保持不检索。昵称问题不再因为带有“喜欢”而被解释为饮食偏好。没有新建语料名单或针对答案的绕过逻辑。

最终实际结果：

- 原 38 条合同 38/38 通过；有据检索 11/11，最终 Prompt 11/11；无关请求注入 0/3。
- 145 项关联测试通过，包括新增 17 项不同活动、值与英文属性的测试，以及错误主体、字段、活动、不可信来源、未确认卡片和通识请求的负例。
- 初始独立样本 8 项失败；其中一项暴露原已有的朋友事实误用为本人。修复中再次捕获三项通识误路由、两项语境偏好退化，修正后全部通过，失败日志保留。

证据位于本机 `artifacts/codex_handoff/memory-upgrade/`：`development-38-package-baseline.json`、`development-38-after-cleanup.json`、`development-38-legacy-card-final.json`、`legacy-card-delivery-red.log`、`legacy-field-definition-red.log`、`legacy-card-focused-r2.log`、`legacy-card-focused-final.log`。

这些是确定性开发合同及工程回归，不是新的密封集泛化结论。此前真实模型报告仍对应报告内记录的代码版本；不能将本次修复未经复测的模型效果计为已验收。

## 已建索引的升级

补充使用 `2f3978f` 的独立 Python 进程建立四份合成旧 SQLite 档案，再由当前进程重开。最初完整检索虽可借助词法扩展交付 4/4，已有投影的 predicate/value 仍为空，直接结构化查询为 0/4；相同 raw_digest 不会自动更新推导字段。

因此将已有派生 `ALGORITHM_VERSION` 的 `typed-literal-v2` 提升为 `typed-literal-v3`，复用现成索引重建机制。四项升级测试先失败后通过，关联 55 项测试通过。同四份真实旧进程档案再次重开，直接精确查询 4/4；权威 JSON 逐字节相同，来源指纹和 context_epoch 均保持不变，仅派生索引 generation 更新。无需迁移或重写长期事实。

原始升级证据：`artifacts/codex_handoff/memory-upgrade/legacy-index-restart/` 下的 `baseline.json`、`current.json`、`after-algorithm-upgrade.json`，以及 `legacy-index-version-red.log`、`legacy-index-version-focused.log`、`legacy-index-rebuild.log`。档案均为独立合成存档，没有访问真实用户数据。

## Claude 当前问题核查后的补修

`51f21d5` 继续修复已确认旧卡片的“我养/拥有一只叫X的宠物”及毛色修饰句式。复用既有宠物字段支持范围，来源必须可信；名称不写成用户姓名，不反写权威事实。猫、兔子、鹦鹉保存重启后召回先红3项，负例3项通过；修后相关114项通过。

真实Flash修前/后各4次，复用原档案且聊天历史为空：三个正例由unknown变为正确名称，别人宠物负例保持unknown，8次输出均通过生产解析器。这些是开发回归，非新增密封结论。旧v3索引在重开时自动提升为v4；四份权威payload逐字不变、epoch保持0，比较在访问计数写回之前完成。完整前后请求、回答及迁移证据见 `artifacts/codex_handoff/memory-upgrade/owned-pet-regression/`。
