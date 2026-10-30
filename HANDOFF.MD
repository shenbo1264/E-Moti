# 核心后端与宿主交接

## 2026-10-30：Claude 桌面接入后的后端修正

当前后续工作以 Claude `5dd8c4e` 为基线，独立目录 `<WORKSPACE>`、分支 `codex/core-followup`。Claude 已完成桌面异步聊天、记忆设置与来源展示；不再按下面旧记录重复接入界面。自然话题遗忘、受控计划记录/纠正、候选有效期以及纠正本轮历史失效已补齐，接入接口不变。详见 `docs/handoff/20261029/claude-backend-followup-20261030.md`。

环境中的 OpenAI/DeepSeek 凭据返回 HTTP 401，不能用于本轮模型验收；桌面应用的独立 DeepSeek 配置可调用，凭据仅进程内使用。保留真实输出、初轮 bad case 与修复后复测；角色仍有将自己的话归给用户的问题，不宣称人格全部通过。

本批最终完整回归 1617 passed / 5 skipped，38 条契约全过；真实生成 12 次、36,723 provider token。纠正后旧地点已不进入后续 prompt，真实回答仅引用新计划地点。原始输出与警告说明在 `docs/modernization/evidence/backend-followup-20261030/README.md`。

## 2026-10-30：桌面记忆与陪伴优先

手机已有提交与代码全部保留，暂停新增移动/观察/远控范围。当前后端从 `0f96f94` 继续；重新核对公开 main 仍为 `b9f2009`、开放 PR 为零。Claude 目录独立保留，其最新已见提交 `a1aabeb` 已包含桌面待确认提示；没有合并或修改其分支。

普通聊天已接现有 PluginEnabled controller，支持受控事实、持久候选、自然纠正/遗忘及旧明确记忆匹配。候选和回执复用原 SQLite document，迁移仅用副本测试。画像、章节、历史推理窗口、语义缓存和在途回复沿 epoch 失效；遗忘命令包含的原话也不会重入后续 prompt。

`DesktopDialogueService` 是现有窗口的异步接入模块：只接同一 controller，背景做 ONNX/模型抽取/表达，Qt 线程验证与提交。原同步输入已具备本地事实处理，界面接入该服务后启用语义抽取和等待语义召回。不得在 Qt 线程等待 Future。取消、切角、模式或来源变化会拒绝迟到提议；实际模型只返回候选，不能自报身份权限或直接写事实。接口及 Claude 调用见 `docs/handoff/20261029/core-integration-20261030.md`。

真实中文 embedding 使用 FastEmbed 0.9.1 + 固定 revision 的 BGE-small-zh-v1.5/ONNX CPU；可选依赖 `.[semantic]`，模型缓存可重建，不含第二份长期事实。真实事件自动巩固为带来源的正文章节，撤回后重建。有限关系表达与兴趣/回忆候选复用原人格、主动门控；冷却、拒绝、最近聊天时间按角色持久保存。逻辑时间不是 Unix 日期。

实际模型已经运行。正式桌面设置与环境代理设置不同：前者 `deepseek-v4-pro` 可调用，后者的代理未运行；没有修改设置或记录密钥。30 个独立 holdout 回答、3 个桌面茶饮回答及规则外称呼抽取/表达已保存。实测 512 token 全被推理耗尽无正文，生产 DeepSeek 默认预算已修为 4096。模型评测超时 60 秒，现有用户设置 30 秒，有一条响应 32.21 秒；不把工具成功外推为全部现配置可用。仍有虚构感官/过去印象，不能宣称人格质量全面通过。详情与原始证据位置见 `docs/modernization/holdout.md`。

已将合成场景的原始模型回答、逐例评审、桌面链路和38条契约记录保留到 `docs/modernization/evidence/core-20261030/`，可随集成提交查看。自然称呼与原别名画像共用来源绑定，删除新称呼不会从旧state恢复旧称呼。

保留旧 38 条开发契约，最新执行 38/38。最终完整回归 **1549 passed / 5 skipped**（4项真实provider需显式启用，1项平台符号链接限制），2项既有websockets弃用警告。完整测试需 `PYTHONUTF8=1`（本机默认 cp1252 会使原有中文工具失败），临时数据使用 `artifacts/codex_handoff/`。语义模型测试使用真实缓存；真实生成集成测试已单独实际执行并保存输出，不能把跳过算通过。最终回归记录见该目录 `core-delivery-final.log`。

## 2026-10-29 宿主交付历史

当前共同基线：`09c048b0a82b592d0c6e90e0ecd273f0329e6031`。公开 main 实际仍为 `b9f2009`，没有开放 PR；本机旧工程 main 为其祖先 `e840d77`，工作区干净。源码包本身没有 Git，因此从公开 main 独立克隆后应用一份累计补丁，未覆盖原目录。

后端分支 `codex/host-backend`，Claude 分支 `claude/product-ui`，两者拥有独立目录。Claude 的基线不含本批后端后续改动；接入应读取 `docs/handoff/20261029/host-integration.md` 并使用后端接口实现，不重新实现领域状态。

宿主入口：`python -m guanghe_companion.host_runtime --data-root <隔离目录>`；可选依赖 `.[host]`。桌面装配传入窗口现有 PluginEnabled controller，并连接 snapshot_changed 到原快照刷新，以传播 TTS 取消。独立入口与旧桌面不能同时写相同数据目录。

`prepare_host_dialogue` / `complete_host_dialogue` / `cancel_host_dialogue` 属于控制器创建线程；只有 immutable request 的 expressor 调用移到 worker。取消后仍需 complete 回收 ticket。不要绕过 generation、epoch 或认证授权检查。手机正文不能选择 owner/character/authority。

测试进程使用 `PYTHONUTF8=1`，因为本机默认 cp1252 无法打印既有工具的中文；不修改系统编码。基线另外存在跨时区日期 fixture 和文档触发旧 hygiene 词匹配的问题，本批只修 fixture 日期和普通文档措辞，保留原断言。

Relay 核查 HEAD `ec5563fb709e7db6eef810326d8d80db77c65787`：Tauri 内部命令可用，认证网络入口及 command receipt 查询尚未对外提供。没有改 Relay、Game Companion 或 Body。runner 默认保留 authority_unavailable，不派发；真实跨小时、断网、取消证据尚缺。

被动观察保持关闭；手机完整缓存/音频撤回仍需客户端实现协议。真实手机、真实模型行为、embedding 效果和自动人格演进未验或未实现，不用本地契约通过替代。

本批完整回归1425通过/1跳过（平台符号链接），最后时钟同步补充16通过，原38条memory契约全部通过；真实HTTP和独立宿主进程重启通过。详细证据与缺项见 `docs/handoff/20261029/host-verification.md`。当前没有新的存档迁移，记忆仍走既有V2权威存储。
