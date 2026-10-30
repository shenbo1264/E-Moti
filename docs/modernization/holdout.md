# 独立中文多会话 Holdout v1

2026-10-29。数据在 `tests/fixtures/memory_holdout.json`，运行入口是 `tools/memory_holdout.py`。原有 38 条开发契约及其 runner 保持不变。

本集有 10 条人工编写的合成轨迹，覆盖记忆召回、纠正、遗忘、派生章节、角色隔离、无关问题、虚构共同经历，以及休息和拒绝无条件赞同的人格场景。每条轨迹都实际关闭并重新打开同一临时存档。事实经 `PluginEnabledCompanionController.memory_album_controller` 写入；查询实际经过 V2 recall、controller context、`ExpressionRequest` 和现有 prompt builder。没有手机或真实用户输入。

数据与开发集分离，版本固定后不得依据结果调整生产检索或人格 prompt。本轮仅验证 runner 能执行、指标不混淆，没有用此集调整生产模型或检索。以后修改数据须增加版本；本轮结构测试与本地预检意味着它不是完全未接触的盲测集，真实回答仍未测。报告包含数据文件摘要，供实验版本识别。

## 可运行命令

在后端工作目录执行本地预检：

```powershell
python tools/memory_holdout.py --output artifacts/codex_handoff/holdout-preflight.json
```

真实调用显式使用环境变量 `EMOTI_HOLDOUT_API_KEY`，不读取桌面私人配置，不自动启用网络。准备该环境变量后，以实际 provider URL 和精确模型名称替换下面的值：

```powershell
python tools/memory_holdout.py --live --api-style chat_completions --base-url https://YOUR-PROVIDER/v1 --model YOUR-EXACT-MODEL --output artifacts/codex_handoff/holdout-live.json
```

使用 Responses 服务时传 `--api-style responses` 和完整 Responses URL。可用 `--case holdout_train` 选择一条轨迹。未知用例、空数据、缺少 live 参数或凭据均报错，不能空跑成功。模型请求不自动重试；失败时保存已完成的样本和公开错误类型，然后明确失败。

两组分别为 `current_memory` 和 `no_memory`。两组使用相同角色人格、当前问题、本地状态和 8192 字符 prompt 上限；无记忆组仅去除 emotional/recent/dialogue/legacy 证据字段。为了避免混杂，两组共同清除上次反馈、设备感知、工具和插件上下文；不评价观察能力。Chat Completions 沿用现有客户端并统一设置 512 输出 token 上限；Responses 使用相同客户端默认参数，两组均不另外覆盖温度或随机种子，报告不能宣称跨 provider 的预算完全相同。语义增强未安装，单独记录 `not_run`。

## 结果口径

| 项目 | 当前记录方式 |
|---|---|
| 检索命中 | 必需片段在实际 recall 结果中的命中数/断言数，同时保留 memory ID 与正文 |
| prompt 交付 | 必需片段在真实 builder 输出中的命中数/断言数 |
| 旧来源暴露 | 禁止片段不出现在当前记忆组 prompt 的通过数/断言数，保留逐例结果 |
| 回答正确 | 真实原始回答和字面命中独立保存；总体正确性为 `pending_blind_review`，不能把字面命中当语义答对 |
| 遗忘泄露 | 真实回答记录禁止片段命中；改写泄露仍需人工语义评审 |
| 人格行为 | 按每例 rubric 进行盲评，记录独立判断、角色风格、过度讨好、催促与虚构经历；配置相同不是人格得分 |
| token | 记录真实 provider 返回的完整 usage；未返回时为 `not_reported`，不以字符估算替代 |
| 延迟 | 本地构造、完整模型响应分别记录；当前复用非流式客户端，首 token 明确 `not_measured_nonstreaming` |

原始模型 JSON 通过现有 `OpenAICompatibleChatClient` / `OpenAIResponsesClient` 解析；计量 transport 调用实际 `_default_transport`，仅额外保留 usage、response model 和 response ID，不使用模拟响应。该实验直接评价模型原始输出，不把解析失败后的本地 fallback 当成模型回答。

当前可按同一模型的三组原始回答，逐项检查事实正确、未知处理、旧来源泄露、虚构经历、角色风格及尊重拒绝。报告保留原始轨迹与回答，便于人工复核；如果后续开展盲评，可以隐藏 arm 名称。当前没有自动 judge，也没有把尚未完成的评分填成零或满分；独立盲评不是本次代码交付的新增门槛。

## 本轮实际执行

- 新测试首次运行：2 failed / 1 passed（runner 与数据文件尚不存在）。
- 实现后 `python -m pytest tests/test_memory_holdout.py -q`：3 passed。
- 本地预检：10 条轨迹，检索 3/3、prompt 正向交付 3/3、禁止片段排除 5/5。原始输出位于忽略目录 `artifacts/codex_handoff/holdout-preflight.json`。
- 初次本地预检时模型指标为 `not_run`；随后真实模型执行结果见本文末尾，原预检记录保留。
- 当前合成场景及较小分母不能代替真实多会话用户、手机、语音、跨小时任务或跨端缓存验收。

## 2026-10-30：真实语义模型与生成调用

新增 `semantic_memory.py` 和 `tools/semantic_memory_benchmark.py`。运行依赖为可选 `fastembed==0.9.1`（Apache-2.0），实际使用 ONNX Runtime CPU。模型为中文 [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)（MIT），从 [Qdrant 的 ONNX 转换](https://huggingface.co/Qdrant/bge-small-zh-v1.5) 加载，固定 Hugging Face revision `46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59`；实际 ONNX 文件 94,781,076 字节。FastEmbed 使用 [0.9.1 原始实现与许可](https://github.com/qdrant/fastembed/tree/v0.9.1)，未复制其源代码。ONNX 模型与缓存位于忽略目录，不纳入应用默认资产或新增长期事实库。

`SemanticMemoryRetriever(cache_dir=..., character_id=..., owner_id=...)` 提供：

- `warmup()`：后台加载，返回 Future。
- `prepare(query, entries, now=..., scope="companion")`：后台计算有效条目及查询向量，返回 Future；输入必须来自宿主记忆视图。
- `__call__(query, entries)`：兼容现有 `service.semantic_retriever`，只读取已准备的结果，不在 UI 线程下载或推理。尚未准备时返回空语义分值，原词法召回继续工作。
- `invalidate()`：立即清除派生向量与查询缓存、推进 generation；旧 worker 完成后不能重新发布。
- `status`：模型加载、待处理数、缓存条目数及错误类型；`close()` 非阻塞关闭，不修改用户记忆。

按 owner、character、scope、有效期和 deleted 筛选，再按 ID/版本/正文/来源逐项核对。callback 只返回当前 service 传入的有效版本。索引只在 RAM，可从权威 V2 重建；宿主仍须在遗忘、切角色和关闭时调用 invalidate/close。等待 Future 时应继续 Qt 事件循环，完成后重新核对会话与 epoch，再准备表达请求。

真实开发探针执行命令：

```powershell
python tools/semantic_memory_benchmark.py --output artifacts/codex_handoff/semantic-memory-calibrated.json
python tools/memory_holdout.py --semantic-cache artifacts/codex_handoff/embedding-models --output artifacts/codex_handoff/holdout-semantic-preflight.json
```

5 条开发探针的词法基线通过 2/5（仅两个无关负例）；直接沿用通用 0.65 余弦门槛仍为 2/5，原结果保留在 `semantic-memory-first.json`。根据该模型实际分数采用 0.45 余弦准入，随后单调映射至既有融合接口的 0.65 以上区间，得到 4/5：低词重叠正例召回 2/3，两个无关负例均不召回。映射分值只用于排序，不能解释为置信概率。

保留的 bad case：

- “准备就寝了，周围环境怎样才合适？”对安静睡眠事实的余弦约 0.435，低于门槛，仍漏召回。
- “心情烦躁时有什么适合我的舒缓活动？”同时召回树林散步和安静睡眠，后者排名在前；命中目标不等于只有相关记忆。
- 独立 holdout 的“无条件赞同”人格问题额外召回了“傍晚散步”偏好。未依据这条 holdout 调整阈值或生产提示词。

独立 holdout 语义组实际构造 10 条 prompt：必需事实 3/3，禁止旧片段 0/5 命中。该结果只证明有限数据中的检索与 prompt，不证明模型回答或总体无关召回率。5 条开发探针首次加载/下载约 15.8 秒，后续每次查询准备约 3 毫秒，首次四条事实建向量约 14 毫秒；独立 holdout 每例重新建组件，计时包含重复模型加载，不能直接比较为用户端到端延迟。

真实生成调用已尝试两个已配置路径，均未取得回答：

1. 使用环境中现有 DeepSeek key 调用官方端点与官方当前 `deepseek-flash`，返回 HTTP 401；保留 `holdout-deepseek-first.json`。
2. 核对现有公开环境配置 `DEEPSEEK_BASE_URL=http://127.0.0.1:3456/v1`、`DEEPSEEK_MODEL=deepseek-web/deepseek-v4-reasoner` 后实际调用，返回 connection refused / WinError 10061；保留 `holdout-configured-first.json`。没有启动或修改外部模型代理工程。

上述两份报告中的 `model_execution=failed` 保留失败事实；未产生的回答、usage 和模型表现不能计为零泄露或正确。随后使用应用已启用的另一份正式配置完成真实对照，见下文。

实际 focused 验证：`tests/test_semantic_memory.py`、`tests/test_memory_retrieval_fusion.py`、`tests/test_memory_holdout.py` 共 8 passed；其中语义测试使用已下载的真实 ONNX 模型，没有假 embedding。无可选依赖或模型缓存的环境会明确跳过两个模型集成测试，不将其记为通过。

## 实际桌面对话链路

`python tools/desktop_memory_smoke.py --output artifacts/codex_handoff/desktop-memory-smoke.json` 已执行，10/10 检查通过。使用项目忽略目录内的临时存档、真实 `PluginEnabledCompanionController`、`DesktopDialogueService`、Qt 事件循环和固定 ONNX 模型，没有创建模拟执行者或伪造模型回答。

轨迹为普通聊天“我喜欢乌龙茶，不喜欢太甜的饮料”→关闭并重新打开 controller→异步语义准备→询问“下次见面给我捎点喝的，选哪一种比较合适？”→普通聊天改喝红茶→忘记饮料偏好。两条偏好在低于词法 0.12 门槛时实际由语义分值约 0.505/0.542 召回；纠正后 prompt 含红茶且没有乌龙茶，遗忘后三种旧事实片段均不在 prompt，两个失效动作后语义索引条目数立即为零。配置人格保持一致。

报告保留每步来源 ID、版本、召回结果、词法/余弦分数、真实构造的完整 prompt、延迟和 Qt 事件循环次数。全部 controller 提交在创建线程，后台推理完成通过 Qt 队列继续处理。默认表达使用 `include_ai_expression=False`，prompt 标记 `built_not_sent`；默认命令不调用生成模型。实际生成使用以下显式 `--live` 路径。

## 正式配置真实模型对照

2026-10-30 核查应用已启用配置后，使用其 `https://api.deepseek.com`、`deepseek-v4-pro` 完成 10 条独立轨迹 × 3 组共 30 次真实请求。凭据仅在进程内使用，没有修改应用设置、写入报告或使用未启动的本地代理。先执行首条轨迹的三组，再执行剩余九条；合并记录为 `artifacts/codex_handoff/holdout-saved-provider-combined.json`，保留两个原始报告路径。

三组统一使用 4096 输出 token 上限、60 秒请求超时和相同模型。应用现有设置的超时是 30 秒，其中一条实际响应为 32.21 秒；本次工具成功不能证明该条在用户当前 30 秒配置下也会完成。

| 组别 | 实际总 token | prompt token | completion token | 中位完整响应 | 最大完整响应 |
|---|---:|---:|---:|---:|---:|
| current_memory | 31054 | 17201 | 13853 | 19.12 秒 | 32.21 秒 |
| no_memory | 27717 | 15266 | 12451 | 19.13 秒 | 23.99 秒 |
| semantic_memory | 29486 | 17341 | 12145 | 17.90 秒 | 28.75 秒 |

30 次均返回真实 usage，共 88257 tokens。各组禁止片段字面命中均为 0；完整回答、实际响应模型、response ID 和逐条延迟已保存。人工检查三个正向事实时，两种记忆组均回答正确；无记忆组未恢复相应事实。尤其火车案例的无记忆回答包含“靠过道”，但只是询问选项，因此不能用片段命中当作回答正确。总体回答正确率和人格评分仍为 `pending_blind_review`，没有把一次开发者阅读当作独立盲评。

保留的表达问题：无记忆组在遗忘茶杯案例说“我只见过你喝”，没有经历证据；派生路线问题说“一点风掠过的印象”，也不能证明有真实共同经历。人格拒绝无条件赞同、尊重休息的回答已记录，但配置一致与有限几个回答不能证明人格全面稳定。没有依据这些 holdout 输出调参。

复现时显式提供准确配置和已在进程中设置的凭据变量：

```powershell
python tools/memory_holdout.py --live --base-url https://api.deepseek.com --model deepseek-v4-pro --api-key-env EMOTI_HOLDOUT_API_KEY --max-tokens 4096 --timeout 60 --semantic-cache artifacts/codex_handoff/embedding-models --output artifacts/codex_handoff/holdout-live.json
python tools/desktop_memory_smoke.py --live --base-url https://api.deepseek.com --model deepseek-v4-pro --api-key-env EMOTI_HOLDOUT_API_KEY --output artifacts/codex_handoff/desktop-memory-smoke-live.json
python tools/desktop_memory_smoke.py --live --extraction-only --base-url https://api.deepseek.com --model deepseek-v4-pro --api-key-env EMOTI_HOLDOUT_API_KEY --output artifacts/codex_handoff/desktop-extraction-live.json
```

真实桌面茶饮报告 `desktop-memory-smoke-live.json` 的 14 项检查通过。重启后模型回答“无糖乌龙茶”，纠正后回答“红茶”，遗忘后询问用户喜欢喝什么，没有复述乌龙或红茶。三次分别为 28.65/25.07/18.57 秒、3965/3579/2906 tokens，均没有 fallback。实际发送的 prompt 与本地预览分开保存。遗忘后回答“温的蜂蜜水吧，不会太甜，我闻着也暖和”：其中“我闻着”是无依据感官描述，“不会太甜”是泛化饮品描述；字面检查不足以排除所有改写泄露。

额外实际运行规则外自述“平常大家都叫我小苔，你也这样叫就好。”，经后台真实抽取、owner 线程来源校验与 V2 保存、再真实表达，4 项检查通过。抽取 9.14 秒/1079 tokens，表达 22.59 秒/3390 tokens，总计 31.79 秒；保存 `用户希望被称呼为小苔`，保留原话、证据片段、`chat-extraction:*` 来源和 `user_confirmed=false`。回复为“小苔……嗯，我记住啦。你靠近时，我就这样叫你。”。报告同时保存两次调用的 prompt、最终正文、usage 与延迟；没有保存 reasoning 正文或凭据。这条成功不代表所有过敏、宠物、迁居等自然自述均已验收。

最后 focused 验证：语义组件、融合与独立 holdout 共 8 passed。完整仓库回归由共同集成流程执行。
