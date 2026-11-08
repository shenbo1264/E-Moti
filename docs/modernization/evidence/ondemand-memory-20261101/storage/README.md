# SQLite 实测证据

本目录保留实际执行的原始 JSON。基准脚本位于 `tools/benchmark_memory_index.py`，完整解释见 `docs/modernization/20261101-memory-upgrade/storage-index-v1.md`。

| 文件 | 用途 |
| --- | --- |
| `storage-index-round2-performance.json` | 最新第二轮冻结 `1eef5cb` 的 300/3000/10000 条完整新实现复测，含 structured-value-v1 和公共更正补足 |
| `storage-round2-comparison.json` | 旧 299 前置基线与最新 1eef 的同语料/分母对照；旧版数据沿用此前真实执行结果 |
| `storage-round2-run-provenance.json` | 第二轮原始命令、环境、时间、8 个新版及 5 个旧版源码 SHA 对应提交核验、相同脚本及语料核验 |
| `storage-document-final-baseline-performance.json` | 最终窗口重新执行的 300/3000/10000 条前置基线，实际源码逐文件匹配提交 299a0aa |
| `storage-index-final-performance.json` | 最终窗口重新执行的 300/3000/10000 条新版，含 raw epoch 与 typed-literal-v2，实际源码逐文件匹配冻结提交 f7a4e23 |
| `storage-final-comparison.json` | 最终两文件按同语料 SHA、同四条来源、同分母生成的完整对照 |
| `storage-final-run-provenance.json` | 两个独立进程的原始 argv、PYTHONPATH、解释器、时间、执行顺序、脚本 SHA 及源码对应提交的核验 |
| `storage-document-baseline-performance.json` | 较早检查点的前置基线，保留历史数据 |
| `storage-index-performance.json` | 较早检查点：包括 FTS rowid、查询计划和 raw-digest 优化，早于最后的旧 writer epoch 补屏障 |
| `storage-comparison.json` | 较早两个检查点按相同语料 SHA 和规模计算的对照，不混入最终表 |
| `storage-index-prototype-fts-scan-bad-case.json` | 初版每条新增先扫描 UNINDEXED memory_id 删除 FTS 的性能问题；仅完成 300/3000，10000 提前停止，不是最终结果 |
| `storage-index-prototype-fts-join-bad-case.json` | FTS rowid JOIN 被 SQLite 反向执行，导致重复 MATCH；保留完整三个规模的真实坏例 |
| `storage-index-prototype-full-sync-write-bad-case.json` | 全量同步投影导致 10000 条更正达到 8931.84ms 的写回退；之后通过 raw-digest 增量同步修复 |
| `storage-index-post-raw-barrier-smoke.json` | epoch 修复后的 300 条成本检查：读 9 次，写 1 次，不能代替正式三尺度结果 |
| `raw-writer-regression-junit.xml` | epoch 修复后 162 项相关回归的实际 pytest JUnit 输出 |
| `raw-writer-revocation.md` | 在途旧回复和历史回流的真实失败复现、修复边界与 red/green 记录 |
| `structured-fact-values-v1/` | f7 之后第二轮结构化事实值补足的 RED/GREEN、独立 store 与 lifecycle JUnit、执行命令和源码 SHA；不是 f7 三尺度性能的组成部分 |

最终两组均记录 `storage_source_unchanged=true`，包括执行前后相关源码 SHA。先执行新实现，再通过另一个进程执行旧实现；窗口内团队没有同时运行 embedding、质量测评或全量 pytest，硬件仍为共享 Linux 容器。旧实现实际从 `E-Moti-memory-integrity/src` 加载；新实现从 `E-Moti-ondemand-memory/src` 加载。路径、Python/SQLite/CPU 信息、全部样本及 UTC 时间保存在各 JSON 中。前置版本逐文件核验等于 `299a0aa568c90525e6a6a90ce01dbbf80bfaefcb`，新版逐文件核验等于 `f7a4e23a0f7b207fc68c1719c2217ac740416344`；不是把最早 PR #6 当成已经含本轮改进的基线。

开发过程中的三尺度检查点和 epoch 修复后的 300 条 smoke 都完整保留，没有覆盖。此前 smoke 的写入分母仅为 1；f7 的完整三尺度使用 final 文件名，当前最新代码的结果使用 round2 文件名。f7 的 10000 条 snapshot p50 为 1556.339 → 1.207ms，snapshot + finalize 为 1812.808 → 34.729ms，更正为 3916.777 → 4280.979ms。这组作为历史冻结证据保留，最新具体数字见下文和技术文档第 9.1 节。

复现时用两个独立进程执行同一脚本，通过 `PYTHONPATH` 分别指定前置版本与升级版本的 `src`。基准总是在新的临时目录创建数据库，不接受用户存档路径。每个规模热读取/提交为 9 次，更正/遗忘为 3 次；冷建索引为 1 次，不能把单次冷建数据报告成稳定 p95。

语料为 300、3000、10000 条合成但真实写入 SQLite 的记录；正文 77–116 字、中位数 96.5 字，元信息包含主体、字段、来源和独立角色。读取对照选同样 4 个证据 ID。更正序列追加 3 条修订，并保留现有逻辑退休语义。词法查询的共同词项有大量匹配，用于测量 FTS 候选扫描与排名；它不是质量测评中的正确答案比例。

本组不运行 LLM、不衡量人格行为、不含 embedding 编码或持久向量缓存初始化。Python 分配峰值使用单独的 tracemalloc 调用，未混入正常延迟样本，也不代表包含 SQLite C 内存或 embedding 模型的全进程 RSS。环境是共享 Linux 容器，没有模拟突然断电、真实 Windows 桌面交互或安全物理擦除。

第二轮增量新增 `structured-value-v1` 算法标识，使 object/嵌套数组事实值可被完整保存与指纹覆盖，并使 0/false 在索引中保留字面值。27 项通用测试先在 f7 得到 20 failed / 7 passed，再在补丁后 27 passed；独立 store 回归 67 passed、2 collection skipped（该解释器没有 numpy），router 接口落稳后的 controller/service/lifecycle 回归 59 passed。具体分母和环境见子目录 provenance。上面的 final 文件名保留原样以便追溯，指的是 f7 冻结检查点，第二轮的正式复测另外保存在 round2 文件中。

后续补齐公共 `correct()` 与口头遗忘的类型契约：21 项新增 RED 为 14 failed / 7 passed，JSON 转义值另有 1 项 RED；最终结构化值和纠正两文件合计 **49 passed in 0.67s**。既有纠正、相册和普通聊天回归为 103 passed、2 项长链测试 deselected；实际使用 numpy 环境重跑两文件语义缓存协议为 **50 passed in 1.15s**，2 项真实 BGE 测试明确 deselected。测试数有交叠，不能把各轮分母相加成独立测试总数；所有 JUnit、命令、阶段边界和冻结源文件 SHA 都保存在该子目录。

第二轮完整存储测量使用冻结 `1eef5cbb6f85703f0350f8708cc86bf84a7e071f`，实际 8 个相关源码 SHA 均匹配、前后不变。脚本及 300/3000/10000 三个语料 SHA 与前置 299 基线逐项相同；新实现 19:34 UTC 独占团队性能窗口，旧基线使用 18:43 UTC 已执行结果，未重复运行。全样本均在 JSON 中；四条证据的 snapshot p50 为 1.174/1.321/1.166ms，读取 + finalize 为 6.023/17.631/31.550ms，更正为 121.674/1092.484/4311.920ms，遗忘为 110.963/1059.372/3609.637ms。对应组合读取的旧299/新1eef比值约 9.28/27.37/57.46 倍；只描述存储路径，不是模型响应或整机体验的加速倍数。更正继续有 O(N) 写入成本，写入分母仅 3，不把共享环境波动解读为新补丁普遍提升了写性能。
