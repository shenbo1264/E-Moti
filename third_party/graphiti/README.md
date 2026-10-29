# Graphiti 排序融合代码来源

## 来源与许可证

- 上游：[getzep/graphiti](https://github.com/getzep/graphiti)。
- 固定版本：`5c27edfa8d3e0f49b2571bcebb4261bcc89ee037`（2026-10-25 核验）。
- 源文件：[`graphiti_core/search/search_utils.py` 的 `rrf` 函数，第 1786–1802 行](https://github.com/getzep/graphiti/blob/5c27edfa8d3e0f49b2571bcebb4261bcc89ee037/graphiti_core/search/search_utils.py#L1786-L1802)。
- 源文件 blob SHA：`b1570343331959607e9e2ea3a8b38082c3c8e171`。
- 许可证：Apache-2.0；本目录 `LICENSE` 保留上游完整许可证。
- 原版权声明：2024, Zep Software, Inc.，已在适配后的模块中保留。
- 已检查该版本的根目录与递归文件树，没有 `NOTICE` 文件。

## 实际复用范围

`src/guanghe_companion/memory_fusion.py` 复制适配上述无外部依赖的小型 RRF 实现，复用了倒数排名累加与稳定降序排序逻辑。没有引入 Graphiti 的图数据库运行时、驱动、提示词、遥测或模型客户端；不需要安装 Graphiti 包。

E-Moti 的适配内容：

1. 排名从 1 开始，默认常数为 60；上游排名从 0 开始、默认常数为 1。
2. 拒绝非正整数常数，包括布尔值。
3. 每个检索器内部先去重，重复 ID 不额外加分，也不挤占后续排名。
4. 返回 `(memory_id, score)` 对，不使用上游的 `min_score` 参数；有效性和结果预算由调用者处理。
5. 同分时按首次出现顺序稳定排列，分数只是排序信号，不代表事实置信度。

调用者必须先过滤角色、状态、有效期和来源依赖，再融合检索结果。RRF 无法修复过时事实、执行遗忘或证明记忆相关。没有向量模型时仍可独立使用词法检索。

## 验证

`tests/test_memory_fusion.py` 覆盖空输入、多检索器共同命中、重复条目、稳定同分、排名常数与非法参数。实现前运行测试，得到预期的 `ModuleNotFoundError`；实现后再次运行。集成与全量测试结果在升级验证记录中统一报告。
