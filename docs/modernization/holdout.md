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

盲评时应隐藏 arm 名称，将回答与原始轨迹交给评审；逐项标记事实正确、未知处理、旧来源泄露、虚构经历、角色风格及尊重拒绝。当前没有自动 judge，也没有把人工尚未完成的评分填成零或满分。需要至少两名评审的真实评分才能报告分歧或一致性。

## 本轮实际执行

- 新测试首次运行：2 failed / 1 passed（runner 与数据文件尚不存在）。
- 实现后 `python -m pytest tests/test_memory_holdout.py -q`：3 passed。
- 本地预检：10 条轨迹，检索 3/3、prompt 正向交付 3/3、禁止片段排除 5/5。原始输出位于忽略目录 `artifacts/codex_handoff/holdout-preflight.json`。
- 模型回答正确率、回答遗忘泄露、人格行为、provider usage 和模型延迟：全部 `not_run`。没有提供本轮模型凭据与精确 provider 配置，未发起模型请求。
- 当前合成场景及较小分母不能代替真实多会话用户、手机、语音、跨小时任务或跨端缓存验收。
