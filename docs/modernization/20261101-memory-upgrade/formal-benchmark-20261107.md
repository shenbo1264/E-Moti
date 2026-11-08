# 公开陪伴记忆 Benchmark：2026-11-07 部分运行

上游：[Ornn8/chat-memory-benchmark](https://github.com/Ornn8/chat-memory-benchmark)，固定 commit `07a11f4074cde1106c5fed9f627e662ff1a3abc1`，MIT。使用其原生 reader、prepare、score，未将正式答案用于生产修改。

生产版本冻结为 `523150e`。模型请求使用实际设置 `deepseek-flash`，提取维持当时的 `reasoning_effort=low`、`max_tokens=4096`。本报告不代表后续生产版本的成绩。

## 实际分母与状态

|人物|全部问题|真实回答完成|回答失败|尚未作答|
|---|---:|---:|---:|---:|
|P01|88|88|0|0|
|P12|79|28|51|0|
|P14|82|21|61|0|
|P16|123|14|88|21|
|P17|172|1|13|158|
|P20|170|2|3|165|
|合计|714|154|216|344|

“回答完成”仅说明真实模型返回有效表达，未进行正式语义评分，正确率为 `not_run`。216 条失败没有写入成功答卷；本地 fallback 不算模型回答。正式任务已停止，不存在仍在后台运行的评测 worker。

共记录 1,535 次请求，其中 813 次收到正常 HTTP 响应，722 次为 HTTP 402，服务返回 `Insufficient Balance` / `insufficient_balance_error`。正常响应报告的 usage：输入 1,671,835，输出 979,337，合计 2,651,172 token；HTTP 402 没有返回 usage，未虚构费用。部分正常响应耗尽 4,096 个推理 token，正文为空，属于提取失败。

首版评测工具把 provider 失败作为失败回合继续，未区分余额耗尽，造成 722 次 402 请求。这是工具缺陷，原始请求与失败保留。现已在首个包含 402 的回合保存 checkpoint 后停止；独立 grader 也停止派发后续批次。不会自动重试失败回合。

P14 的一题 pilot 使用 3 次真实作答/提取请求，独立 Flash 裁判请求 1 次，语义评分 0/1。这个已见样本不作为新泛化结论。

## 回放与恢复语义

每个人物使用独立档案，固定 user 与 assistant 按原时间增量回放。考试使用关闭后的档案副本，短期聊天窗口为 0；同 cutoff 的不同考试时间不推进主档时间。Unix/Asia/Shanghai 标记持久保存，保留原生到期维护。请求、输出、usage 在每次 provider 调用后立即写入日志。

最初空正文错误发生于 `extract_memory` 返回前，尚未 `apply`，prepare 的到期清理已经发生。恢复只补交固定对话，未重放准备阶段、未重新请求提取；checkpoint 保留原 source config、runner revision 和恢复事件。其他不明中断仍拒绝自动重放。

余额恢复后的续跑必须使用原冻结生产代码，不能直接在新版生产目录混合成绩。可从 `523150e` 建立独立工作目录，依次应用仅评测提交 `4ce35c3`、`79f0048` 与本报告随附的 HTTP 402 工具修复提交，复制原完整运行目录，再执行：

```powershell
$env:PYTHONUTF8='1'
$env:QT_QPA_PLATFORM='offscreen'
python tools/eval_chat_memory_formal.py --benchmark-root <固定上游目录> --app-settings <本机设置文件> --model-cache <本机BGE目录> --output <原完整运行目录> --jobs 3 --max-calls 9000 --resume --accept-runner-recovery
```

续跑跳过已经完成和已经失败的问题，继续未作答题；不覆盖请求日志，不重做已付费请求。此次 402 期间未保存的事实仍然缺失，续跑只能补充这份有缺失记忆的诊断记录。不能把它改写为完整、无故障的质量成绩。新的生产版本应另建运行目录，保留本次失败基线。

提交的证据 ZIP 排除全部 SQLite/运行存档/向量缓存和密钥；包含实际答卷、逐请求原始日志、逐回合状态、checkpoint、失败记录、恢复说明和上游许可证。ZIP 本身不能独立恢复完整档案；本机 ignored 原运行目录保留完整档案。

工具验证：`tests/test_chat_memory_formal.py` 与 `tests/test_chat_memory_benchmark_adapter.py` 合计 11 项通过；`git diff --check` 通过。工程检查不代替正式模型质量评分。
