# 冻结五路线结果（由原始 JSON 汇总）

实际 SQLite、CPU embedding 和最终 provider prompt；未发送生成请求。下表不表示实际模型答案、人格行为或真实用户成功率。

| 规模 / split | 方法 | 问题数 | 交付 Recall | 严格支持交付 | 未知误注入 | 路由一致 | 多余检索 | 错误 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 300 / holdout | none | 48 | 0.0000 | 0/33 | 0/10 | — | 0/5 | 0/48 |
| 300 / holdout | lexical | 48 | 0.6212 | 7/33 | 9/10 | — | 5/5 | 0/48 |
| 300 / holdout | bge_rrf | 48 | 0.6970 | 6/33 | 10/10 | — | 5/5 | 0/48 |
| 300 / holdout | routed | 48 | 0.2121 | 7/33 | 0/10 | 14/48 | 4/5 | 0/48 |
| 300 / holdout | layered | 48 | 0.2121 | 7/33 | 0/10 | 14/48 | 4/5 | 0/48 |
| 300 / development | none | 108 | 0.0000 | 0/52 | 0/29 | — | 0/27 | 0/108 |
| 300 / development | lexical | 108 | 0.7308 | 37/52 | 17/29 | — | 27/27 | 0/108 |
| 300 / development | bge_rrf | 108 | 0.7308 | 37/52 | 20/29 | — | 27/27 | 0/108 |
| 300 / development | routed | 108 | 0.9808 | 51/52 | 0/29 | 108/108 | 0/27 | 0/108 |
| 300 / development | layered | 108 | 0.9808 | 51/52 | 0/29 | 108/108 | 0/27 | 0/108 |
| 300 / validation | none | 36 | 0.0000 | 0/19 | 0/11 | — | 0/6 | 0/36 |
| 300 / validation | lexical | 36 | 0.7632 | 14/19 | 9/11 | — | 6/6 | 0/36 |
| 300 / validation | bge_rrf | 36 | 0.7632 | 14/19 | 11/11 | — | 6/6 | 0/36 |
| 300 / validation | routed | 36 | 0.8421 | 16/19 | 0/11 | 35/36 | 1/6 | 0/36 |
| 300 / validation | layered | 36 | 0.8421 | 16/19 | 0/11 | 35/36 | 1/6 | 0/36 |
| 300 / holdout | none | 48 | 0.0000 | 0/33 | 0/9 | — | 0/5 | 0/48 |
| 300 / holdout | lexical | 48 | 0.5758 | 3/33 | 6/9 | — | 5/5 | 0/48 |
| 300 / holdout | bge_rrf | 48 | 0.5758 | 2/33 | 8/9 | — | 5/5 | 0/48 |
| 300 / holdout | routed | 48 | 0.5455 | 18/33 | 0/9 | 46/48 | 1/5 | 0/48 |
| 300 / holdout | layered | 48 | 0.5455 | 18/33 | 0/9 | 46/48 | 1/5 | 0/48 |
| 3000 / development | none | 18 | 0.0000 | 0/13 | 0/3 | — | 0/2 | 0/18 |
| 3000 / development | lexical | 18 | 0.6154 | 8/13 | 2/3 | — | 2/2 | 0/18 |
| 3000 / development | bge_rrf | 18 | 0.6154 | 8/13 | 2/3 | — | 2/2 | 0/18 |
| 3000 / development | routed | 18 | 1.0000 | 13/13 | 0/3 | 18/18 | 0/2 | 0/18 |
| 3000 / development | layered | 18 | 1.0000 | 13/13 | 0/3 | 18/18 | 0/2 | 0/18 |
| 10000 / development | none | 18 | 0.0000 | 0/13 | 0/3 | — | 0/2 | 0/18 |
| 10000 / development | lexical | 18 | 0.6154 | 8/13 | 2/3 | — | 2/2 | 0/18 |
| 10000 / development | bge_rrf | 18 | 0.6154 | 8/13 | 2/3 | — | 2/2 | 0/18 |
| 10000 / development | routed | 18 | 1.0000 | 13/13 | 0/3 | 18/18 | 0/2 | 0/18 |
| 10000 / development | layered | 18 | 1.0000 | 13/13 | 0/3 | 18/18 | 0/2 | 0/18 |

300 条组：原输入与来源正文相同，但规范化后的结构化值不同。旧版本会丢失嵌套 fact_value，新版本保留；全部逐字段变化已记录，结果包含这项输入规范化修复的收益，不能只归因于检索算法。

数据用途：holdout=second_independent_sealed_holdout_first_run_after_1eef5cb。

300 条组：原输入与来源正文相同，但规范化后的结构化值不同。旧版本会丢失嵌套 fact_value，新版本保留；全部逐字段变化已记录，结果包含这项输入规范化修复的收益，不能只归因于检索算法。

数据用途：development=development_seen_during_tuning；validation=development-validation_seen_during_diagnostics_and_tuning；holdout=seen_regression_after_f7_first_independent_scoring。

数据用途：development=development_seen_during_tuning。

数据用途：development=development_seen_during_tuning。

所有分母、阶段耗时、每类失败与原始 artifact SHA 均保存在同名 JSON。
这是合成故事的经验测量；独立故事是聚类单位，同一句换措辞不是新增独立用户。
