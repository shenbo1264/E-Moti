# 记忆核心对抗审查与修复记录

核验日期：2026-10-25。本记录针对本批增量实现的实际源码与确定性回归测试，不代表已通过真实模型、Windows 真机或断电测试。

## 发现与已修复行为

| 可复现问题 | 影响 | 本批修复与对应测试 |
|---|---|---|
| `save_memories` / `upsert_memory` 接受 `deleted=True`，但未写撤回记录；随后写回旧对象就能重新召回 | 低层公开写入口可绕过遗忘，也不推进上下文 epoch | 两个入口共用 `_write_memory`，删除统一进入 `_retire`，保存 ID/来源撤回记录并使派生物失效。`test_public_deleted_write_creates_durable_revocation` |
| 删除原事实后，批量保存同来源、不同 ID 的对象仍被召回 | 事件或迁移数据改变 ID 后可复活 | 批量与单条写共用来源检查，覆盖 source ID、legacy key、plugin event/proposal ID；同批删除先处理。`test_batch_save_cannot_replay_forgotten_origin_with_new_id` |
| `confidence=NaN` 被裁成 1；`valid_until=NaN` 被清洗成 0 | 不可信值变成高置信度，失效时间变成永久有效 | 归一化前检查生命周期数值有限性；拒绝 NaN、正负 Infinity、布尔值。JSON 读取拒绝非标准常量和浮点溢出。`test_nonfinite_lifecycle_values_are_rejected_before_persistence`、`test_legacy_nan_expiry_fails_closed_and_preserves_original` |
| 更正或遗忘只在调用前检查 epoch，检查与保存间可插入另一次修改 | 过期操作覆盖较新的用户决定 | `replace_memory`、`forget_memory` 在 SQLite 写事务内验证可选 `expected_epoch`，Service 与相册调用方透传。`test_revocation_writes_check_epoch_inside_transaction` |
| 更正允许复用已有或已撤回的 ID | 重复主键语义；原事实先退休，替换条目又被旧 tombstone 隐藏 | 更正必须使用未占用、未撤回的新 ID，失败时原事实保持有效。`test_correction_cannot_reuse_an_existing_or_retired_id` |
| 修改画像称呼、边界等内容未推进 epoch | 已组装上下文或异步回包可能继续使用旧画像 | `save_profile` 在同一事务内检查 epoch，并对除 `updated_at` 外的内容变化推进 epoch；单纯时间更新保持 epoch 不变。对应三个 profile 回归测试 |
| SQLite 存在但主表或状态行丢失时，重新导入保留的旧 JSON | 已遗忘的旧档事实重新出现 | 首建与已有权威状态分离；缺行、缺表、预置空数据库均拒绝回源。`test_missing_authoritative_state_never_reimports_forgotten_legacy_data`、`test_preexisting_empty_database_is_not_treated_as_first_run` |
| 整个 SQLite 文件丢失时，无法区分首次运行与状态丢失 | 旧 JSON 再次成为导入源 | 增加不含事实的初始化 receipt；receipt 存在但 DB 缺失时拒绝自动导入。上述 missing-state 测试包含删除整个 DB 的场景 |
| schema=1 的合法 JSON 内存在无效 row 或非列表 entries，原迁移静默跳过并提交 | 用户修正旧文件后也不会再次导入被跳过条目 | 结构与逐条记录验证失败直接报告 `MemoryStorageError`；不创建数据库，源文件保持原字节，修复后可重试。`test_invalid_legacy_rows_fail_without_committing_and_can_be_repaired` |
| 旧版非默认 owner 也写共享角色目录，新目录隔离后看不到原存档 | Alice 等已有 owner 的历史在升级后表现为丢失 | owner 专用旧文件不存在时，首次迁移读取共享旧文件并按 owner/character 筛选；专用文件优先，已初始化后不再回源。四项 owner 迁移回归覆盖 Alice、Bob、local_user 与忘记后重启 |
| 旧章节把另一 owner 的来源放在第 17 位，解析时被 16 条显示上限截掉 | 部分来源检查误判为同 owner 章节 | 迁移核对完整原始来源；归一化丢失依赖的章节留在旧档、不导入。`test_shared_chapter_cannot_hide_foreign_source_beyond_display_limit` |

更正与忘记含义保持区分：用户忘记一个旧版本时，会撤回该版本的后续更正链；一般批量保存已退休旧版本不会再次撤回其仍有效的新版本。更正后的有效事实可以保留原始来源，普通重放不能借同一来源恢复被忘记的旧内容。

## 存储与恢复边界

权威内容、来源、版本、画像证据、章节证据、撤回记录和上下文 epoch 存在一个 SQLite 文档内。日常修改使用 `BEGIN IMMEDIATE`；先读取当前状态，再验证和提交，避免“最后一个 JSON 文件覆盖前一个进程”式更新丢失。

第一次初始化先严格读取和验证旧 JSON，再创建 SQLite。初始文档单独提交后才开始调用者的修改事务，因此第一次用户操作失败不会把初始化留在不可用状态。坏 JSON 在创建 DB 前失败；修正源文件后可以重试。旧 JSON 保持原字节不变。

旧版曾将多个 owner 写入同一角色 `memory_v2` 目录。迁移到新的 owner 命名空间时，按文件优先读取 owner 专用旧 JSON；专用文件不存在时才使用共享目录对应文件。事实逐条验证后只导入当前 owner 和角色；画像 owner 不匹配时不导入。章节要求完整来源均属于当前 owner、在迁移时有效，且已有指纹没有不匹配。旧章缺少版本指纹时仍不补造证据，只保留可检查历史，模型上下文继续拒绝无充分来源证据的派生文本。

`memory_state.initialized` 只保存 schema 与 initialized 标志，没有记忆正文、摘要或画像。初始化先写入并 `fsync` receipt，再提交初始文档；若在最后一步中断，下一次启动会保守报告状态缺失，不自动重新导入。已有有效数据库也会补写 receipt。备份与恢复时应保留整个角色 `memory_v2` 目录；不要以删除 receipt 来处理错误，应该先查验或恢复权威数据库。

这是一条避免旧 JSON 自动复活的防线，不能抵抗同时删除数据库和 receipt、恢复过时的完整备份或任意手工篡改本地文件。本批遗忘属于当前运行时的逻辑撤回；旧 JSON、备份和底层 SQLite 页没有获得“正文物理抹除”的承诺。

## 实际验证

先运行新增失败测试，再改生产实现。第一组得到 16 个预期失败，包含公开删除入口复活、同源重放和非有限数值。存储损坏补充组得到 5 个预期失败，另两个首次失败后重试场景保持通过。迁移补充组先得到 8 个失败及 1 个已有通过，随后另用一个失败测试确认并修复章节来源显示上限造成的 owner 检查绕过。

最终集中命令：

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_memory_adversarial.py \
  tests/test_memory_lifecycle.py \
  tests/test_emotional_memory.py \
  tests/test_emotional_memory_service.py \
  --disable-warnings
```

结果为 **81 passed in 0.72s**，其中新增对抗文件 40 项。原始命令输出保存在 [`evidence/memory-core-focused.txt`](evidence/memory-core-focused.txt)。全工程测试、相册 TOCTOU、上下文/异步回包与 Memory Benchmark 的结果由统一验证记录报告，不能用这里的 81 项替代。

在 300 条存档的本机单次测量中，共用写入口曾引入逐条重新解析/序列化的内部性能回退，发现后已改为事务内一次解析和最终一次序列化：

| 操作 | 本轮中间实现 | 修正后实现 |
|---|---:|---:|
| 批量保存约 300 条 | 4.318 s | 0.027 s |
| 300 条存档中强化一条 | 8.473 s | 0.065 s |

这里比较的是本轮中间实现与修正结果，不是原仓库的性能基线，也不是跨设备性能保证。没有新增向量库或第三方服务依赖。

## 后续验证

已验证的是可重复的状态与上下文契约。Windows 文件系统并发、进程被杀、真实断电和实际模型对旧内容的改写泄露尚需后续环境验证。恢复工具应在副本中检查数据库、schema、receipt 与旧档来源，再让用户明确选择恢复点；不能为了“自动修好”退回已失效的旧 JSON。
