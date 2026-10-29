# Memory Benchmark v1：确定性闭环与最终 Prompt 验证

## 这个基准测什么

这是 E-Moti 自有 **38 条合成用例的确定性工程契约测试集**。它验证记忆生命周期、来源有效性、隔离与实际模型输入连通性，不是自然用户总体准确率，也不是与其他 memory 产品的榜单比赛。

测试覆盖：6 条正确召回、3 条无关问题、3 条纠正、5 条遗忘、4 条派生失效、5 条角色／用户／场景隔离、3 条时间有效性、6 条禁止虚构事件写入、2 条人格配置稳定性、1 条迁移防复活。

数据集：`tests/fixtures/memory_benchmark.json`。脚本：`tools/memory_benchmark.py`。每条用例包含真实写入、纠正或遗忘操作序列及观测断言；数据全部为虚构昵称、地名、偏好和经历，每次创建临时用户目录，结束销毁。不会读用户当前存档，不调用网络／真实模型／麦克风／TTS。

## 为什么必须检查最终 Prompt

基线源码能够 `recall()` 到事实，但主 `ExpressionRequest` 白名单丢弃 `emotional_memory`。如果只检查记忆 API，就会得到“正确召回 100%”；如果只看最终 prompt 的泄露率，又可能把“完全没接记忆”误判为隐私成功。

因此每例分开观测：

1. Service recall 的 memory IDs、标题、正文。
2. `PluginEnabledCompanionController.get_expression_context()` 的真实上下文。
3. `ExpressionRequest.from_snapshot()` → `controller.ai_expressor.build_prompt()` 产生的最终 prompt。

这仍然不执行模型回答。模型可能忽视正确上下文或从自身常识猜错；该问题需要下一阶段真实模型对照。

## 运行与版本对照

```bash
python tools/memory_benchmark.py --output docs/modernization/evidence/memory-benchmark-after.json
```

同一 runner、同一 dataset 可以测试旧代码，确保不是分别编写偏向结果的两个脚本：

```bash
python tools/memory_benchmark.py \
  --repo /tmp/emoti-audit-baseline \
  --output docs/modernization/evidence/memory-benchmark-before.json
```

`--repo` 指向被测仓库，所有 `guanghe_companion` imports 从它的 `src` 加载，并在每个结果记录真实 module 路径。新旧仓库分别启动 Python 子进程，禁止在同一进程复用已缓存模块。`--dataset` 可指定另外一套 JSON；重复 `--case <id>` 可以选择小批用例。不存在的 case ID 会返回错误，不能空跑然后显示成功。

退出码：0 全部通过；1 存在失败／missing capability；2 命令行或数据集错误。

基线固定为 `b9f200955123790a5c66abcaf4e2567b3659a90e` 的 git archive。archive 本身没有 `.git`，因此报告 revision 显示 `archive_without_git_metadata`；源提交以审计与交接记录为准，不能把工作树 HEAD 冒充 archive 自报版本。每份报告同时记录 runner、dataset、全部 `src/*.py` 的 SHA-256 及 Python／平台，以便区分同 HEAD 下的未提交代码。

## 指标解释

|指标|分子／分母|解释与限制|
|---|---|---|
|correct_recall|正确返回的目标 memory ID 断言／所有正向召回断言|仅当前问题和 top-k=4；不是整个自然语言分布的召回率|
|final_prompt_delivery|必需事实片段出现在最终 prompt 的断言／所有正向 prompt 断言|必须与漏召回和泄露一起看；零交付绝不视为优良记忆系统|
|irrelevant_recall|无关问题中出现记忆或禁止内容的案例／无关问题案例|本版3个负例，不能外推总体误召回|
|outdated_fact_reference|纠正／时效组出现旧值、被排除ID或过期召回的案例／该组案例|本版检测上下文暴露，没有生成回答|
|forgotten_information_leak|遗忘／派生／迁移组发生正文／ID泄露的案例／该组案例|包含中间context和最终prompt；不代表物理擦除备份或撤回已发送远端请求|
|cross_role_owner_scene_contamination|隔离组观察到异域事实或切换中scope不一致的案例／隔离组案例|owner测试服务契约；当前桌面UI并未声明多账号功能|
|fabricated_event_write_acceptance|禁止写入用例中仍有active memory的案例／对应案例|测 host写入规则，不测模型能否编故事或正文事实判定|
|persona_configuration_stability|纠正／遗忘后配置hash不变／相关断言|hash覆盖当前角色包＋实际连接的performance profile（如存在）；仅配置不变，模型行为一致性单列 `not_run`|
|context_and_prompt_latency_ms|本地context构造＋snapshot＋typed request＋prompt格式化的计时分布|含这段代码中的本地磁盘访问；不含数据构造、预先recall探针、网络、模型、UI渲染、语音|
|estimated_prompt_tokens|`ceil(UTF-8字节数 / 4)`|粗略预算估计；不是provider tokenizer，不是实收token|

每个原始结果记录全部 checks、missing capabilities、兼容路径、context、prompt、活动事实数、实际导入路径和本地耗时。汇总表不能替代这些原始 bad cases。

## 对旧版本的公平处理

- 旧版本没有 `correct()`，runner 复用旧相册的实际 `remember(supersedes=old_id)` 行为，并记录 compatibility note。
- 旧版没有 scope、validity、画像 source IDs 参数，runner 去掉不支持的参数以继续观察旧行为，但同时写入 `missing_capability` **失败**。不能把“旧版不支持”悄悄跳过然后报全通过。
- 未捕获的产品异常计为 execution_error 失败。不能过滤掉失败例改变分母。
- “当前用户问题直接引用旧值”不应算记忆泄露；数据集检查禁止片段没有出现在 probe query。
- 生成事件测试使用真实 `EmotionalMemoryPolicy`／service 接口，不能以伪造的满意回答替代。

## 本轮基线结果

在审计环境执行固定基线：**12/38 整例通过**。正确召回为 **11/11**，但最终 prompt 事实交付为 **0/11**。这说明原有检索能工作，但实际表达链路没有消费 V2。

遗忘／派生／迁移组在 **8/10** 个案例观测到失效未传播；跨角色／owner／场景组 **4/5** 失败。人格配置 hash **2/2** 未变；这不说明模型人格表现合格。首轮本地构造 prompt 中位耗时约1毫秒，机器／缓存／负载会影响结果，应读取 JSON 的实际值，不作为应用端到端延迟承诺。

修复后同一 runner 的最终结果已写入 `memory-benchmark-after.json`：**38/38 整例通过**，最终 prompt 事实交付 **11/11**，遗忘／派生／迁移组 **0/10** 泄露，过时事实 **0/6**，隔离组 **0/5**。全部分母、实际构造耗时及未运行的模型指标见 [verification.md](verification.md)。这仍是开发契约集，不是独立 holdout 或真实用户准确率。

## 一个由对照实验发现的真实工程 Bad Case

最初37例在开发中的修复版全部通过后，审计增加了一个有明确依据的变体：用户先说“本周住在青藤城”，这句话同时进入事实记忆与聊天历史；事实的 `valid_until=200`，在 `now=300` 提问“本周城市”。

当时 V2 recall 已正确返回空，但旧历史的 context epoch 没有因时间到期变化，原句仍通过 `recent_dialogue` 进入最终 prompt。于是“存储正确过滤”与“真正不再暴露过时事实”出现分离。

这个例子成为第38例 `expired_fact_with_history`，并对旧基线重新运行相同完整数据集。修复采用到期来源触发一次上下文失效屏障，令旧历史和相关派生信息失去进入后续 prompt 的资格。该过程保留在开发验证记录中；38例属于开发契约集，尚不是从未用于调试的独立 holdout 测试集。

## 下一阶段：真实模型对照实验

可以扩展独立实验 runner，但不可把尚未完成的设计写成实测成果：

1. 固定匿名化／合成多会话轨迹、角色包、模型精确版本、温度、检索预算与随机种子；冻结测试集，另设开发集。
2. 对照至少包括“无记忆”“现有V2”“本次生命周期修复”“可选检索增强”，保留同样的人格prompt，防策略混杂。
3. 每个真实模型请求记录输入、事实来源ID、trace、输出、provider token usage、首token／完整回复耗时、成本及失败重试；不将本地微基准时间当模型响应时间。
4. 遗忘／过时事实硬违规采用确定性字符串与来源检查；自由改写的事实用人工盲评或经过人评校准的judge。每类正负例随机抽查，报告一致性、分歧与置信区间。
5. 人格一致性评价需使用跨休闲／游戏／工作／拒绝／情绪场景的行为rubric，区分“稳定风格”“过度讨好”“不恰当打扰”“未经证实共同经历”；不能只看embedding相似度或配置hash。
6. 上线阈值应由产品风险与真实bad cases确定。38条开发契约通过是进入下一阶段的门槛，不是“长期伙伴能力已解决”。
