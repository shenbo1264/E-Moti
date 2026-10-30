# E-Moti Android 客户端

Kotlin + Jetpack Compose 的手机端，连接桌面 E-Moti 宿主，与同一角色聊天并管理共同回忆。宿主契约见 [host-integration.md](../../docs/handoff/20261029/host-integration.md)。

## 当前范围

- 配对：输入电脑地址与桌面“手机连接”页生成的一次性邀请码；凭据用 Android Keystore 加密保存，备份与换机迁移均排除。
- 聊天：发送后轮询结果；区分发送中、投递未知（可用同一 request_id 重试）、回复中、已完成、已取消、上下文已变化作废、被拒绝。
- 回忆：查看、确认待确认候选、明确记住、纠正、忘记、查看来源。所有写入携带 session_id / expected_epoch / expected_revision。
- 失效：前台每 3 秒读取 `/v1/events`；任一版本变化或 `clear_cached_content`、`resync_required` 时清除聊天与回忆缓存，再从电脑重新读取。
- 不包含：屏幕/应用观察、电脑任务、后台常驻、推送。能力页如实显示宿主 capabilities。

## 连接方式

明文 HTTP 只允许 `127.0.0.1`、`localhost` 与模拟器别名 `10.0.2.2`（见 `network_security_config.xml`），局域网地址必须是 https。

- 模拟器：`http://10.0.2.2:8765`
- USB 真机：电脑执行 `adb reverse tcp:8765 tcp:8765`，手机填写 `http://127.0.0.1:8765`

## 构建与测试

需要 JDK 17+ 与 Android SDK（platform 35、build-tools 35）。在 `local.properties` 写入 `sdk.dir`，然后：

```powershell
.\gradlew.bat testDebugUnitTest
.\gradlew.bat assembleDebug
```

单元测试用 MockWebServer 回放 `app/src/test/resources/recorded-host.json`，这些响应录制自真实回环宿主（隔离临时数据、本地表达，令牌已脱敏）。它们验证客户端状态逻辑，不能代替真机与宿主联调。
