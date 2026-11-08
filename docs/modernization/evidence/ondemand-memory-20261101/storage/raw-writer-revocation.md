# 旧 writer 的 epoch 漏口：真实失败与修复记录

## 实际复现

2026-11-01，在真实临时 SQLite 和 `PluginEnabledCompanionController` 中写入一条有明确来源与结构化字段的饮料偏好，准备“我喜欢喝什么”的 `HostDialogueTicket`。已构建的 prompt 确实包含“紫苏冰饮”。随后通过兼容 `_document()` 把该行 `deleted=True`，不主动改变 `context_epoch`，再把确定性的旧 speech 事件交给 `complete_host_dialogue()`。

修复前实际输出：

```text
old_prompt_has_fact True
state (same_generation, 2, 0) (same_generation, 3, 0)
current_guard True
delivered_old_fact True
history [('user', '我喜欢喝什么'), ('assistant', '你喜欢紫苏冰饮。')]
```

这里没有调用真实 LLM，也没有测其回答品质。事件用于检验一个真实在途生成请求已经取得旧事实后，最终投递与历史写入能否拦住过期结果。直接 SQL 更新 `memory_state.payload` 也产生同样问题。检索时的 fingerprint 和 revision 检查已经正确，controller 和最近对话历史使用 epoch，因此仍可能接纳旧内容。

## 测试先失败，再修复

首次新增 `tests/test_raw_writer_revocation.py`，在改生产代码前运行：

```text
20 failed, 3 passed in 0.61s
```

失败包括 7 种旧来源变化分别经过 document/SQL 两个入口（14 项），document/SQL 在途回答未拒绝（2 项），document/SQL 已存在的旧历史回流（2 项），dirty SQL 在旧 epoch 读取/写检查前未修复，以及 epoch 被回退。已有普通新增/访问、正常纠正到期和事务回滚 3 项通过。

在 `sync_projection()` 检测旧来源语义变化/删除后，若 canonical epoch 没有超过旧 header，则在同一个事务里把 canonical JSON 和 projection 的 epoch 一起推进。JSON1 只补 epoch，不做第二轮 Python 全量序列化。`memory_document()` 在 yield 前也 reconcile 既有 dirty，使读取旧 epoch 和基于旧显示状态的写入都先经过该屏障。

首次修复后：

```text
23 passed in 0.70s
```

随后增加纯来源化章节写入不误推进 epoch 的回归，更新 3 个旧测试中“raw 改动后 epoch 不变”的过时断言，并保留“即使给新 epoch，旧来源指纹仍不能通过”的独立检查。最终命令：

```bash
env PYTHONPATH=src \
  LD_LIBRARY_PATH=/tmp/emoti-pr6-libs/root/usr/lib/x86_64-linux-gnu \
  QT_QPA_PLATFORM=offscreen \
  /tmp/emoti-pr6-review-venv/bin/python -m pytest \
  tests/test_raw_writer_revocation.py tests/test_indexed_memory_store.py \
  tests/test_memory_context_snapshot.py tests/test_memory_lifecycle.py \
  tests/test_memory_adversarial.py tests/test_memory_maintenance_budget.py \
  tests/test_emotional_memory.py -q --tb=short \
  --junitxml=docs/modernization/evidence/ondemand-memory-20261101/storage/raw-writer-regression-junit.xml
```

实际结果：**162 passed in 4.67s**。其中本次新增文件包含 24 个测试实例。机器可读结果保存在同目录 JUnit 文件；项目全量验收由主集成记录单独报告，不能用这 162 项代替全部项目测试。

在此检查点之后，主集成补充受信旧饮品字面事实的读取规则，投影 `ALGORITHM_VERSION` 的 `typed-literal-v1` 升级为 `typed-literal-v2`。新增 `test_literal_parser_v1_projection_rebuilds_without_changing_authority` 先实际失败于 generation 未改变，升级后 **1 passed in 0.09s**；确认重建后的新事实索引可用，原始正文、空 metadata 与 epoch 不变。这个单独迁移用例不反向计入前述 162 项 JUnit。

## 不会误触发的情况

正常新增来源、访问计数、正常纯章节/画像变更不因此撤销当前对话。已有纠正、遗忘、到期入口正确推进 epoch 时不再额外推进。异常回退的 epoch 被保持为之前已知值。事务失败时 canonical 与 projection 同时回滚。

旧 writer 更改已有正文、事实性 metadata、scope、deleted、retired 集合、expired 指纹集合，或者物理移除旧条目，都会让 controller 拒绝在途旧结果，并使旧 epoch 的对话档案不再进入上下文。档案仍可以由用户查看，修复没有删除真实历史。

## 性能证据的版本边界

最初的 300/3000/10000 条检查点在此修复前已经完成并保留源码 SHA。修复后先补运行同脚本的 300 条检查（9 次读、1 次纠正与遗忘），结果见 `storage-index-post-raw-barrier-smoke.json`：热快照 p50 1.212ms、快照加 finalize p50 5.608ms、更正单次 111.528ms。运行前后源码一致。该文件始终只是一份有限成本检查，不把单次写入当稳定 p95。

最终冻结 raw epoch、typed-literal-v2 与相关源码后，又在独立静默窗口实际重跑了**新旧两套全部三个规模**，读 9 次、写 3 次。最新结果为 `storage-index-final-performance.json`、`storage-document-final-baseline-performance.json`，命令和对应提交核验见 `storage-final-run-provenance.json`。最终 10000 条快照加 finalize 为 1812.808 → 34.729ms；更正为 3916.777 → 4280.979ms。旧检查点和 smoke 没有被覆盖，最终对比也没有混用不同版本的最小值。
