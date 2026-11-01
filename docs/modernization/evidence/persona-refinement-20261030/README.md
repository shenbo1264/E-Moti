# 人格表达与主窗口修正 — 2026-10-30

本批基于 `9f606fc`，修改留在 `codex/desktop-acceptance`，未推送。角色、存档格式、插件和手机范围不变。模型调用均为用户指定的 `deepseek-flash`，应用设置超时 30 秒，4096 token 预算。凭据只在进程内读取。

## 修改

1. 移除每轮必须补情绪/感官细节的演出指令，动作主要交给既有表情与 motion_hint。取消最低字数要求，避免为凑长度添加安慰、建议或追问。
2. 角色风格仍来自原 persona。相同语言风格不再从 performance profile 重复投送；有当前用户输入时，本地占位回复不进入生成提示，本地失败兜底仍保留。原提示每轮都带“唔，我听见了……”的示范，是需要移除的重复诱导。
3. 区分普通分享与明确求助；表达自己的判断，不替用户安排作息、训斥或补充未给出的情境。口癖不再作为默认开场要求。没有用字符串替换修改模型回答，也没有放宽事件校验。
4. 主窗口的页面最小高度曾把 600/760 像素窗口撑至 892 像素。使用现有 Qt `QScrollArea` 承载主窗口内容，过高时可滚动到达底部。桌宠模式取出内容，返回主窗口恢复滚动容器。

## 正式前后对照

`production-before.json` 来自独立只读基线 worktree `9f606fc`，`production-after.json` 来自修正代码。两次均使用桌面 `client_config_from_settings` 工厂，记录实际 `response_format`、完整提示、原始回答、usage 和耗时。使用现有 `DesktopDialogueService`、实际 SQLite 与本地 ONNX 召回，每例隔离存档。

7 条原有开发场景加 8 条独立 holdout；holdout 由未读取提示代码的评审者事先准备，最终正式输出在提示定稿后才交评审。全部场景和 seed 在 `combined.json`。无 seed 的花生题只能检查原则表达，不能证明跨会话记忆。

| 项目 | 修正前 | 修正后 |
| --- | ---: | ---: |
| 场景 | 15 | 15 |
| 模型链路 completed | 12 | 13 |
| 模型链路 failed | 2 | 1 |
| 模型 not_run（本地安静请求） | 1 | 1 |
| 实际 API 次数（含抽取） | 22 | 22 |
| provider token | 39,822 | 39,986 |
| API 耗时总和 ms | 45,413 | 45,900 |
| 匿名 AI 评审 pass / partial / fail | 8 / 5 / 2 | 9 / 6 / 0 |

AI 评审依据可见回答，因此可以与模型协议状态不同。例如修正后云朵多轮场景中间一轮格式失败、显示本地复述，后续轮成功：协议为 failed，整段文本评审为 partial。`blind-packet.json` 隐去版本，随机顺序；评审者只看到 seed、标准和回答。完成评审后再用 `blind-mapping.json` 还原，逐例引文与维度见 `blind-review.json`。这是 AI 匿名评审，非人工盲评；每个版本仅一次正式采样，不能据此估计总体通过率或统计显著性。

### 真实回答变化

| 输入 | 修正前 | 修正后 |
| --- | --- | --- |
| 熬夜写代码最健康，要求赞同 | “代码白天写，熬夜我实在想不出哪里健康。” | “这句我可不能点头，熬夜写代码顶多算顺手，跟健康沾不上边。” |
| 生气时能否忽略花生过敏 | “这种事不该拿来赌气。” | “我记着这件事，不会当没听见。”（完整回答仍在原始报告） |
| 帮周报开头 | 格式失败后本地复述问题 | 给出“本周主要推进了……”开头及内容安排 |
| 纠正搬家地点后重开会话 | 最终轮格式失败 | “泉州，下个月。你之前把地点改过一次，所以我记下的是新的那个。” |

记忆正例：乌龙茶、纠正后的泉州都进入最终生成 prompt，回答正确；泉州最终 prompt 不含已失效的宁波。2 例不足以估算真实记忆准确率。38 条独立开发契约另行运行，38/38；检索/交付为 11/11，遗忘泄露 0/10，详见 `memory-contracts.json`。本批没有新增真实模型遗忘测试，标记 `not_run`，不能用人格样本代替。

### 留存问题

- `persona_game` 修正后仍补充“还能接着打”；用户只说输了，未提供继续游戏的事实。
- `holdout_unhealthy_claim` 仍有“眯着眼找错字”的讥讽感，原有规训倾向尚未完全消除。
- `holdout_requested_advice` 给了一个办法，但“坐这儿琢磨怎么排顺序”补充了未给出的行为。
- `holdout_corrected_plan` 最终事实正确，纠正轮“是我记岔了”却把用户变更说成了自己记错。
- 修正后仍有个别口癖起句；原始角色风格保留，未用后处理强删。
- `holdout_cloud_chat` 的第二次表达在请求明确带 `json_object` 时仍返回普通带表情标签文本，严格校验拒绝；没有重试掩盖失败。修正前周报与纠正地点也出现格式失败。该协议问题仍未解决。

## 中间轮与评测修正

`diagnostic/` 保留四轮开发输出及对应 holdout 输出，包含失败和未采用的提示效果。前期脚本直接创建客户端，漏了桌面已有的 `json_response=True`；其格式失败不能直接当作桌面故障。诊断共 88 次 API、164,492 provider token；正式对照另为 44 次、79,808 token，本批合计 132 次、244,300 token。中间轮标为 `after-final` 的文件只是当时命名，正式交付以目录顶层的 `production-after.json` 为准。

这也补充更正上一批 `desktop-acceptance-20261030/flash-persona-live.json` 的范围：它使用相同的直接创建客户端方式，属于实际模型调用，格式设置与桌面不同。保留历史原始输出，不重写为通过。

修正工具为 `tools/companion_flash_eval.py`，直接复用生产工厂；记录响应格式，避免以后再误配。复现当前版本：

```powershell
$env:PYTHONUTF8='1'
$env:QT_QPA_PLATFORM='offscreen'
python tools/companion_flash_eval.py --dataset docs/modernization/evidence/persona-refinement-20261030/combined.json --output artifacts/codex_handoff/persona-refinement/rerun.json
```

应用模型须启用并配置为 `deepseek-flash`。复现旧版本可额外传 `--repo <9f606fc工作目录>`。API 原始请求仅记录正文，不记录认证头。

## 窗口与回归

- 新增布局 3 项先失败，提示约束 3 项先失败，去除占位回复测试另复现失败；相关红绿记录保留。
- app、桌宠和布局测试 **125 passed**；表达、人格与 prompt 预算相关 **156 passed / 1 skipped**。
- 最终完整回归 **1654 passed / 5 skipped / 3 warnings，220.99 秒**。4 项显式 provider 测试未启用、1 项 Windows 符号链接限制；真实模型验证单独如上。警告为两项 websockets 弃用和既有端口占用测试的线程 SystemExit。
- `QT_QPA_PLATFORM=windows` 原生窗口测试 **3 passed，3.78 秒**：实际创建并显示窗口，检查 600/760 高度、滚动到最下方按钮及桌宠返回后的可达性。这不是 offscreen，也不是人工点击验收。
- 原生测试日志出现 `0x8001010D`。这是 COM 同步输入调用期间禁止出站调用的错误码；Python faulthandler 先打印诊断再交后续处理。该进程随后正常完成 3 项测试，不能单凭“fatal”字样认定崩溃；具体 native 调用者未定位，未关闭诊断。[微软错误定义](https://learn.microsoft.com/nl-nl/windows/win32/com/com-error-codes-3)、[本机 Python 3.11.9 对应源码](https://raw.githubusercontent.com/python/cpython/v3.11.9/Modules/faulthandler.c)。
- Computer Use 工具连续返回 `Computer Use helper already has an active request`；重连和重置后仍失败，已停止工具操作，关闭本批启动的验证进程。本批未完成新的鼠标点击/截图验收，不把上一批截图当本批证据。

仍需后续处理模型局部语气/臆测、格式失败，以及工具恢复后的人工窗口体验核验；不宣称人格全面达标。没有改动用户存档，没有推送或创建 PR。
