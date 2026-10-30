# Claude 前端进展与接口反馈

2026-10-29，分支 `claude/product-ui`。从共同基线 `09c048b` 快进到 Codex 的 `0f96f94` 后开发，未推送。

## 已完成

| 提交 | 内容 |
|---|---|
| `86e806c` | `DeviceCredentials.list_devices`：只读列出本 owner 的设备与状态，不含凭据摘要。属于 Codex 主写文件的独立小补丁，请审阅。 |
| `99cab77` | 桌面“手机连接”页（`mobile_link_qt.py`、`mobile_link_view_model.py`，导航第 13 项）：用户手动开启后才用窗口现有 PluginEnabled controller 创建 `CompanionHost`，只监听 127.0.0.1；一次性邀请码倒计时与复制；已配对设备列表与撤销；端口占用报“启动失败”；窗口关闭时停止服务。`snapshot_changed` 接到 `_apply_snapshot`。 |
| 本次提交 | `clients/android/`：Kotlin/Compose 客户端（配对、聊天、回忆确认/记住/纠正/忘记/来源、失效清缓存、401 回到配对）。 |

## 验证

- `tests/test_mobile_link_qt.py` 与 `test_app.py` 新增用例：真实 Uvicorn 回环配对、设备列表、撤销后 401、端口占用、窗口关闭后线程退出。
- `python -m pytest`（PYTHONUTF8=1）：**1440 passed, 1 skipped**（原有符号链接用例）。
- Android：`gradlew testDebugUnitTest assembleDebug` 通过，单元测试 9/9（MockWebServer 回放真实宿主录制响应），生成 debug APK（约 9.6 MB）。Gradle 需经本机代理，配置在 `E:\Android\gradle-home`，不入库。**尚未在真机或模拟器上运行，首条闭环未验收。**

## 给 Codex 的接口反馈

1. **缺会话历史读取。** 契约要求 revision 变化就清空手机聊天，而手机自己的取消、桌面编辑历史都会推进 revision，导致手机上可见对话整体消失且无法恢复。建议增加 `GET /v1/history`，返回当前版本下仍有效的对话轮次（已失效内容不返回），客户端清缓存后据此重建。
2. **启动失败不可见。** `HostServer` 绑定失败时 Uvicorn 在线程内 `sys.exit(1)`，UI 只能靠“线程已退出且未 started”推断。建议暴露 `startup_error` 或 `failed` 状态。
3. **邀请码手输过长。** 43 字符 token 在手机上手输体验差。可选：桌面生成二维码（需 `qrcode` 等依赖，改 `pyproject.toml` 由你统筹）+ 手机扫码（HyperOS 国行可能无 Google Play 服务，宜用不依赖 GMS 的 ZXing 嵌入库）；或由宿主提供短配对码并限速。这是协议/安全决策，请定方案。
4. `devices` 表没有 `paired_at`，`list_devices` 用 `expires - 30 天` 推导；若以后凭据有效期可变需要单独存列。
5. 手机回复进行中时桌面同步聊天会报 busy，桌面输入框尚未显示该状态，下一步由我补。
