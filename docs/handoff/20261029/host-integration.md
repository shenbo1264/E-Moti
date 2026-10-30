# 可运行宿主与 Claude 接入契约

2026-10-29。共同基线 `09c048b0a82b592d0c6e90e0ecd273f0329e6031`，来自公开 `b9f2009` 加累计开发包。后端分支 `codex/host-backend`；Claude 分支 `claude/product-ui` 从同一基线建立。没有推送、PR 或远端修改。

## 桌面装配

在现有 controller 所在线程创建宿主，传入 **窗口正在使用的 PluginEnabledCompanionController 实例**，不创建手机专用 controller。保留宿主和 server 对象至窗口关闭。

```python
from guanghe_companion.host_auth import DeviceCredentials
from guanghe_companion.host_service import CompanionHost
from guanghe_companion.host_runtime import HostServer

host = CompanionHost(controller, DeviceCredentials(data_root / "host-devices.sqlite3"))
host.snapshot_changed.connect(window._apply_snapshot)
server = HostServer(host, bind="127.0.0.1", port=8765)
# 用户启用连接后调用；局域网地址必须同时提供 certfile/keyfile。
server.start()
invitation = host.create_invitation()  # 当前 owner / 当前角色，300 秒有效、一次使用
# 窗口提供二维码/复制邀请码。凭据撤销：host.revoke_device(device_id)。
# 关闭：server.stop(); host.close()。controller 继续由窗口管理。
```

`snapshot_changed` 在 controller 线程发出；连接现有 `_apply_snapshot` 后，桌面既有 TTS epoch 取消路径会立即处理手机纠正/遗忘。Claude 主写 `app.py`，本批没有改窗口装配。手机同样必须按下文失效事件停止播放和清除内容。

网络操作经 Qt queued signal 串行进入现有 controller。模型只在单独工作线程读取准备好的请求；结果回到原线程验证 generation、角色与 memory epoch 后提交。单一会话忙时返回 409，不并发复用 expressor。取消阻止结果提交，不能取消已经发送给模型供应商的计算；工作线程回收前会话保持 busy。桌面同步聊天入口也会在此期间报告 busy，前端应禁用重复发送或显示状态。

## 独立启动

在后端工作目录执行：

```powershell
python -m pip install -e ".[host]"
python -m guanghe_companion.host_runtime --data-root artifacts/codex_handoff/host-demo
```

运行包含网络测试的完整套件时安装 `python -m pip install -e ".[host,test]"`；本机 Windows 测试使用 `$env:PYTHONUTF8='1'` 后执行 `python -m pytest`。

启动输出一次短期邀请码；默认仅监听 `127.0.0.1:8765`。这是使用隔离数据目录的可运行宿主，不会连接正在运行的桌面存档。若要使用桌面已有数据，优先按上面的同实例方式装配；独立宿主不能与旧桌面同时打开同一个数据目录。独立入口使用 `QLockFile` 排除第二个独立宿主。

局域网启动必须提供匹配连接地址的可信 TLS 证书和私钥：`--bind <本机IP> --certfile <证书> --keyfile <私钥>`。客户端校验证书或明确配对时固定证书信任，不能关闭证书验证。TLS 由 Uvicorn/Python SSL 提供，认证头由 FastAPI HTTPBearer 解析；邀请码与 bearer token 使用标准库 secrets 的 256 位随机值，数据库只保存 SHA-256 摘要。配对凭据有效期 30 天，过期重新配对；撤销立即阻止后续访问和迟到结果提交。数据库与私钥放用户运行数据目录，使用本机用户访问权限，不打包到仓库。

没有默认网络监听、开机启动、屏幕采集或任务执行。HTTP 服务禁用代理头信任及访问日志，响应 `Cache-Control: no-store`，请求体上限 16 KiB；配对入口只能兑换宿主先行创建的高熵邀请码，不能远程申请权限。当前配对授予该角色的聊天和记忆管理，不能访问其他角色、任务执行或观察权限。

## HTTP 契约

完整可生成 schema：`GET /openapi.json`。除配对外，以下请求携带 `Authorization: Bearer <access_token>`。身份、owner、允许角色由宿主凭据决定，正文中的 owner/character/authority 等额外字段返回 422。

| 请求 | 行为 |
|---|---|
| `POST /v1/pair` | `{invitation, device_name}` → `{access_token, token_type, device_id, expires_at}` |
| `GET /v1/session` | 当前 session_id、revision、character_id、context_epoch 与 capabilities |
| `POST /v1/messages` | 下述版本信息及 text → 202，返回 request_id、running/completed |
| `GET /v1/messages/{request_id}` | 当前设备的运行状态或已验证 speech/visual/intent；带 local/model、fallback_reason |
| `POST /v1/cancel` | 版本信息及原 request_id；取消本机发布，不声称远端停止 |
| `GET /v1/memory` | 现有 MemoryAlbumController 的 album，含待确认候选 |
| `GET /v1/memory/{memory_id}/source` | 当前来源、版本、有效期、确认状态 |
| `POST /v1/memory` | operation 为 remember / confirm / correct / forget |
| `GET /v1/events?after=0` | 失效事件、游标和 resync_required |

发送消息示例（版本从 session 响应取值）：

聊天和记忆正文沿用现有领域上限 240 字，记忆标题上限 60 字；超长请求返回 422，不静默截断。

```json
{"session_id":"<session_id>","expected_epoch":0,"expected_revision":1,
 "request_id":"phone-message-1","text":"你好"}
```

显式记忆操作使用相同四个版本/请求字段，另加：

```json
{"operation":"remember","text":"我的饮品是桂花茶"}
```

聊天“请记住……”只创建候选。用户确认按钮提交 `operation="confirm", pending_id="..."`；纠正提交 `operation="correct", memory_id="...", text="新事实", title="标题"`；遗忘提交 `operation="forget", memory_id="..."`。所有写入走现有 V2 事务和来源失效链。

同一设备在同一进程会话中重复相同 request_id 和内容不会再次写入；同 ID 不同内容返回 `request_conflict`。版本已失效的旧响应只返回 stale，正文被清除。请求记录保留到宿主关闭，最多 2048 个；达到容量返回 429，不自动丢弃去重记录。重启产生新的 session_id，旧写入请求返回 `session_changed`；先刷新实际状态，不能把未收到回执的旧写入改成新 ID 盲重放。记忆与历史本身沿用持久存储，网络请求去重不承诺跨重启自动重放。

## 失效与断线恢复

revision 是宿主上下文代数，切角色、取消、记忆失效和历史编辑时推进，解决 A→B→A 的同 epoch 重入。每次写入必须提交 session_id、expected_epoch、expected_revision。事件 `context_invalidated` 携带 `clear_cached_content=true`；不携带被撤销的文本。

客户端重连先读取 session 和事件，再显示缓存。session_id / revision / character_id / context_epoch 任一变化，清除旧消息、摘要、记忆页面与音频缓存，停止播放，放弃在途旧响应，再拉当前内容。事件游标过旧或超前返回 `resync_required=true`，执行相同刷新。已下载/播放内容与远端供应商已收到的数据不属于宿主可追回范围。

当前事件接口发布失效通知；消息结果和记忆列表由客户端查询，不承诺实时推送。被动观察 capabilities=false，设备观察尚未接入聊天/摘要/TTS；不得据此宣称已完成观察的全部派生撤回。

错误统一为 `{"error":{"code":"...","message":"..."}}`：401 凭据/邀请码无效；403 当前角色未获授权；404 记录不存在；409 版本变化、忙碌或重复 ID 冲突；422 请求字段错误；429 容量/并发限制；413 请求体过大。电脑不可达由客户端呈现离线，不变更任务实际状态。

## 组件与验收边界

网络依赖使用 FastAPI 0.137.x（MIT）、Uvicorn 0.46.x（BSD-3-Clause）；Qt queued connection 复用已有 PySide6。参考实际接口与官方 [HTTPBearer 文档](https://fastapi.tiangolo.com/reference/security/) 和 [QObject 线程规则](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QObject.html)。没有复制第三方源代码；Graphiti 既有许可证保留。

本批真实 Windows loopback HTTP 已覆盖配对、拒绝正文身份篡改、当前角色本地回复、事实确认、纠正、来源查看、遗忘、失效事件和撤销。另有真实线程和 SQLite 生命周期回归。它不等于 Android/iOS/HarmonyOS 真机或 TLS 证书部署验收；桌面 UI 装配由 Claude 完成后再联合验证。

Relay 实际接口与 runner 见 [runner-integration.md](../../modernization/mobile/runner-integration.md)。尚无可调用的认证 Relay 传输，宿主不暴露虚假的任务 HTTP 端点。模型评测见 [holdout.md](../../modernization/holdout.md)，真实模型凭据/固定模型和行为盲评仍缺失。
