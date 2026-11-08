# Windows 存储性能复测

测量使用独立临时 SQLite 档案，未读取用户存档。`long-source` 是公开脚本生成的合成负载：摘要约 180–240 字符，来源原文 512/1024/2048 字符；它覆盖较长输入，不代表真实用户长度分布。旧文档后端来自 `memory-legacy-baseline@1e10b715` 的 prerequisite-only 重建，不能视为原始 `299a0aa` 提交。

## 已实施

- Windows 峰值进程内存采用已安装 `psutil` 的 `peak_wset`（字节），其他平台沿用标准库 `resource`；共用 `tools/memory_profile_metrics.py`。
- 测量脚本显式关闭 SQLite 连接，修复 Windows 临时档案清理时的 `WinError 32`。
- `_clean_text` 用 `str.translate` 保持原控制字符和空白规范化语义，减少逐字符 Python 循环。
- `_retire` 只更新命中的原始记录，保留无关记录和未知扩展字段；避免撤销时再次规范化整库。
- `service.correct` 通过索引读取目标卡片和同次读取的 epoch；事务写入继续核对 epoch。它支持未来生效及零置信度卡片的管理操作。
- 撤销来源检查同时识别原来源和物理删除后的不可逆摘要；普通纠错可以沿用原来源，已物理删除的来源不能重新写入。

## 同负载结果

单位 ms，读取及组装各 5 次，更正/遗忘各 3 次，表中为 p50。共享 Windows 运行环境，没有独占 CPU；此结果不能作为生产 p95 承诺。

| 条数 | 旧文档读取 | 索引读取（修改前） | 索引读取（修改后） | 更正前 | 更正后 | 遗忘后 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 300 | 39.90 | 1.22 | 1.57 | 129.84 | 60.79 | 52.30 |
| 3,000 | 402.79 | 1.41 | 1.79 | 1331.81 | 863.25 | 724.44 |
| 10,000 | 1557.03 | 1.12 | 2.43 | 4094.88 | 2923.77 | 2400.99 |

读取加最终 recall 写回在三个规模分别为 11.44/59.20/237.95 ms；修改前为 12.48/42.18/123.19 ms。大规模这项测量退化，不能用更正加速概括所有操作都更快。单次四条读取的 Python tracemalloc 峰值约 85 KB；它不等同进程峰值 RSS。

3,000 条 `service.correct` 的 cProfile 显示 `_entries` 从 3 次降为 1 次，`from_dict` 从 9002 次降为 3004 次。含分析器开销的更正总时间从 6914.7 降为 1063.6 ms，遗忘从 4949.3 降为 1258.5 ms；这些数字用于定位成本，不能当作实际交互延迟。

## 权威存储决定与剩余问题

保持同 SQLite 内的 `memory_state.payload` 为唯一权威，索引和向量缓存继续可重建。本轮没有迁移用户档案。重复规范化已显著减少，但更正仍解析一次全库并写整个 JSON，10,000 条更正仍约 2.9 秒，最终 recall 写回也随规模增长。行式权威迁移有明确性能动机，但需连同事务、版本、来源撤销和旧档案回退一起实施；本轮不能宣称存储写入优化完成。

## 真实 BGE 与跨进程恢复

实际运行 `BAAI/bge-small-zh-v1.5`，revision `46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59`，512 维，CPUExecutionProvider，2 个推理线程。每个规模使用三个不同进程，最后一个进程将 passage 编码调用设为立即失败以验证确实只恢复缓存。

| 条数 | 冷索引首查询 ms | 重启首查询 ms | 更正遗忘后重启 ms | 三阶段 passage 编码数 | 三阶段峰值 RSS MiB |
| --- | ---: | ---: | ---: | --- | --- |
| 300（生产修改前） | 8825.95 | 25.31 | 24.75 | 300 / 0 / 0 | 822.91 / 220.67 / 220.40 |
| 3,000（生产修改后） | 128010.46 | 149.42 | 180.42 | 3000 / 0 / 0 | 852.86 / 307.85 / 221.65 |
| 10,000（生产修改后） | 363497.64 | 666.93 | 671.14 | 10000 / 0 / 0 | 925.65 / 572.73 / 247.50 |

3,000/10,000 条的更正分别写入 571.54/1692.11 ms，随后各仅编码 1 条，索引准备 27.86/97.09 ms；遗忘分别写入 420.39/1475.13 ms，随后编码 0 条，索引准备 17.58/53.10 ms。三个阶段均断言撤销后的缓存行不存在、恢复数量正确、源代码在测量期间未变。10,000 条冷建约 6 分钟，不能用缓存命中时延掩盖初次准备成本。这里没有进行 BGE 语义质量或 LLM 生成验收。

## 复现与证据

从当前 worktree 运行前显式设置 `PYTHONUTF8=1` 和 `PYTHONPATH=<当前 worktree>/src`，避免 Windows 管道编码错误或导入其他 editable checkout。BGE 测量另外设置 `OPENBLAS_NUM_THREADS=1`、`OMP_NUM_THREADS=2`，使用本机已有模型权重缓存。

脚本：`tools/benchmark_memory_index.py`、`tools/profile_memory_upgrade.py`、`tools/profile_persistent_embeddings.py`。

本机原始记录位于 `artifacts/codex_handoff/`：

- `storage-document-long-baseline.json`
- `storage-index-300-long-baseline.json`、`storage-index-large-long-baseline.json`
- `storage-index-long-after-r2.json`
- `storage-write-profile-3000-baseline.json`、`storage-write-profile-3000-after-r2.json`
- `persistent-bge-300-long-baseline.json`、`persistent-bge-3000-long-after.json`、`persistent-bge-10000-long-after.json` 及各阶段原始 JSON/log。早期原始报告中的 `corpus.source` 沿用 six-template 标签；实际 `corpus.profile=long-source` 和脚本参数才是本次语料标识。工具已修正文案，保留早期记录。
- 原 Windows 导入错误、连接清理错误、未知字段被改写失败及首次错误导入路径日志均保留，未覆盖为成功记录。

本页仅报告存储与缓存工程测量；模型回答、人格行为和真实桌面交互需要各自的验收记录。
