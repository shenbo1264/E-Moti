# E-Moti Plugin Runtime 架构说明

## 1. 目录

```text
<app_root>/plugins/<plugin-folder>/
  emoti-plugin.json
  plugin.py
  README.md
  assets/                         # 可选

<user_data>/plugins/installed/    # 玩家手动安装
<user_data>/plugins/config.json
<user_data>/plugins/data/<hash>/state.json
```

插件代码与数据分开保存。禁用或卸载插件不会自动删数据；玩家可在插件中心清理。

## 2. Plugin Host

`PluginHost` 负责桌面应用启动链路：

```text
读取配置
→ 扫描内置与本地插件
→ 逐个校验 Manifest
→ 计算启用集合
→ 按依赖闭包激活
→ 返回 Boot Report
```

启用规则：

- 内置插件可使用 `default_enabled`；
- 本地安装插件只接受配置中的显式启用；
- 配置中的显式禁用优先；
- 损坏配置回退到安全默认值并保留警告。

故障隔离：

- 非法 Manifest 记入 discovery failure；
- 重复 ID 保留先发现的插件，后者记入 failure；
- 一个插件激活失败后回滚其依赖闭包；
- 无关插件继续加载；
- 主程序可以继续启动并在插件中心显示错误。

## 3. Manifest

`emoti-plugin.json` 声明：

- `id`、名称和语义版本；
- Plugin API 版本；
- Python 入口；
- 默认启用状态；
- 权限；
- 必需或可选依赖；
- 无密钥默认设置；
- 插件中心展示用 contributions 元数据。

入口必须位于插件目录内。绝对路径、`..`、错误后缀、缺失文件和 symlink 逃逸都会被拒绝。Manifest 设置中出现非空 `api_key`、`token`、`password` 或 `secret` 会验证失败。

## 4. 生命周期

```text
discover
→ validate
→ dependency plan
→ API compatibility check
→ PluginContext
→ activate(ctx)
→ loaded
```

卸载：

```text
插件 cleanup
→ UI / Service / Memory / Context / Skill / Action / Listener 注销
→ 动态模块移出 sys.modules
→ unloaded
```

激活中途抛错会回滚已经完成的注册。事件监听报错只进入 `EventDispatchReport`，其他监听器继续执行。

## 5. 权限

### 常规权限

```text
events.subscribe
events.publish
actions.register
skills.register
context.provide
memory.propose
ui.register
services.register
storage.local
game.snapshot.read
```

### 敏感权限

```text
screen.summary.read
network.http
credentials.use
filesystem.external
timer.background
```

敏感权限需要显式授权。当前 Overlay 完成声明、配置和门禁；正式仓库由 Capability Broker 提供窄接口。插件不会直接拿到 API Key。

## 6. Extension Registry

每个注册项保留 owner plugin id：

- 全局 contribution id 冲突会阻止后加载插件；
- 注册顺序稳定；
- Context Provider 和 Memory Rule 支持 order；
- Service Provider 使用 priority；
- 卸载时只移除当前 owner 的注册。

## 7. Event Bus

支持：

```text
companion.event.settled
plugin.*
*
```

插件只能主动发布到自己的 `plugin.<plugin_id>.*` 命名空间。宿主事件由 Host 创建。Payload 和游戏快照都会递归转成只读结构。

## 8. Service Seam

```python
ServiceDefinition(
    service_id="emoti.voice.tts",
    version="1",
    description="角色语音合成",
    required_methods=("synthesize",),
)
```

```python
ServiceProviderDefinition(
    provider_id="emoti.voice.tts.edge",
    service_id="emoti.voice.tts",
    provider=edge_provider,
    priority=10,
)
```

Runtime 会检查 Provider 是否实现所需方法。默认选择优先级最高者，宿主也可以指定 provider id。

## 9. Story Bridge

`PluginStoryBridge` 连接现有记忆系统：

- 已结算 Domain Event 广播给插件；
- `MemoryProposal` 经过安全检查后写入情感记忆；
- `plugin_proposal_id` 保证幂等；
- 标记为屏幕原始内容的提案会被拒绝；
- 插件上下文位于 `plugin_context` 命名空间；
- Action 和 Skill 产生的事件使用同一条处理链。

## 10. 配置与插件中心

`PluginRuntimeConfiguration` 保存：

- 显式启用与禁用；
- 敏感权限授权；
- 无密钥设置覆盖。

`PluginCatalogItem` 提供：

- 名称、版本、描述；
- 当前加载状态；
- 权限与敏感权限；
- 依赖；
- 贡献项；
- 权限复核状态。

正式 PySide6 页面只使用 ViewModel，不直接修改 Runtime 内部字典。
