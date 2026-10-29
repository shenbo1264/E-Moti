# 宿主后端交接

当前共同基线：`09c048b0a82b592d0c6e90e0ecd273f0329e6031`。公开 main 实际仍为 `b9f2009`，没有开放 PR；本机旧工程 main 为其祖先 `e840d77`，工作区干净。源码包本身没有 Git，因此从公开 main 独立克隆后应用一份累计补丁，未覆盖原目录。

后端分支 `codex/host-backend`，Claude 分支 `claude/product-ui`，两者拥有独立目录。Claude 的基线不含本批后端后续改动；接入应读取 `docs/handoff/20261029/host-integration.md` 并使用后端接口实现，不重新实现领域状态。

宿主入口：`python -m guanghe_companion.host_runtime --data-root <隔离目录>`；可选依赖 `.[host]`。桌面装配传入窗口现有 PluginEnabled controller，并连接 snapshot_changed 到原快照刷新，以传播 TTS 取消。独立入口与旧桌面不能同时写相同数据目录。

`prepare_host_dialogue` / `complete_host_dialogue` / `cancel_host_dialogue` 属于控制器创建线程；只有 immutable request 的 expressor 调用移到 worker。取消后仍需 complete 回收 ticket。不要绕过 generation、epoch 或认证授权检查。手机正文不能选择 owner/character/authority。

测试进程使用 `PYTHONUTF8=1`，因为本机默认 cp1252 无法打印既有工具的中文；不修改系统编码。基线另外存在跨时区日期 fixture 和文档触发旧 hygiene 词匹配的问题，本批只修 fixture 日期和普通文档措辞，保留原断言。

Relay 核查 HEAD `ec5563fb709e7db6eef810326d8d80db77c65787`：Tauri 内部命令可用，认证网络入口及 command receipt 查询尚未对外提供。没有改 Relay、Game Companion 或 Body。runner 默认保留 authority_unavailable，不派发；真实跨小时、断网、取消证据尚缺。

被动观察保持关闭；手机完整缓存/音频撤回仍需客户端实现协议。真实手机、真实模型行为、embedding 效果和自动人格演进未验或未实现，不用本地契约通过替代。

本批完整回归1425通过/1跳过（平台符号链接），最后时钟同步补充16通过，原38条memory契约全部通过；真实HTTP和独立宿主进程重启通过。详细证据与缺项见 `docs/handoff/20261029/host-verification.md`。当前没有新的存档迁移，记忆仍走既有V2权威存储。
