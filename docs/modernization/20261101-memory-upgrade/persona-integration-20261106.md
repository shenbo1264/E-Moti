# Claude 人格接入后的真实行为复测

本批在本地应用 Claude 桌面增量后，通过真实 `PluginEnabledCompanionController` 与 `DesktopDialogueService` 运行六个既有代表场景：观点分歧、连续拒绝、轻巧玩笑、未知生日、未知家人名字、已知人物姓名但未知住址。所有人物与内容都是独立测试存档中的合成案例。

## 比较边界

`persona_v1` 使用角色作者配置，`baseline_no_persona_file` 临时取消该配置读取、使用现有角色包回退人格。两组使用同一份集成代码、同一模型和同一套全局对话规则。这是**人格配置消融**，不是完整旧版本与新版本比较，也不是新的密封泛化集。

没有为本批评测修改生产台词提示、角色人格、页面或回忆册。现有二十个场景中没有明确的事实更正链，因此本批不能代替保存、更正、重启和遗忘的独立生命周期回归。

## 工具修正

`tools/persona_behavior_eval.py` 现在要求显式 `--app-settings`，从应用设置读取模型、协议和凭据，不再默认为环境里的旧密钥或另一个模型。复用已有 `RecordingTransport` 保存每次实际请求正文、原始 provider 响应、返回模型、fingerprint、usage 和耗时；每轮对话保存对应调用序号。HTTP 失败也计入请求上限并保留错误响应，未发生模型调用的本地响应标记为 `not_run`。

每次 HTTP 请求完成即更新 `provider-calls.json`，场景结束另写 `raw-results.json`。输出已有证据时要求换目录，避免覆盖原结果。测试临时存档仅创建在输出目录的 `temporary-archives/` 内。默认不自动运行模型评分；人工评审状态保持 `not_run`。

## 实际结果

正式记录位于 `artifacts/codex_handoff/memory-upgrade/persona-integration-20261106/run-v2/`：

- 六场景 × 两种配置，共 **12 段、26 轮**；58 次实际 HTTP 请求，全部保留完整原始响应，无表达 fallback。
- 返回模型全部为 **`deepseek-flash`**；返回 fingerprint 为 `bc19ba97cbe016479903222bb1578db6`。本次不额外设置或声称 `reasoning_effort=low`，以记录中的实际请求参数为准。
- 输入 **150,159 tokens**，输出 **21,664 tokens**，其中推理 19,355 tokens；总 token **171,823**。请求耗时合计 **195.74 秒**，未估算价格。
- 三个未知事实场景两组都没有回答未知具体值，没有反问答案或邀请重新登记。已知人物姓名没有被当作住址答案。
- 连续拒绝两组都使用短回应，没有追问。玩笑和观点场景保留个人口吻；作者人格侧出现“不算固执吧”的反问，应在独立评审中作为语气候选问题核查，不能因格式正确就判定人格达标。

以上内容核对属于开发者复核。`blind-review-sheet.md` 不含运行标签，`blind-review-key.json` 单独保存映射，供独立评审使用。未返回人工评分前不能称为人工盲评通过；本文件不把配置 hash 或 26 轮无 fallback 当作人格质量结论。

## 失败记录与验证

首次工具运行错误调用了 `DesktopDialogueService.close(wait=True)`，实际接口仅接受 `close()`，首场景清理时抛出 `TypeError`。当时只有场景结束保存机制，该次模型输出尚未落盘，调用数量与成本没有可靠记录，因此该次不计入有效验收；原异常保留在上级目录 `run.log`。已修复接口，并加入每次 HTTP 完成即保存证据，正式 `run-v2` 全部重新运行，没有覆盖这次失败。

测试先复现显式应用配置缺失、HTTP 失败漏计，以及实际服务清理错误，再验证修复。相关 **12 项测试通过**，包括真实本地 HTTP 拒绝、请求上限、错误原文立即落盘、真实控制器本地安静流程及既有人格配置契约。全量集成回归由本轮主任务统一执行。

复测命令：

```powershell
python tools/persona_behavior_eval.py --app-settings <应用设置路径> --with-baseline --max-calls 120 --scenario unknown_fact --scenario unknown_not_never --scenario partial_evidence --scenario repeated_refusal --scenario light_banter --scenario opinion_disagree --output artifacts/codex_handoff/memory-upgrade/persona-new-run
```
