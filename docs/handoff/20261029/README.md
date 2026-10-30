# E-Moti：Claude 产品/前端 × Codex 后端交接

2026-10-30 优先级已更正：当前主线为现有桌面的记忆、共同经历、人格与自然陪伴。保留全部手机工作，暂停新增手机范围。下文旧的手机优先顺序已失效；当前实现、接入及未验项见 [核心接入说明](core-integration-20261030.md)。

日期：2026-10-29（America/Los_Angeles）。本包汇总完整需求、保留前两批源码/研究/测试，补充iOS官方资料，并给出两份可以直接启动开发的提示词。本次交接修改文档，不新增生产功能。

## 必须先知道

**平台更正：移动端是 Android/HyperOS、iPhone/iOS、华为手机原生HarmonyOS。此前macOS为口误，当前不开发Mac桌面客户端；iOS所需Mac/Xcode属于构建条件。**

E-Moti保持独立人格与共同记忆，工作/游戏/观察能力可选。Claude负责产品与前端实际开发；Codex负责后端、宿主与接口。开发分工不限制E-Moti将来可连接的执行者种类，不授权重构Relay或开发Body固件。

## 使用顺序

1. 解压完整包，从包根 `00_START_HERE_CN.md` 选择已有仓库的接入方式。包内源码已经累计包含旧两批升级，无需把旧包再覆盖一遍。
2. 先让Codex按 [后端提示词](CODEX_PROMPT.md) 检查最新分支/PR/未提交改动并建立共同基线。Claude可以同步只读需求和现有UI。
3. 将 [前端提示词](CLAUDE_PROMPT.md) 交给Claude。两者从同一基线的独立worktree/分支工作，遵守 [文件分工](work-allocation.md)。
4. 第一条真实切片是手机与同角色聊天、记忆确认/纠正/遗忘；随后接实际Relay任务、阶段汇报和长程监督。先打通一条实际链路，再扩展观察与其他手机。

无需先购买iPhone/Mac或开放手机全局观察，便可开始Android和宿主开发。实际平台构建/设备/凭据缺项由接手者具体记录，不能用模拟输入替代验收。

## 本包阅读索引

| 文件 | 用途 |
|---|---|
| [requirements.md](requirements.md) | 全量需求、平台更正、18组责任映射和评测口径 |
| [current-state.md](current-state.md) | 已实现/已测/未验、两批提交、真实代码导航 |
| [work-allocation.md](work-allocation.md) | Claude/Codex职责、单写文件、接口协作和第一条闭环 |
| [platform-scope.md](platform-scope.md) | 三种手机的实施方案与权限差异 |
| [ios-research.md](ios-research.md) | 新补的Apple官方研究，版本/地区/签名条件 |
| [acceptance.md](acceptance.md) | 伙伴记忆、任务、观察和真实评测的验收场景 |
| [CLAUDE_PROMPT.md](CLAUDE_PROMPT.md) | Claude完整启动提示词 |
| [CODEX_PROMPT.md](CODEX_PROMPT.md) | Codex完整启动提示词 |

前两批完整资料仍在 [modernization](../../modernization/README.md)：Personal Agent/Companion/Memory调研、许可证取舍、源码审计、差距矩阵、架构、迁移、benchmark、真实bad case、路线图和求职总结；[mobile](../../modernization/mobile/README.md) 保留任务/设备研究与验证。历史证据按原日期保留，旧Mac研究不再列入当前任务。

## 状态摘要

已有记忆/人格主链、来源失效和用户管理升级；新增任务journal与RAM观察门控。最新生产代码历史全量结果 **1390 passed / 1 failed**，新增任务/观察测试 **57 passed**；38条memory开发契约全部通过，本地任务演示18/18。详细口径和唯一旧Linux失败见 [current-state.md](current-state.md)。

尚无Android/iOS/华为手机安装包、认证远程服务、真实Relay联通、持续runner或手机观察完整派生撤回。这些是接下来要实现和实测的工作。
