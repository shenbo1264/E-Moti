# 冻结版本的 Qt / BGE 桌面对话链路诊断

代码基线：`f7a4e23a0f7b207fc68c1719c2217ac740416344`。本目录保存冻结工具原样运行的失败结果，以及不修改生产源码、测试或评分脚本的独立诊断。它不是窗口外观验收，不是 Windows 真机验证，也没有请求生成模型。

## 原工具原样运行：9 / 10 检查通过

```bash
QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 \
python tools/desktop_memory_smoke.py \
  --cache-dir /tmp/emoti-bge-model-cache \
  --output docs/modernization/evidence/ondemand-memory-20261101/desktop-smoke-frozen/original-smoke.json
```

实际 exit code 为 1，`original-smoke.json` 和 `original-smoke.log` 保留原始结果。唯一失败项为 `real_semantic_recalls_below_lexical_threshold`。

失败原因可以直接从最终 provider prompt 核查：饮料问题已经路由为 `fact`，结构化证据状态为 `sufficient`，两条有效偏好都进入最终上下文。BGE 模型已经真实载入，但 passage/query 编码数都为 0，这正是按需路径应避免的额外工作。旧工具仍通过旧 `recall()` 取词法结果，并要求每条已送达偏好都有 cosine ≥ 0.45；其旧 API 返回空列表，旧 oracle 因此失败。不能为了让这个检查变绿，重新给结构化事实强制增加 BGE 调用。

其余九项检查全部通过：普通聊天写入两条偏好、重新打开宿主保留记忆、当前偏好正确送达、更正后旧偏好消失、遗忘后旧事实消失、缓存评分失效、人格配置稳定及宿主线程调用。遗忘后的最终上下文明确为 `unknown`，没有把附近的其他内容作为饮料答案。

## 当前契约独立诊断：12 / 12 检查通过

`desktop_current_route_diagnostic.py` 最初在独立 scratch 路径执行，本目录保存其原样副本、`current-route-diagnostic.json` 和日志。它导入冻结版生产服务与原工具的宿主辅助函数，使用实际 QCoreApplication、实际 SQLite、实际 fixed-revision BGE 和生产最终 prompt builder。

脚本中的根路径、模型缓存和输出路径在开头明确指定。异地复现时修改这些路径即可；不要修改生产检索代码或金标。执行环境需要项目 PySide6 依赖与 semantic 依赖。

| 阶段 | 实际路由 / 充分性 | 最终可见证据 | 实际 embedding 变化 |
| --- | --- | --- | --- |
| 重启后问饮料偏好 | fact / sufficient | 乌龙茶、不喜欢过甜的两条来源 | passage 0、query 0 |
| 查询共同摄影事件 | episode / sufficient | 唯一已完成事件来源 | passage +3、query +1 |
| 更正后再问饮料 | fact / sufficient | 红茶与保留的不过甜偏好 | 未触发额外 embedding |
| 遗忘后再问饮料 | fact / unknown | 0 条事实证据 | 未触发额外 embedding |
| 再问无关的摄影事件 | episode / sufficient | 原事件仍在 | passage +0、query +1 |

事件是**明确标记的合成已结算事件 fixture**，通过生产 `record_focus_completion()` 写入，具有固定事件 ID 和完成状态。它验证事件来源、实际 BGE worker 和遗忘隔离，不能宣称用户真实在公园拍过照、真实完成过游戏或已经获得长期陪伴体验证据。

八次真实对话提交产生八次 `snapshot_changed`，全部信号回调在宿主 owner thread 上执行。诊断中所有生产 Python 文件与冻结 smoke 工具的 hash 在运行前后保持一致。人格检查只覆盖配置和 prompt 的一致性；没有输出任何真实 LLM 回答，因此自然未知表达和人格行为稳定仍为 `not_run`。

日志中 ONNX Runtime 报过 telemetry device ID 无法持久化并改用内存 ID 的 warning；编码实际完成，诊断检查通过。没有将 warning 隐藏成缺少实际推理。

## 工具契约修订后：10 / 10 检查通过

初次诊断后，主线程应用了独立 scratch 中准备的小补丁：让 `prompt_preview()` 同时记录最终 provider 证据、按需 trace 和 semantic status，将旧 `recall()` 明确标注为 legacy 诊断；饮料案例验证结构化证据和跳过 embedding，遗忘验证 `unknown` 与零证据。没有修改生产 `src`、检索评分脚本或评测语料，没有据此调节 holdout。

再次用相同命令运行修订后的原工具，将输出目标改为 `revised-smoke.json`，结果 **exit code 0，10 / 10 检查通过**。原始 `original-smoke.json/log` 的 9 / 10 失败记录完整保留；新结果为 `revised-smoke.json/log`。`run-metadata.json` 保存旧、新工具 SHA-256，核对生产源码与 freeze commit 一致，并额外检查三个事实阶段的最终 provider routes/status、passage/query 编码数为零、遗忘字符串不再出现在最终 prompt。

这是修订过时的工具 oracle；不是降低事实正确性要求或把实际 BGE 测试删掉。真正的 episode/BGE worker 推理已由上述独立诊断验证，运行日志和合成事件来源均保留。两条 smoke 都没有发送生成模型请求，不能代替模型回答或人格行为验收。
