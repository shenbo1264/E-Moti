# 本轮语义索引实现与验证说明

当前 indexed 路径已增加同一 SQLite 内的持久向量投影，默认开启。完整缓存身份、事务撤销、重启、损坏恢复与独立进程评测见 [持久向量投影](../../../20261101-memory-upgrade/persistent-vector-cache.md)。本目录原有 batch64 JSON 是此前 **RAM-only 实现的历史实测基线**，保留原始文件和 source hash；持久版本另外保存 `persistent-embedding-performance*.json`，不覆盖旧成绩。

第二轮冻结代码 `1eef5cbb6f85703f0350f8708cc86bf84a7e071f` 的 10,000 条追加复测保存在 [round2-10000](round2-10000/README.md)：冷建 145.897 秒、独立进程恢复首问 385.531 ms、纠正遗忘后第三进程恢复首问 370.950 ms；两次恢复均正文编码 0 条。更正仍需 3,834.051 ms 权威写入再加 68.425 ms 语义准备，遗忘为 2,720.570 + 49.588 ms。原三尺度持久化结果是首轮历史证据，第二轮没有重新测量 300 和 3,000 条；不能混合标成同一冻结版本的三尺度结果。

## 实际接口

- `SemanticMemoryRetriever.prepare_indexed(query, store, *, now, scopes=("companion",)) -> Future`：在现有单个后台线程完成增量索引准备和查询编码。
- `candidate_ids(query, *, limit=32, scope=None)`：返回有界的候选 ID。最近邻只是候选；主体、字段、来源、时态和充分性由检索服务进一步判断。
- 原 `prepare(query, entries, *, now, scope)` 和 `__call__(query, entries)` 保留，供旧词法+BGE/RRF 对照和兼容调用。
- `invalidate()` 清空可读查询评分，推进异步 generation。尚未受影响的向量可以保留在 RAM，但必须经过下一次来源清单授权后才能重新参与评分。

## 生命周期

SQLite 中的原始 JSON 文档继续是唯一事实权威；规范化索引、同库持久向量和内存向量均可重建。RAM 向量键包含 memory ID、owner、character 和 `evidence_fingerprint()`；持久投影额外绑定固定模型 revision、512 维、编码协议、scope 和 index generation。指纹包括事实性 metadata、版本、有效时间和来源，不包括访问计数。

首次读取按 2,048 条头信息分页。先以每批 256 条认证并恢复持久向量；仍缺少向量或指纹变化的记录，才通过 `read_indexed_snapshot(memory_ids=..., include_chapters=False, include_profile_sources=False)` 读正文并编码。每次后续准备读取 revision 增量；不把 10,000 条正文重新传给模型。

同一个游标追踪已访问 scope 的并集。首次访问新 scope 会完整读取头信息，但相同指纹的向量保留，因此在陪伴和任务经验之间切换不会重复编码全部数据。未生效来源只保留头信息，到 `valid_from` 后才读取正文并编码；到期、撤回、物理删除 tombstone 和移出允许 scope 均移除相应缓存。

清单分页、正文读取和最终发布都验证 index generation、revision 和 context epoch。写入竞争最多重试三轮，仍不稳定则返回明确异常。generation 改变时重建派生向量；不能把旧索引当成当前事实。

`__call__` 和 `candidate_ids` 还会通过 `current_index_state()` 仅读取元信息，核对 generation、revision、context epoch。当前存储同步还会为兼容旧写入器引起的来源撤销补充 epoch；语义回调仍保留 revision/generation 屏障。检索服务最后仍必须按当前时间、scope、版本做最终认证，语义组件不替代该事务检查。

## 搜索与模型

保持 FastEmbed 与固定 BGE 基线：`BAAI/bge-small-zh-v1.5`，Qdrant ONNX revision `46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59`，CPUExecutionProvider，2 个推理线程。实际测得默认 256 条 passage batch 的内存代价后，本轮显式采用 64 条模型 batch；数据库正文读取仍每批 256 条，二者职责不同。

正文编码输入与旧基线一致：标题、正文、tags。归一化 float32 向量通过 NumPy 矩阵精确计算余弦，最多保留 4 个当前查询范围的矩阵。撤销来源时，其包含的矩阵也清理。本轮未引入 HNSW 或外部向量服务。

旧 `__call__` 为兼容 RRF 保留历史 cosine 门槛和单调分值映射。新的 `candidate_ids` 允许弱相似候选进入后续证据检查，不能解释成正确概率、无答案概率或充分性结论。

## 时间与计数

`status` 提供真实计数：`encoded_entries_total`、`last_encoded_entries`、`query_embed_count`、`payload_rows_loaded`、`manifest_pages`、`prepare_retries`；同时提供 `manifest_ms`、`payload_read_ms`、`passage_encoding_ms`、`query_embedding_ms`、`search_ms`。

当前 `index_prepare_ms = manifest_ms + payload_read_ms + passage_encoding_ms + persistent_cache_read_ms + persistent_cache_write_ms`；历史 RAM-only 记录没有后两项。`prepare_ms` 包含完整后台准备过程（包括检索、Python 调度和上述阶段），因此不能把各阶段之外的开销消失掉。`search_ms` 包含需要时构建候选矩阵和精确搜索；它不是完整 RAG 或 LLM 响应耗时。

## 测试与真实失败案例

`tests/test_incremental_semantic_memory.py` 的计数编码器用于生命周期协议测试；不作为语义质量的证据。真实 BGE 测试单独标出，使用真实 SQLite、固定模型和真实 embedding。

RAM-only 阶段针对性测试为 **25 passed，0 skipped，1.29 秒**：包括新增模块的 21 项协议测试和 1 项真实 BGE 生命周期测试，以及原模块的 1 项普通回调测试和 2 项真实 BGE 测试。命令、原始结果见 `semantic-focused.log`；通过 `EMOTI_BGE_TEST_CACHE=/tmp/emoti-bge-model-cache` 使用已缓存的固定模型，没有以计数编码器替代真实模型测试。

补充审查实际发现并修复了一个派生缓存问题：向量字典移除了忘记的来源，但先前缓存的 NumPy 矩阵仍持有该来源的向量。评分已经不可见，旧矩阵也不会匹配新的来源键，但仍应清理这份派生副本。新增测试先失败，再在来源键集合变化时清空矩阵，随后通过。

另一个真实协议失败案例是兼容旧写入器直接改 JSON：它会让索引 revision 改变，但未必推进 context epoch。根检索的最终指纹校验仍能阻断旧正文，不过单独调用旧 entry 的语义评分可能得到旧分数。新增测试重现后，将回调检查升级为上述三元元信息屏障，旧评分不再可见。

真实性能脚本为 `profile_incremental_embeddings.py`。`incremental-embedding-performance.json` 是默认 256 batch 的先期原型数据，`incremental-embedding-batch64-300.json` 是只调整真实 FastEmbed batch 参数的小规模对照，最终生产 64 batch 三尺度结果保存为 `incremental-embedding-performance-batch64.json`。必须区分这三组，不能将原型的内存或时延作为最终成绩。脚本使用 300、3,000、10,000 条合成中文文本和真实 BGE，测冷编码、三次热查询、一次更正和一次遗忘。它验证首次编码 N 条、热查询 0 条、更正 1 条、遗忘 0 条的实际计数；回答正确性、真实模型生成和桌面交互仍由其他评测承担。

### RAM-only batch64 历史基线

| 当前事实数 | 首次编码与索引准备 | 3 问热准备中位数 | 更正写入 / 随后语义准备 | 遗忘写入 / 随后语义准备 | 进程峰值 RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| 300 | 4.274 秒 | 6.449 ms | 117.874 / 15.509 ms | 80.708 / 7.765 ms | 392.754 MiB |
| 3,000 | 42.445 秒 | 13.027 ms | 1,121.631 / 26.029 ms | 770.761 / 16.519 ms | 482.211 MiB |
| 10,000 | 152.989 秒 | 30.447 ms | 3,812.013 / 57.304 ms | 2,565.698 / 55.396 ms | 552.141 MiB |

三组均真实编码 N 条，三次热查询均重新编码 0 条，更正后只编码 1 条，遗忘后编码 0 条。所有组检查的存储及语义源文件在运行期间 hash 不变。更正与遗忘是单个测量点，不把它们当 p95。语义准备不包括另列的权威 JSON 写入；10,000 条更正端到端不能宣传成 57 ms。

表中首次准备发生在模型载入后。已缓存权重的模型载入另耗 389 / 518 / 362 ms；使用 `local_files_only=True`，没有把模型下载耗时混入，也没有测量首次下载。

模型输出实测为 **512 维 float32**。10,000 组遗忘后剩余 9,999 条向量，实际数组占 20,477,952 bytes，缓存搜索矩阵另占同样字节数。原型默认 batch256 的 RSS 是 850.6 / 1,175.1 / 1,203.0 MiB，本轮固定 batch64 后的结果如表；比较包含其他最终存储优化，单独的 300 条 batch 参数对照另存原始文件。

文本由六种中文模板构造，长度中位数为 62 / 63 / 63 字，最大 65 / 66 / 66 字；不是私有用户聊天或长文档。每个规模独立进程，FastEmbed 2 个推理线程、OpenBLAS 1 线程。协调避开了重型并发，但没有独占 CPU；一次约 0.2 秒 Qt 取消回归可能与冷编码重叠。三问中位数只描述本次样本，不是生产时延 SLO。

存储最终修复后又运行了语义与生成入口的联合检查：`semantic-generation-focused-final.log` 为 **36 passed，0 skipped，1.41 秒**，由上述 25 项语义测试与 11 项生成入口契约测试组成。真实生成 API 仍未运行；生成入口用受控 transport 的测试不计入模型效果。

持久化实现与存储最终 epoch/typed-literal-v2 补齐后，`persistent-semantic-focused.log` 为 **66 passed，0 skipped，2.36 秒**。新增 30 项持久缓存测试包含 29 项真实 SQLite/受控编码器协议检查和 1 项真实 BGE 独立进程恢复；与原来 25 项语义和 11 项生成入口测试合并运行。独立进程恢复时禁止 passage 编码器运行，仍能完成查询。

## 工程限制

- RAM-only 基线每次重启需重新编码，这个缺口已由同 SQLite 持久投影补齐。首次建立索引、模型/编码版本改变或 index generation 重建仍需要编码；不能把重启命中延迟当成全新用户的冷建延迟。
- 同一个 optional encoder 载入后会有显著 ONNX/NumPy 内存占用。关闭语义功能仍可走结构化和词法路径。
- 常规写入的原始 JSON 事务仍有全量成本，本组件只减少语义重编码和读取正文的成本。
- indexed 评分发布前受版本检查保护；应用必须遵守 `prepare` 完成后消费并在最终上下文提交前再次验证来源的契约。
