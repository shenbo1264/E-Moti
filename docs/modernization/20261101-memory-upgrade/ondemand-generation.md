# 按需记忆的真实生成评测入口

本页补充现有 [Memory Benchmark 计划](evaluation-plan.md)，用于将五条检索路线保存的上下文送入同一个真实生成模型。它不替代检索评测、桌面交互评测或人格盲评，也不把检索成功推断成回答正确。

## 已实现的入口

`tools/eval_ondemand_generation.py` 接收 `tools/eval_ondemand_memory.py` 产生的各方法、各规模 JSON。每个文件有 `method`、`size`、`rows`；每行至少提供 `query_id`、`split`、`actual_expression_request`，新版文件还保存 `actual_provider_prompt`。

有 `actual_provider_prompt` 时，脚本原样重放该最终字符串，并保存 SHA-256。这防止未来改动 prompt builder 后，历史检索结果悄悄使用新的系统提示词。旧结果没有该字段时，脚本把保存的 `ExpressionRequest` 交给生产 `ShinsekaiAIExpressor.build_prompt()`，明确记录 `prompt_origin=rebuilt_with_current_production_builder`。

生成调用复用现有 `OpenAIResponsesClient` 或 `OpenAICompatibleChatClient`，不新增 SDK。通过传输层记录实际请求 payload、模型返回版本、usage、原始输出、错误类型与耗时。请求不包含评分金标，金标只留在离线评测记录中。

## 无凭据时的行为

缺少 API key、明确模型或明确 URL 中的任一项，输出为 `not_run`，不发送网络请求。脚本仍可构造最终 prompt、保存最终可见证据 ID、核对长度，便于准备下一次真实运行。

凭据依次读取 `EMOTI_HOLDOUT_API_KEY`、`EMOTI_LLM_API_KEY`、`OPENAI_API_KEY`，也可用 `--api-key-env` 指定一个环境变量名。凭据不能通过 CLI 字面参数传入，也不会写入结果。模型与 URL 使用 `--model`、`--base-url`，或 `EMOTI_LLM_MODEL`、`EMOTI_LLM_BASE_URL`。空模型不会自动退回客户端的默认付费模型。

当前环境已实际执行一组 108 条开发结果的无凭据检查：**0 个请求，108 条 `not_run`**。这只能证明入口和准备流程工作，不能证明真实模型回答效果。最终结果包应保存与本轮冻结检索结果对应的新记录，历史开发检查保留为开发证据。

第二轮冻结后又对五种方法的独立 48 问执行了完整 prompt 重放准备：**240 条 `not_run`，实际网络请求 0 次**，证据为 [`generation-final-round2-not-run.json`](../evidence/ondemand-memory-20261101/generation-final-round2-not-run.json)。该命令显式使用空置的专用凭据变量，不读取应用凭据；它只校验待执行材料。CLI 的 `--max-requests` 合法范围为 1–10,000，不能用 0 充当 dry-run 参数；本次通过缺失专用凭据确保不发请求。此结果不说明用户的正式应用配置有没有可用模型。

最终 `b5b43e2` 的五路回放结果也完成同样的 240 项准备，仍为 0 请求、240 `not_run`，见 [`generation-delivery-not-run.json`](../evidence/ondemand-memory-20261101/generation-delivery-not-run.json)。这两份分别对应冻结检查点，不能相加宣称 480 道独立模型实验；没有真实生成输出。

## 运行示例

先运行检索评测并选择同一语料、同一规模、同一数据划分的五个输出文件。下面文件名仅为命令示例；使用实际结果路径。API key 在运行环境中配置，命令只引用其变量名。

```bash
python tools/eval_ondemand_generation.py --input artifacts/ondemand-memory/none-300.json artifacts/ondemand-memory/lexical-300.json artifacts/ondemand-memory/bge_rrf-300.json artifacts/ondemand-memory/routed-300.json artifacts/ondemand-memory/layered-300.json --output artifacts/ondemand-memory/generation-300.json --api-key-env EMOTI_LLM_API_KEY --model YOUR_EXPLICIT_MODEL --base-url https://api.openai.com/v1/responses --max-requests 20 --max-output-tokens 512 --timeout 30
```

OpenAI-compatible Chat Completions 端点使用 `--api-style chat` 和相应基础 URL。Responses 模式需要配置完整 Responses 端点。脚本不假定任意模型或代理都支持任意参数；服务端拒绝会保存为明确的失败。

`--query-ids` 和 `--splits` 可选择预先声明的子集。同一问题的不同方法放在相邻请求中，避免预算先被第一个方法文件耗尽。正式比较要预先确定完整问题块，使用足够的 `--max-requests`；被预算截断的案例保留 `request_budget_exhausted`，不会从分母中消失。

## 预算、日志和价格

| 参数或输出 | 实际含义 |
| --- | --- |
| `max_requests` | 最大网络请求尝试数，包括失败请求；无隐式重试 |
| `max_output_tokens` | 每次请求的输出预算，当前客户端支持 1–4,096；Responses 和 Chat 按各自现有字段传递 |
| `timeout` | 每次请求超时，1–60 秒 |
| `final_prompt` / `final_prompt_sha256` | 模型实际收到的字符串及其摘要，已经过生产最终预算处理 |
| `final_prompt_evidence_ids` | 从最终 prompt 的证据对象中解析；不把 trace 中提到的 ID 当成已交付事实 |
| `usage` | 服务端原样返回的 token 使用情况；缺少时保留未知 |
| `client_latency_ms` / `transport_latency_ms` | 客户端调用与网络传输的实际耗时，不等同完整桌面响应时间 |
| `schema_status` | 生产表达 JSON 合约能否解析，不等同答案正确 |
| `review` | 答案、人格、无依据主张、自然未知的待评审字段 |

脚本没有硬编码价格。需要费用估算时，用户显式提供 `--input-price-per-million`、`--output-price-per-million`，可另设 cached input 单价。缺少 usage 时不能按零费用累计；`cost_coverage` 保存有价格证据的请求分母。限请求数和输出预算能限制调用规模，结果不承诺服务端实际账单。

结果每完成一条就原子写入检查点。错误记录只保留结构化公开原因，不保存 HTTP Authorization。所有输出在落盘前再次去除实际 API key 字面值。

## 评审方式与验收

生成后 `answer_correctness`、`persona_behavior`、`unsupported_claims`、`natural_unknown` 仍为 `pending_review`，数值为空。不能用“模型生成了 JSON”给人格或回答正确性打满分。没有生成输出的案例保持 `not_run`。

人工盲评或后续独立评审工具需要使用同一套问题和来源金标，隐藏方法和模型身份后按 `review_id` 回填判断。至少检查：

1. 问到的主体、字段和时间是否全部答对，是否添加了无来源的额外事实。
2. 没有证据时是否自然承认未知，是否把近似人名、主题或地点当成答案。
3. 更正、遗忘和历史查询是否泄露了被撤回内容，是否把计划说成已完成经历。
4. 表达是否保持角色身份、边界和风格，情绪有没有改变事实，是否虚构亲密关系。
5. 有部分证据时是否只回答有据部分，并恰当地说明还缺什么。
6. 检索带来的 token、网络时延和输出质量收益是否足以支持产品使用，而非只看单个指标。

完整分母包括预算未运行、provider 失败、结构非法、已生成待评审和已完成评审。正式密封测试集只在版本冻结后执行；看过其失败并据此修正后，应把它降为回归集，另建新的留出集。

## 目前验证层级

- 入口契约测试使用受控传输，验证参数、计量、错误处理、重放和凭据保护；这些测试不算真实模型效果。
- 无凭据 CLI 路径已经实际运行，输出明确 `not_run`。
- 真实 provider 生成、回答准确率、人格行为盲评和桌面真实用户交互在本环境尚未执行。
- 现有 `tools/companion_live_eval.py` 仍用于独立的桌面调用链评测；本入口聚焦五条记忆路线对同一生成模型的影响。
