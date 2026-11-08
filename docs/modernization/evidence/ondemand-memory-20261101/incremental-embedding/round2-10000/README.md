# 第二轮冻结版本：10,000 条持久向量复测

源码冻结为 `1eef5cbb6f85703f0350f8708cc86bf84a7e071f`，包含 `structured-value-v1` 的结构化值索引升级。本目录只复测 **10,000 条**；父目录原来的 300、3,000、10,000 条三尺度结果全部保留为首轮历史证据，不能把其中 300 和 3,000 条写成第二轮结果。

## 运行与审计

- 聚合数据：`persistent-embedding-performance.json`。
- 三个实际子进程：同名前缀的 `10000-cold`、`10000-reopen_mutate`、`10000-reopen_verify`，各有独立 JSON 和原始 stdout/stderr log。
- `run-plan.json` 保存运行前命令、冻结 commit、所有 135 个顶层生产 Python 文件和 profiler 的 SHA256。
- `provenance.json` 保存退出码、源文件前后核对、原始产物 hash、三个独立 PID、SQLite 与 CPU 配额。全部源文件 hash 在运行前后相同；profiler 记录的七个核心模块 hash 在三个进程中也相同。

```bash
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 \
python tools/profile_persistent_embeddings.py \
  --source-root /absolute/path/to/E-Moti \
  --model-cache /absolute/path/to/pinned-model-cache \
  --size 10000 \
  --output /absolute/path/to/new-results/persistent-embedding-performance.json
```

实际命令中的 Python 是装有 FastEmbed 的 `/tmp/emoti-retrieval-venv/bin/python`，完整命令保存在 JSON。SQLite 是真实临时数据库，三个子进程共享同一个临时数据库但不共享 Python 对象。所有记录均为六种中文模板构造的合成数据，不代表真实用户活动或真实共同游戏事件。

## 实测结果

| 指标 | 结果 | 分母与边界 |
| --- | ---: | --- |
| 首次编码和索引准备 | 145,896.586 ms | 10,000 条，模型已载入；编码 10,000 条 |
| 首次模型载入 | 454.092 ms | 已缓存固定模型，没有网络下载 |
| 第二进程恢复＋首问 | 385.531 ms | 恢复 10,000 条，正文读取 0、正文编码 0 |
| 第二进程模型载入＋恢复＋首问 | 776.065 ms | 模型载入单列为 390.535 ms |
| 第二进程 RAM 热准备中位数 | 24.148 ms | 只有 3 问，不是 p95 |
| 更正的权威写入 | 3,834.051 ms | 1 次更正，仍包含 JSON 全量写成本 |
| 更正后的语义准备 | 68.425 ms | 正文只读取和编码 1 条，持久写入 1 条 |
| 遗忘的权威写入 | 2,720.570 ms | 1 次遗忘 |
| 遗忘后的语义准备 | 49.588 ms | 正文读取、编码和持久写入均为 0 |
| 第三进程恢复＋首问 | 370.950 ms | 只恢复 9,999 条；正文编码器一旦调用就抛错，实际未调用 |
| 第三进程模型载入＋恢复＋首问 | 738.174 ms | 模型载入单列为 367.225 ms |
| 第三进程完整 wall time | 1,039.352 ms | 包含进程启动、导入、初始化、模型载入、首问、3 问热查询和写结果 |
| 第三进程 RAM 热准备中位数 | 23.117 ms | 只有 3 问 |
| 首次编码 / 第三进程峰值 RSS | 458.668 / 248.754 MiB | Linux `ru_maxrss`，不是纯向量内存 |

第三进程首次查询的缓存读取为 258.509 ms、manifest 为 63.726 ms、矩阵构建及精确搜索为 21.081 ms。时间字段是分阶段计量，不等于完整用户回答时间。首问的 top 4 ID 在三个进程中相同；这只验证持久恢复搜索结果一致，**不是答案正确率**。

首次向量 BLOB 为 20,480,000 bytes；遗忘后为 20,477,952 bytes，9,999 条。内存检索矩阵还占同量级副本。最终 SQLite 文件为 106,414,080 bytes，包含权威 JSON、结构化及 FTS 投影、向量、索引和空闲页，不能全部算作向量存储开销。

## 生命周期断言

脚本退出码为 0，全部断言通过：

1. 冷建编码 N 条、两个新进程编码 0 条；当前有效向量分别恢复 N 和 N−1 条。
2. 更正事务结束时旧 ID 的持久向量立即消失，持久行数为 N−1；后续只编码并写入新修订 1 条。
3. 遗忘事务结束时更正后的来源向量立即消失，后续不编码、不写回该来源。
4. 新旧被撤销 ID 都不出现在发布的旧语义评分中；第三进程也不恢复它们。
5. 全阶段持久缓存错误数和待写数量为 0；三个进程 PID 不同，源码 hash 不变。

`structured-value-v1` 使旧算法投影 generation 变化时，旧向量需要按既定规则失效和重建。这次计时使用新建数据库，验证新版本的正常冷建、相同 generation 跨进程恢复和写后撤销；**不把这组运行表述成旧版本原地升级耗时**。generation 重建行为另由真实 SQLite 协议测试覆盖，见 `storage/structured-fact-values-v1/semantic-protocol-green-junit.xml`（相对于总证据目录）。

## 结论与限制

同模型、同有效来源的重启恢复无需重复正文编码，在该 10,000 条短文本语料上，恢复首问约 0.39 秒，加模型载入约 0.78 秒。首次构建仍需要约 146 秒；算法 generation 或模型版本变化的重建成本也仍存在。

更正总计约 3.90 秒、遗忘总计约 2.77 秒，主要成本仍在权威 JSON 写入。不能只报 68 ms 或 50 ms 的向量维护时间来描述整个操作。每类写入只有 1 个样本，不能据此声称生产 p95 或与首轮差值有统计显著性。

环境为 Linux x86_64、Python 3.12.14、SQLite 3.53.1、FastEmbed 0.9.1、NumPy 2.5.4、ONNX Runtime 1.31.1。模型 `BAAI/bge-small-zh-v1.5` 固定 revision `46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59`，512 维；CPUExecutionProvider、模型 batch64、推理线程 2、OpenBLAS 1。宿主为 AMD EPYC 9V74，容器配额 8 核、8 GiB 内存。与存储、质量评测和全量测试协调错开重型负载，但没有独占宿主 CPU。

本组不评测真实 LLM 回答、人格行为、桌面用户体验、长文本或 Windows 真机。它提供缓存协议、真实编码计数、重启与维护成本的工程证据。
