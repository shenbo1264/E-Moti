# E-Moti 插件开发指南

插件接口为 E-Moti 独立设计，当前 API 主版本为 `1`。本地插件放入 `<user_data>/plugins/installed/` 后，还需要在插件中心明确启用。

## 1. 生成骨架

```bash
python tools/scaffold_emoti_plugin.py \
  --target plugins/my_plugin \
  --id emoti.community.my-plugin \
  --name "My Plugin"
```

结构校验：

```bash
python tools/validate_emoti_plugin.py plugins/my_plugin
```

可信源码可以加 `--activate`，在临时 Runtime 中执行一次激活与卸载：

```bash
python tools/validate_emoti_plugin.py plugins/my_plugin --activate
```

## 2. 一个最小动作插件

Manifest：

```json
{
  "schema_version": 1,
  "id": "emoti.community.hello",
  "name": "Hello Plugin",
  "version": "0.1.0",
  "api_version": "1",
  "entrypoint": "plugin.py:activate",
  "default_enabled": false,
  "permissions": ["actions.register"],
  "dependencies": []
}
```

入口：

```python
from guanghe_companion.plugin_api import ActionDefinition, ActionResult


def activate(ctx):
    ctx.register_action(
        ActionDefinition(
            action_id="hello.wave",
            label="挥挥手",
            handler=lambda request: ActionResult(
                speech="星汐朝你挥了挥手。",
                motion="Default",
            ),
        )
    )
```

## 3. 提交游戏状态变化

插件无法直接修改 `coins`、`inventory`、`trust` 或存档。需要结算的行为通过 `HostCommandProposal` 返回：

```python
ActionResult(
    speech="要一起玩吗？",
    command_proposals=(
        HostCommandProposal(
            command_type="companion.interaction",
            payload={"action_id": "play"},
            requires_confirmation=True,
        ),
    ),
)
```

宿主检查命令类型、玩家确认和当前状态，再调用原有 Controller。

## 4. 新增记忆规则

```python
from guanghe_companion.plugin_api import MemoryProposal, MemoryRuleDefinition


def rule(event):
    if event.event_type != "plugin.emoti.community.example.completed":
        return ()
    return (
        MemoryProposal(
            proposal_id="emoti.community.example:first",
            kind="共同日常",
            title="第一次共同完成",
            summary="你们一起完成了一件小事。",
            source="plugin:emoti.community.example",
            source_ids=(event.event_id,),
            tags=("第一次",),
        ),
    )


def activate(ctx):
    ctx.register_memory_rule(
        MemoryRuleDefinition(rule_id="example.first", handler=rule)
    )
```

记忆提案需要真实事件来源。原始屏幕内容、窗口标题、剪贴板和代码正文不能进入长期记忆。

## 5. 新增 Companion Skill

```python
from guanghe_companion.plugin_api import SkillDefinition, SkillResult


def activate(ctx):
    ctx.register_skill(
        SkillDefinition(
            skill_id="local.chime",
            title="播放星铃",
            description="播放一声本地提示音",
            requires_confirmation=True,
            handler=lambda request: SkillResult(speech="叮。"),
        )
    )
```

`requires_confirmation=True` 的 Skill 必须携带当前玩家确认，旧授权不能复用。

## 6. 新增 UI 区域

首版插件提供 ViewModel，不直接返回任意 QWidget：

```python
ctx.register_ui_panel(
    UiPanelDefinition(
        panel_id="example.panel",
        title="示例页",
        navigation_group="扩展",
        view_model=lambda request: {"count": 3},
    )
)
```

宿主使用统一组件渲染，插件主题无法破坏主窗口布局。

## 7. 新增可替换服务

定义接口：

```python
ctx.define_service(
    ServiceDefinition(
        service_id="emoti.weather",
        version="1",
        description="天气查询",
        required_methods=("current",),
    )
)
```

提供实现：

```python
ctx.register_service_provider(
    ServiceProviderDefinition(
        provider_id="emoti.weather.local-cache",
        service_id="emoti.weather",
        provider=my_provider,
        priority=10,
    )
)
```

Provider 插件应依赖 Definition 插件。

## 8. 测试要求

每个插件至少覆盖：

- Manifest；
- 激活；
- 贡献项可见；
- 核心行为；
- 卸载后贡献项消失；
- 权限不足；
- 重启后的插件数据；
- 错误不影响宿主；
- 本地安装后不会自动启用；
- 卸载后贡献项全部撤销。

本包自带：

```bash
python tools/run_plugin_smoke.py
python -m pytest -q
```
