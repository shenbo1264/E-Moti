# 合并后桌面与人格验收 — 2026-10-30

基线：`79c83776eb8279f75cec0cf9f7869fe6fbf6dcdc`，已合并 [PR #5](https://github.com/shenbo1264/E-Moti/pull/5)。Codex 按用户要求暂代 Claude，改动留在 `codex/desktop-acceptance`。本目录样本均为测试输入，未使用真实个人存档；凭据未保存。

## 实现与验证

- 普通第一人称连续偏好支持“也/还”，重复的前一事实不会阻止后句；句号、转述和未知主语终止继承。澄清的口头回复与内部诊断分离。
- 明确“先别说话”等直接请求走控制器本地短答与现有持久冷却，跳过抽取、语义召回和模型表达；同步、Qt 异步和宿主路径一致。引述、假设不触发。
- 桌宠回忆提示缩为可点击短文案，完整信息保留在提示中；使用不透明背景避免文字叠底和点击穿透。待确认按钮独立成行，窗口随内容增高。

三个切片均先复现失败。最终相关 UI/领域测试 160 passed；完整 `python -m pytest -q -rs` 为 **1650 passed / 5 skipped / 3 warnings，281.59 秒**。4 项显式真实 provider 测试未启用，1 项因 Windows 符号链接限制跳过；另外执行了下面的真实模型调用。警告包括两项 websockets 弃用，以及端口占用测试中的 uvicorn 线程 SystemExit；保留于 `full-final.log`，未隐藏。

`memory-contracts.json`：38/38，检索命中 11/11、prompt 交付 11/11、过时内容 0/6、遗忘内容泄露 0/10。这是开发契约，回答正确率与人格行为不由它估计。执行环境 `PYTHONUTF8=1`、测试 Qt 为 offscreen、临时数据放 ignored artifacts；原始真实窗口另用 Windows 平台。

## 实际模型与匿名评审

沿用应用当前设置 `deepseek-flash`，30 秒超时，4096 输出预算。没有修改旧 Pro 报告。`flash-persona-live.json` 保存实际请求、回答、provider usage 与延迟。复用现有 companion live eval 的 Qt service 链路；7 个原有 persona 场景另加 1 个先存入核桃过敏、重新打开再询问的有依据样本。

| 场景 | 模型状态 | API 次数 | 实际 token | API 耗时合计 ms |
| --- | --- | ---: | ---: | ---: |
| rest | completed | 1 | 2446 | 5375 |
| tease | completed | 2 | 2623 | 5790 |
| opinion | completed | 1 | 2081 | 2874 |
| refusal | failed / invalid_json | 2 | 2199 | 2755 |
| game | completed | 2 | 2448 | 3680 |
| work | completed | 2 | 2530 | 4943 |
| emotion_fact | completed | 1 | 2286 | 4736 |
| grounded_allergy_emotion | completed | 1 | 2746 | 6433 |

合计 12 次 API、19,359 provider token，包含抽取与表达，不含另行进行的窗口手动验证。API 耗时不等于整条桌面交互延迟。refusal 的模型实际返回带 `[calm]` 的普通文本，未满足 JSON 协议，用户可见兜底重复了拒绝指令。该失败保留；随后本地控制器修复安静请求并在真实窗口验证，**没有把它重记为模型通过**。

匿名评审采用随机顺序和无模型身份的包，身份映射仅在评审后揭示。两名独立 AI 只读取 `blind-packet.json`，对应 Claude 留下的两模型各 7 条 post-fix 回答；两份评审均为 **10 pass / 4 partial / 0 fail**。`blind-mapping.json` 可还原原始案例。主要问题是周报外层角色感弱、重复“唔/桌角”、无 seed 的过敏题不足以证明记忆稳定。评审完成后其中两名评审者才参与修复。

当前 Flash 另交独立 AI 读取 `current-blind-packet.json`，结果 **3 pass / 5 partial / 0 fail**，详见 `current-review.json` 与映射。部分回答加入未表达的自责、提醒带规训语气、擅自安排收尾工作；原始过敏题仍缺 seed。新增有依据的核桃样本正确引用记忆，只有 1 例，不能推算整体正确率。这两批是 **AI 匿名评审，人工盲评仍未完成**，不同模型不是严格同条件能力排名。

## Windows 实际窗口

使用独立测试存档启动真实 `PluginEnabledCompanionController` 与 `CompanionWindow`，未触碰用户存档；验证结束已停止此次测试进程。初次窗口启动未正确向 UI 暴露启用模型设置，产生本地回复，不能算模型证据；随后修正验证装配，真实 Flash 完成桂花茶聊天。

- `window-before-receipt.*`：修复前长回忆提示截断、透明背景叠字。
- `window-fixed-pending.*`：修复后输入框可用，待确认与回忆入口完整显示。实际蓝莓/油腻陈述产生保存和待确认结果。
- `window-memory-source.*`：点击回忆入口返回主窗口，最大化后选择桂花茶事实，显示普通聊天来源、原话、理由、确认状态和版本。
- `window-quiet.*`：发送“别烦我，先别说话了。”，得到“好，我先安静待着。”，无模型兜底复述。

截图只记录所测窗口；这里未声称已经验证所有分辨率、DPI、麦克风、音箱、托盘和取消交互。忘记/删除未通过图形界面执行，本批遗忘证据来自上述开发契约。

## Claude 恢复后的已知事项

1. 普通大小主窗口在当前显示环境下底部操作显示不完整，最大化可使用；需要继续做主窗口尺寸适配。
2. 不相关的否定偏好“太甜/油腻”落在同一宽泛 slot，后者进入待确认；本批保留受控行为，未扩大自动覆盖。
3. 人格尚有套话、过强建议与第三人称动作生硬的问题。真实窗口曾出现“是从桌角轻轻探出头来”；保留问题，不据测试数量宣称人格完成。
4. 人工盲评、更多真实共同记忆场景、其他屏幕配置与音频体验仍待验证。手机与长程工作范围仍暂停新增。

本批没有存档迁移或默认角色/资源替换。继续修改前读取当前分支，避免双方同时改 `app.py`。
