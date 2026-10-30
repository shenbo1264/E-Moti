# 桌面核心记忆与陪伴接入

更新：Claude 已在 `dbc12d2`/`5dd8c4e` 完成本页所述窗口接入。后续明确计划、自然遗忘和纠正历史失效行为以 `claude-backend-followup-20261030.md` 为准；下文暂时计划不保存的描述是本批之前的边界。

本批基于后端 `0f96f94`，只扩展现有 V2、实际 PluginEnabled controller 和领域服务。公开 main 重新核对仍为 `b9f200955123790a5c66abcaf4e2567b3659a90e`，没有开放 PR。Claude 独立工作目录保留在 `<WORKSPACE>`，已新增桌面待确认提示与独立验收；未合并、覆盖或修改该工作目录。手机、Relay、观察范围暂停新增。

## 普通聊天与来源

原有 `submit_dialogue_request(DialogueRequest(...))` 直接进入普通聊天处理，无须“请记住”。本地快速处理明确偏好、居住地、职业、过敏、长期忌口、宠物、称呼及现实变化；否定保留否定含义，引用、假设、角色扮演、反话、暂时计划不自动保存。旧有明确记忆通过只读匹配视图参与纠正/遗忘，不重新扫描历史或导入已删除事实。

`DesktopDialogueService` 在快速处理未覆盖或目标需澄清时，为个人自述调用已启用的真实模型进行语义抽取。普通问题不额外调用抽取模型。工作线程只返回结构化提议；主线程校验原话片段、字面值、用户事实域、可信身份、epoch、generation、来源指纹、模式和冲突后再写入。模型遗漏的同字段冲突由宿主补充检查，不能自行宣布已确认。取消、切角或来源失效后提议丢弃。没有模型时保留本地有限覆盖，不宣称能理解所有自然语言。

`controller.set_chat_memory_mode("auto" | "review" | "off")` 按角色持久保存设置，默认 `auto`。`review` 只生成持久候选，`off` 禁止新推断，仍允许用户遗忘。明确自述可自动保存，冲突或指代不清才待确认/澄清；原“请记住”确认流程保持。

`controller.get_chat_memory_status()` 返回模式、最后处理结果、待确认数及语义状态。最后结果有 `status`（ignored/saved/pending/clarify/forgotten）、`message`、`memory_ids`。现有回忆册可查看、确认、纠正、遗忘；`source_details()` 新增 `provenance`，包括原话、消息 ID、说话者、场景、墙钟记录时间和提取理由。`occurred_at` 仍是现有逻辑时间，不能当现实日期。

候选及确认/拒绝回执进入原 SQLite document，兼容现有文档；没有第二套事实库。候选按来源去重，确认原子核对 epoch 与来源指纹。冲突确认替代旧版本；纠正保留原发生时间，现实变化用新发生时间。画像从获准偏好原文生成并绑定来源。旧事实、画像、章节、历史推理窗口、语义缓存及在途回复沿原失效路径撤回。包含原事实的遗忘命令本身也被排除在后续 prompt 外。

## Claude 的桌面接入

`app.py` 未在本批修改。普通聊天处理已在现有 controller 入口生效；异步语义/模型表达由桌面界面将提交调用接到以下服务后启用。不要在窗口外新建第二个 controller。

```python
from guanghe_companion.desktop_dialogue_service import DesktopDialogueService
from guanghe_companion.dialogue import DialogueRequest

# 在现有窗口/controller 所属 Qt 线程创建，窗口持有它至关闭。
self.desktop_dialogue = DesktopDialogueService(self.controller, parent=self)
self.desktop_dialogue.snapshot_changed.connect(self._apply_snapshot)
self.desktop_dialogue.failed.connect(self.show_dialogue_error)

# 需要语义召回时启用；返回 Future，不在 Qt 线程调用 result() 等待。
self.controller.enable_semantic_memory(cache_dir=model_cache)

# 原发送按钮/快捷键统一调用，Future 可取消；busy 时禁用再次提交。
future = self.desktop_dialogue.submit(DialogueRequest(text), include_ai_expression=True)
# 取消按钮：self.desktop_dialogue.cancel()
# 窗口关闭：先 self.desktop_dialogue.close()，再原 controller.close()
```

依赖安装：`python -m pip install -e ".[semantic]"`。FastEmbed 0.9.1 复用 ONNX CPU，模型初次下载约 95 MB，独立缓存目录。离线已有缓存可 `local_files_only=True`；不启用时仍使用词法路径。下载、抽取、推理和模型表达在工作线程，事实与 Qt 快照只在原控制器线程提交。准备期也保留串行占用；切角、撤回、取消使迟到结果失效。`failed` 显示真实错误，不以本地话术冒充模型回答。界面可调用 `controller.disable_semantic_memory()` 后明确选用词法路径；当前没有自动静默吞掉下载失败。

相册更新后继续走原快照刷新/TTS 取消路径；尤其是冲突确认已触发失效回调。不要把本地语音或未交付主动文案写成共同经历。

## 共同经历、关系和主动策略

已结算真实游戏事件、确认完成的陪伴行动自动触发巩固。章节按发生顺序使用真实事件正文及来源，预算裁剪同步裁剪来源，不再拼接标题；用户偏好不被称为共同经历。

`story_runtime.relationship_development(now=...)` 从至多六条有效共同经历给出有限熟悉表达指引、来源指纹及 epoch，进入实际 prompt。它不修改作者人格或赋予角色新性格；删除来源后重新计算。超预算时先移除该派生指引，保留当前输入、事实与 persona。

现有主动服务接受真实回忆与获准兴趣候选，继续使用安静时段、全局/分类冷却、日上限及拒绝退避。每条来源一天内不重复提及；主动话语本身不会生成新共同经历。拒绝记录、冷却计数与逻辑时钟按角色持久保存，重启不立即重复打扰。

## 实际证据和限制

可随提交查看的原始结果集中在 [实际证据目录](../../modernization/evidence/core-20261030/README.md)。

- `tools/desktop_memory_smoke.py` 通过真实 Qt 事件循环、实际 controller、关闭重开与真实中文 ONNX：普通乌龙茶/负甜偏好→低词重叠召回→红茶纠正→遗忘，10/10 检查通过。完整 prompt、来源、分数和延迟在 `artifacts/codex_handoff/desktop-memory-smoke.json`；prompt 为构造而未发送，生成行为 `not_run`。
- `tools/semantic_memory_benchmark.py` 五条开发探针：词法 2/5，语义融合 4/5。独立 holdout 事实交付 3/3，禁止片段命中 0/5；仍有漏召回与无关召回，详细 bad case 保存在 [holdout 说明](../../modernization/holdout.md)。小分母不代表总体质量。
- 先前环境凭据调用官方服务 401，环境中的 `127.0.0.1:3456/v1` 代理连接被拒绝，失败报告保留。之后读取正式桌面应用已启用的另一份配置，真实 `deepseek-v4-pro` 成功完成 10 条独立用例×3组回答。没有修改设置、输出凭据或启动其他项目。原始报告为 `artifacts/codex_handoff/holdout-saved-provider-combined.json`。
- 三组 current/no/semantic 总 token 分别 31054/27717/29486；完整响应中位数 19.12/19.13/17.90 秒，最大 32.21/23.99/28.75 秒。评测超时明确 60 秒，用户现有设置为 30 秒；至少一条不能外推为现配置下成功。回答语义质量须与逐例评审共同阅读，字面旧片段未命中不能当作全面零泄露。
- 语义抽取使用真实模型的四条开发样本通过，原话校验失败的早期 bad case 保留；它们不是独立 holdout。实测 512 输出预算全部耗于 reasoning 且无正文，生产 DeepSeek 默认预算已修为 4096，显式设置其他预算的客户端仍保留其选择。
- Claude 新增验收已运行并保存原始失败 `claude-independent-core.json`；看过后仅作为已见回归，其后报告为 `claude-observed-regression.json`。该工具调用同步本地路径，不启用语义抽取或准备 embedding，仍有未覆盖语言及短期计划案例，不能把它算成完整异步链路成绩。
- Claude 尚需在自己目录完成异步发送、模式/来源展示及真实桌面体验验收。本批没有替他修改界面，也没有把无模型的本地结果当体验验收。
- 实际桌面服务已另行完成三次真实茶饮表达及规则外称呼的抽取/表达，分别14/14和4/4检查通过；仍发现无依据感官措辞。实际GUI接入与产品体验验收仍由Claude完成。
- 旧 38 条开发记忆契约保留；本批迁移只在存档副本上验证。完整回归结果在 HANDOFF.MD 中记录。
