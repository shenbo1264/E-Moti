# 桌面后端跟进验证，2026-10-30

基线为 Claude `5dd8c4e`，实现说明见 `docs/handoff/20261029/claude-backend-followup-20261030.md`。所有数据都是合成样本，实际走现有 controller、SQLite 和 Qt 服务；没有操作真实存档。旧独立 holdout 和 Claude 28 条验收集保持原样。

## 最终代码检查

- 完整 `python -m pytest -q -rs`：**1617 passed，5 skipped，3 warnings**，160.96 秒，原始日志 `followup-full-final.log`。
- 跳过：4 条需显式启用的 provider 测试，1 条 Windows 符号链接测试。真实生成另行运行，见下文。
- 警告：2 条既有 websockets 弃用提示；Claude 的 `test_panel_reports_port_in_use` 主动占用端口时，uvicorn 工作线程产生 SystemExit 警告。保留结果，本批未扩大修改暂停中的手机功能。
- 38 条开发契约 **38/38**，`followup-memory-contracts-final.json`。检索/交付 11/11，遗忘内容 prompt 泄露 0/10；这是确定性契约，不是模型回答得分。
- 新回归先观察到自然遗忘缺失、计划纠正误写已发生事实、到期抽取恢复旧上下文、纠正原话跨重启重新进入 prompt 的失败，再验证修复。原“所有计划都不保存”的两条测试已更新为受控计划语义。
- `git diff --check` 通过。

运行使用 `PYTHONUTF8=1`，测试目录 `artifacts/codex_handoff/`；真实 embedding 缓存复用原 host-backend 目录，不重复下载。

## 实际模型结果

使用桌面已启用的 `deepseek-v4-pro`，工具超时 60 秒，4096 输出 token，实际 ONNX 召回开启。凭据不在报告中。环境变量中的 OpenAI 和 DeepSeek 凭据均返回 HTTP 401：相应 OpenAI 两模型本轮为 `not_run`，不计入下面实际调用。

| 记录 | 有效调用 | 实际 token | 结论 |
|---|---:|---:|---|
| `desktop-saved-provider-followup.json` | 3 | 9675 | 14/14 生命周期检查；3 个实际回答 |
| `followup-live-independent.json` | 6 | 18834 | 三条新增轨迹；保留两个 bad case |
| `followup-live-correction-final.json` | 3 | 8214 | 历史失效修复后的纠正轨迹复测 |

合计 12 次调用、36,723 实际 token。新增轨迹初轮最长响应 25.662 秒，纠正复测最长 23.100 秒；非流式请求，未测首 token 延迟。token 来自 provider usage，不是字符估算。报告包含实际 prompt、输出、usage 和逐次延迟。

分别判断：

- **检索**：茶饮轨迹实际 ONNX 找到两条低于词法阈值的事实；新计划跨重启后出现在实际 prompt。
- **prompt 交付**：茶饮纠正/遗忘后旧值清除；计划初轮纠正仍从本轮历史带入旧地名，已修复，复测后续 prompt 包含“漳州”、不含“泉州”。
- **回答正确性**：新计划地点均能答出，纠正复测回答为“唔，你上次说下个月搬去漳州……是已经定下来了吗？”，保留未来语义。单凭地点字面命中不能判整句正确。
- **遗忘泄露**：狗名字遗忘后重启询问，实际 prompt 和回答均无原名字“松子”；茶饮遗忘后无旧饮料偏好。
- **人格/归因**：仍未全面通过。计划召回回答“还问我桌角会不会换个朝向呢”错误地把角色先前的问题归给用户；原 prompt 中角色标签正确。此 bad case 原样保留，交 Claude 做体验评审，没有针对它改人格配置或调优测试样本。

`followup-live-independent.json` 是本次新增合成轨迹，非用户样本、非盲评；纠正复测沿用失败样本，属于回归而非新 holdout。初轮“漳州。这次我记住了，不再说成泉州。”的旧地名复述也保留在原报告中，不用修复后结果覆盖历史。

常规复现命令：

```powershell
$env:PYTHONUTF8='1'
python -m pytest -q -rs --basetemp=artifacts/codex_handoff/followup-recheck
python tools/memory_benchmark.py --output artifacts/codex_handoff/contracts.json
python tools/desktop_memory_smoke.py --live --base-url https://api.deepseek.com --model deepseek-v4-pro --api-key-env EMOTI_HOLDOUT_API_KEY --output artifacts/codex_handoff/desktop-live.json
```

新增轨迹使用现有 `companion_live_eval.run_case`，精确输入见报告 `turns`，初始事实分别为“我下个月要搬去泉州。”和“我的狗叫松子。”；复测脚本保留在工作目录的 `artifacts/codex_handoff/run_followup_live.py`。无需更改桌面配置或真实存档。
