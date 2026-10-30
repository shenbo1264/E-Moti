# 2026-10-30 核心升级实际证据

这些记录来自隔离的合成存档和真实 provider/ONNX 调用，不含用户真实聊天存档或模型凭据。原始工作记录仍在后端 `artifacts/codex_handoff/`；以下副本纳入本地集成提交，便于 Claude 和后续开发者阅读。

| 文件 | 含义与边界 |
|---|---|
| `holdout-saved-provider-combined.json` | 冻结的10条独立轨迹×无记忆/词法/语义三组，真实 DeepSeek 回答、实际 prompt、usage、延迟。 |
| `holdout-answer-review.json` | 30条回答的单模型、知组别语义评审，包含证据和坏例；不是双盲或用户体验验收。 |
| `desktop-memory-smoke-live.json` | 普通茶饮自述→重启→真实 ONNX→三次实际桌面服务表达→纠正/遗忘，14项检查；不以字面检查代替改写泄露评审。 |
| `desktop-extraction-live.json` | 规则外称呼的真实语义抽取→主线程校验→V2保存→模型表达，4项检查。 |
| `semantic-extraction-provider.jsonl` | 真实抽取开发样本的原话、提议、用量、结果；属于已见开发验证。 |
| `semantic-memory-calibrated.json` | 真实中文 ONNX 五条开发探针，保留原始余弦及漏召回、无关召回。 |
| `core-memory-benchmark.json` | 原38条确定性开发契约，全部通过；其中人格项只检验配置，不当作模型行为评分。 |
| `claude-independent-core.json` | Claude 新验收第一次运行当前本地同步路径的原始失败，保留事实。 |
| `claude-observed-regression.json` | 看过上述样本后运行的已见回归，不再视为独立 holdout；该工具不启用异步语义抽取或 embedding 准备。 |

真实输出存在无依据的过去观察和感官描写，详见逐例评审。词法/语义记忆组各3/3事实回忆仅是本批小样本结果；12次纠正、遗忘与隔离探测未见目标旧事实泄露，不代表总体零泄露或人格稳定已验收。

生产 DeepSeek 输出预算已由512修为4096，依据是实际512预算耗尽于reasoning且无正文。真实评测使用60秒超时，正式应用已有配置为30秒；一条响应32.21秒超过它。没有修改该用户配置。

这些模型调用发生于以 `0f96f94` 为 HEAD、包含本批开发改动的工作区，各报告保存实际发送的 prompt。最后的称呼画像来源整合随后由本地回归验证，没有重复模型调用。最终源码完整回归为1549 passed / 5 skipped，原始日志在 `artifacts/codex_handoff/core-delivery-final.log`。
