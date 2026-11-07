# 2026-11-07 真实评测证据

本目录用于审阅 [实现与结果](../../20261101-memory-upgrade/completion-20261107.md)。全部人物、物品与活动均为隔离合成数据或公开 benchmark 人物，不是用户存档；不导入生产记忆。

| 文件 | 内容 |
| --- | --- |
| `local-evaluations.zip` | 生命周期修改前后、人格回答与 AI 复核、实际格式失败重放、性能和余额阻塞记录；含原始 prompt、响应、usage |
| `local-evaluations-manifest.json` | 上述包的逐文件列表与来源 |
| `retrieval-evaluations.zip` | 第九至第十三相关原始检索、最终提示词、真实生成、评分、输入纠正与中间失败；公开单题试跑及 MIT 许可证 |
| `retrieval-evaluations-manifest.json` | 上述包的逐文件列表与来源 |
| `formal-public-partial.zip` | 公开714题部分运行的154条生成完成回答、失败、逐请求记录、检查点描述、恢复说明及 MIT 许可证 |
| `frozen-source-patches.zip` | 两份源码与测试补丁，依次从 `523150e` 重建中间 `8b9efe6` 和最终 `d3c55d2` 的生产内容 |

ZIP 保留原目录结构，排除运行档案、SQLite、模型缓存和本机设置。真实凭据匹配扫描通过。完整运行档案仍保留在本机 ignored 工作目录，因此证据 ZIP 可供核查，但不能单独恢复全部回放状态。

新版本真实模型验收因 HTTP 402 余额不足未完成。已完成请求不等于答案正确，未完成/未评分项不能从分母删除。正式公开批次生产为 `523150e`；后续修复冻结为 `d3c55d2`。不得混合两版本成绩。

第十二原版查询时钟不被工具读取，纠正版本只调整明确时钟所在层级；第十三原版缺必填时间字段，修正版只补未变更来源的记录时间。原始输入与失败均保留。第十三没有完成新的泛化质量评价。

`full-pytest-d3c55d2.log`：2589 passed、9 skipped、3 warnings。`final-tool-tests.log`：随后评测工具28项通过。`ui-isolated-final.log`：离屏页面5项通过。38条开发记忆契约结果在检索证据包内。这些工程验证与真实模型效果分别报告。
