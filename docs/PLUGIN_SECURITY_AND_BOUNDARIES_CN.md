# E-Moti 插件安全边界

## 当前信任模型

首版插件与 E-Moti 在同一个 Python 进程中运行。内置插件、本地自制插件和经过源码审查的插件可以使用。未知来源插件保持默认关闭。

Manifest 权限承担三项工作：

1. 向玩家展示能力范围；
2. 限制插件通过 `PluginContext` 获取宿主能力；
3. 为后续子进程沙箱保留稳定权限名。

Python 源码仍然具备当前用户进程的系统权限。Manifest 无法拦截恶意代码直接导入 `os`、`socket` 或其他库。插件中心需要明确提示这一点。

## 启动安全

- 内置插件可声明默认启用；
- 本地安装插件需要玩家明确启用；
- 非法 Manifest 和激活失败不会阻断无关插件；
- 重复 ID 不允许覆盖内置插件；
- 损坏配置回退到安全默认值；
- 插件错误写入脱敏 Boot Report。

## 游戏权威状态

插件得到的 `state_snapshot` 是递归只读结构。状态变化通过 `HostCommandProposal` 提交，Controller 执行：

- 命令白名单；
- 当前状态检查；
- 玩家确认；
- 本地结算；
- 事件生成；
- 存档。

插件无法直接改金币、背包、信任、关系、目标和存档。

## 凭据

API Key 不进入：

- `emoti-plugin.json`；
- `user_data/plugins/config.json`；
- 插件本地 `state.json`；
- 日志；
- Smoke 报告；
- 公开 ZIP。

外部服务插件声明 `credentials.use`，配置保存 `credential_alias`。正式仓库的 Credential Broker 按调用返回授权客户端或临时令牌，插件配置不保存原值。

## 记忆

`memory.propose` 只提交候选。宿主检查：

- 必填字段；
- 提案 ID；
- 真实来源事件；
- 屏幕内容标记；
- 玩家确认；
- 角色命名空间；
- 重复与覆盖关系。

屏幕摘要只服务当前表达。经玩家确认并实际完成的共同事件可以形成回忆。

## 网络、文件与定时任务

以下权限需要显式授权：

```text
network.http
filesystem.external
timer.background
screen.summary.read
credentials.use
```

当前 Overlay 没有向插件暴露通用网络、外部文件或后台定时器对象。正式合入时使用窄接口、超时、取消、日志脱敏和权限复核。

## 发布前检查

1. `python -m pytest -q`
2. `python tools/run_plugin_smoke.py`
3. 校验每个 Manifest
4. 检查插件源码与许可证
5. 扫描 API Key、Token 和私有配置
6. Windows GUI Smoke
7. 构建后再次扫描成品目录
8. 记录内置插件哈希和版本
