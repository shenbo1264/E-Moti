# DeepSeek Harness 的插件理念如何落到 E-Moti

## 参考范围

DeepSeek Harness 的官方文档把模型适配、工具、会话日志、Agent Loop 和 UI 放进同一棵插件树。插件向共享上下文注册服务、类型化事件和可撤销 effect；能力接口再拆成 Service Definition、Service Provider 和 Consumer。Profile、Bundle 与 patch layer 负责组合运行时。

E-Moti 保持 Python、PySide6、本地状态机和现有角色包。当前实现借用了插件注册、生命周期、事件与能力接缝的工程思路，没有引入 Cordis，也不与 DeepSeek Harness 插件协议兼容。

## E-Moti 采用的机制

### 1. 可撤销注册

动作、Skill、事件监听、记忆规则、上下文区、UI ViewModel 和 Service Provider 都返回注销句柄。卸载插件时，Runtime 按注册的相反顺序释放 effect，并从 `sys.modules` 清理动态模块。

### 2. 类型化事件

宿主已经结算的互动进入 `companion.event.settled`。插件自己的事件使用：

```text
plugin.<plugin_id>.*
```

需要长期保存的事实带 `durable=true`。插件事件、宿主事件和记忆提案都保留来源。

### 3. Capability Seam

可替换能力由三部分组成：

```text
Service Definition
→ Service Provider
→ Consumer
```

随附接口覆盖 LLM 表达、TTS、ASR、屏幕摘要和搜索。正式仓库可以逐个把现有实现接成 Provider Adapter，调用方只依赖稳定接口。

### 4. 分层启动

E-Moti 的 Plugin Host 扫描两层目录：

```text
<app_root>/plugins/                    内置插件
<user_data>/plugins/installed/         本地安装插件
```

内置插件可以声明默认启用。本地安装插件需要玩家明确启用。配置、权限和插件数据都写入 user-data。

### 5. 故障隔离

非法 Manifest、重复 ID 和激活失败会进入 Boot Report。无关插件继续加载，主程序仍能启动。插件激活过程中已经注册的内容会回滚。

## E-Moti 保留的宿主权威

E-Moti 的玩法依赖确定性结算。插件系统保留以下边界：

- 金币、背包、关系、信任、目标和存档由宿主规则修改；
- 插件读取递归只读快照；
- 状态变化通过 `HostCommandProposal` 交给 Controller 审核；
- 长期记忆通过 `MemoryProposal` 交给记忆层校验、去重和持久化；
- 屏幕摘要、网络、外部文件、凭据和后台计时属于敏感权限；
- 配置只保存凭据别名，不保存 API Key。

## 已实现的扩展点

| 扩展点 | 典型用途 | 当前接口 |
|---|---|---|
| 动作 | 新增看星星、拍照、小游戏等互动 | `register_action()` |
| Companion Skill | 玩家确认后的轻量能力 | `register_skill()` |
| 事件监听 | 观察结算完成的互动与关系事件 | `on()` |
| 插件事件 | 发送插件命名空间内的类型化事件 | `publish()` |
| 记忆规则 | 从真实事件提出纪念回忆 | `register_memory_rule()` |
| 表达上下文 | 给角色台词增加小型只读信息区 | `register_context_provider()` |
| UI 面板 | 向 PySide6 宿主提供通用 ViewModel | `register_ui_panel()` |
| Service Seam | 定义并替换 LLM、TTS、搜索等实现 | `define_service()` / `register_service_provider()` |
| 本地数据 | 每个插件独立 JSON 空间 | `ctx.storage` |

## 示例插件

`plugins/stargazing_moment/` 提供“一起看星星”互动：

```text
点击“一起看星星”
→ 插件返回角色台词和完成事件
→ 首次完成提出《第一次一起看星星》
→ 宿主记忆层校验并写入
→ 上下文区和“星图角落”面板显示累计次数
→ 第二次不重复生成第一次回忆
→ 卸载后动作、上下文、面板和记忆规则一并消失
```

`tools/run_plugin_smoke.py` 已完成这条链路的自动验证。

## 当前边界

首版 Runtime 使用同进程 Python 插件。它适合内置插件、本人开发的插件和经过源码审查的本地插件。Manifest 权限能够约束正式宿主接口，无法拦截恶意 Python 源码直接访问操作系统。

第三方插件公开分发前需要补齐：

1. 子进程隔离或受限执行环境；
2. 插件签名、来源、许可证和哈希；
3. 安装包路径穿越检查；
4. 版本范围与数据迁移；
5. 社区索引和撤回机制。

## 参考

- DeepSeek Harness README: https://github.com/deepseek-ai/deepseek-harness
- Architecture: https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md
- Extension cookbook: https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/extension-cookbook.md
- Adding a package: https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/adding-a-package.md
