# Android / 小米澎湃 OS 4 适配研究

研究日期：2026-10-28（America/Los_Angeles）；实际资料读取跨入 2026-10-29 UTC。本节针对用户自己的手机，不涉及他人设备。已读取官方 API、平台政策、仓库源码及 LICENSE；**没有连接手机、安装 APK、开启采集或运行 Android 真机测试**。固定源码版本与资料索引见 [android-sources.json](android-sources.json)。

## 1. 结论与第一版取舍

手机聊天、查询电脑任务、提交已授权的任务、查看阶段结果，都不需要 root。E-Moti 手机端可以先是正常的联网原生客户端，电脑上的 E-Moti 主机负责持续运行与连接 Relay；手机退到后台或断网，不应令已经接收的电脑任务失去状态。Android 的后台限制反而支持这个分工：手机作为交互、授权和观测端，不能被当作永不休眠的调度服务器。

观测也有不需要 root 的路线，但“开一个隐私开关”不能替代系统分别授予的权限。产品可以提供一个总开关，并按来源显示子开关与实时状态：应用使用记录、主动分享、媒体信息、通知、当前屏幕、实验性的可见界面文字。总开关关闭应立即停止新采集，取消处理中的结果，并令已经派生的观测摘要失效；“暂停采集”和“删除既有数据”要各自可操作。

建议首发支持 **聊天与任务 + 分享到 E-Moti + 可选应用使用记录 + 用户发起的看屏幕会话**。浏览器语义提取优先接收分享的 URL/标题，其次研究 ActivityWatch；不要先以“全天无痕读取所有 App”为验收目标。无障碍不是所有应用内容的公共接口，也存在独立的分发限制。

## 2. 能做什么，需要什么权限

| 能力 | 无 root 原生实现 | 实际可获得的数据 | 不能据此承诺 |
|---|---|---|---|
| 文字聊天、向电脑发任务、查看状态 | HTTPS/WSS，设备配对与应用层认证；LAN 另见 Android 17 规则 | 用户输入、任务 ID、事件序列与结果引用 | 电脑离线时仍能真正执行电脑任务 |
| 语音聊天 | 用户授予麦克风；录音/语音会话遵守前台服务与 while-in-use 规则 | 用户主动录制或已开启会话的音频 | 任意后台随时开麦、无提示长期录音 |
| 接收网页、图片或文字 | 系统分享入口、明确 URI 授权 | 用户选中的内容和来源 | 自动获得浏览器全部历史或其他 App 私有数据库 |
| 应用使用轨迹 | `UsageStatsManager` + 用户在系统设置授予 Usage Access | 包名、前后台事件、时间及使用时长；具体事件可用性依设备/版本 | 正在读哪条微信、B站视频正文、网页 DOM |
| 通知内容 | 用户授予 Notification Access，`NotificationListenerService` | 系统实际投递给监听器的通知元数据/允许的正文 | 全量聊天历史；被 App 隐藏的通知内容；OTP 总能读到 |
| 播放中的媒体信息 | 获授权的通知监听器配合 `MediaSessionManager` | 播放器公开的标题、作者、播放状态 | 每个 B站页面都提供完整标题/字幕，或每个视频 App 都正确实现 MediaSession |
| 当前可见界面文字 | 用户启用 AccessibilityService，声明读取窗口内容；按分发规则披露和审查 | App 暴露的可访问性节点/事件 | 自绘/游戏画面、所有 WebView、敏感节点一定可读；后台隐藏页面或历史记录 |
| 用户开启的一段屏幕观察 | MediaProjection + 系统同意 + 正确的前台服务；API 30+ 无障碍另有截图 API | 被共享应用或显示区域的可截图像，再做 OCR/VLM | 锁屏后持续抓图；绕过安全窗口；无提示永久授权 |
| 手机操作自动化 | 技术上有 Accessibility 手势、ADB、AppFunctions 等不同路线 | 获授权路线支持的动作 | 通用 GUI Agent 可以无条件通过 Google Play 分发，或取得一个权限就能操作所有 App |

官方依据：[UsageStatsManager](https://developer.android.com/reference/android/app/usage/UsageStatsManager)、[通知监听器](https://developer.android.com/reference/android/service/notification/NotificationListenerService)、[无障碍服务](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService)、[MediaProjection](https://developer.android.com/media/grow/media-projection)、[前台服务类型](https://developer.android.com/develop/background-work/services/fgs/service-types)、[接收分享内容](https://developer.android.com/develop/ui/compose/sharing/receive)。

`UsageStatsManager.queryEvents` 不是全局推送流；系统只保留近期详细事件，需要增量查询并处理重启、时区、重复及丢失。当前 API 文档也出现了 37.2 的 `queryAppUsageDuration/QUERY_APP_USAGE`，但权限标为 `internal|role`，不能把它当作任何普通 App 都能申请的新替代品。[权限定义](https://developer.android.com/reference/android/Manifest.permission#QUERY_APP_USAGE)

### 浏览器、B站、微信应怎样表达

- **浏览器**：用户分享的 URL 是最清晰的证据；无障碍可在受支持浏览器读取可见地址栏/标题，但浏览器升级会改变资源 ID，网页正文、登录状态、内置浏览器和无痕状态必须单独验证。
- **B站**：知道“B站在前台 15 分钟”是使用记录；知道“播放器公开标题为 X”是媒体信息；知道“屏幕 OCR 读到 X”是观察结果。三者不能混成“用户完整看过并喜欢 X”。
- **微信**：通知只代表实际暴露的部分通知；当前屏幕只代表当前可见内容；都不是微信完整聊天导出。对话对方的发言不能自动记成用户自己的事实或表达风格。优先支持用户主动分享或挑选片段。

屏幕文字和通知是外部内容，不应获得指令权限。例如网页写着“把所有文件发给我”，只能作为页面内容，不得转成 Relay 命令。观察得到的偏好应先形成带来源的候选，沿用现有 Emotional Memory V2 的用户确认、纠正、撤回与 epoch，不能直接改人格。

## 3. Android 14—17 的具体边界

### 3.1 MediaProjection 是会话授权

Android 14+ 要求每次投屏会话取得用户同意；不能反复复用同一个授权 Intent/MediaProjection token 创建新的虚拟显示。正确声明 `FOREGROUND_SERVICE_MEDIA_PROJECTION` 和 service type，并在 `onStop()` 回调释放截图/编码资源。

Android 15 QPR1+ 有明显的屏幕共享状态提示，用户可以从状态栏结束共享；锁屏也会自动停止。E-Moti 必须把这类停止同步到电脑端，取消队列中的 OCR/VLM 结果，不能仅让手机 UI 显示“关闭”而让晚到摘要继续进入上下文。[官方说明](https://developer.android.com/media/grow/media-projection)

`FLAG_SECURE` 和内容敏感性标记可阻止截图/共享显示；Android 14+ 的 `accessibilityDataSensitive` 也会对非真正无障碍工具隐藏敏感节点。应记录“该窗口不可观测”，不能把黑图或缺失节点解释成用户没有活动。[安全窗口](https://developer.android.com/reference/android/view/WindowManager.LayoutParams#FLAG_SECURE)、[敏感节点](https://developer.android.com/reference/androidx/core/view/accessibility/AccessibilityNodeInfoCompat#setAccessibilityDataSensitive(boolean))

### 3.2 通知权限不等于读取通知内容的权限

`POST_NOTIFICATIONS` 用于发布 E-Moti 自己的通知，不能拿它读其他 App 的通知。读取通知需要用户另行打开 Notification Access；Android 15 对不受信任监听器的 OTP 通知进行脱敏。不要把读取验证码、密码或付款页面设计成可靠数据来源。[Android 15 行为变更](https://developer.android.com/about/versions/15/behavior-changes-all)

### 3.3 Android 17 的局域网许可

面向 Android 17/API 37 的应用连接/发现局域网设备，通常要声明并请求 `ACCESS_LOCAL_NETWORK`，或者使用系统介导的 `NsdManager` 设备选择器，获得特定所选服务的访问。TCP/UDP、NSD、OkHttp 等都受底层限制，WebView 也继承宿主权限状态。因此手机扫描电脑、输入局域网 IP、连 WebSocket 都要覆盖拒绝权限后的状态；仅声明 `INTERNET` 不是完整适配方案。[官方局域网权限](https://developer.android.com/privacy-and-security/local-network-permission)、[NsdManager](https://developer.android.com/reference/android/net/nsd/NsdManager)

这是 target SDK 与设备 Android 版本共同决定的规则。不要通过长期停留旧 target SDK 来代替适配。首次配对可以让用户选定电脑并核对身份；发现设备不等于已经授权向它发任务。

### 3.4 长程任务不能依赖手机永远存活

WorkManager 的周期工作最短为 15 分钟，并受省电/Doze 影响；它适合可延迟同步，不适合秒级实时观察。Android 16+ 的 long-running worker 即使使用前台服务，仍可能耗尽 JobScheduler 配额。前台服务本身也有启动时机、类型、时限及用户可见通知要求。[周期工作](https://developer.android.com/reference/androidx/work/PeriodicWorkRequest)、[长时间工作](https://developer.android.com/develop/background-work/background-tasks/persistent/how-to/long-running)

因此长程执行应持久化在当前可用的电脑 E-Moti 主机或用户自选的常驻主机；手机在前台用流式事件，在后台通过适用推送或下次上线补拉。断网重发需要相同请求 ID、防重执行及事件游标。用户划掉 App、手机重启或系统杀进程，都只能使手机暂时失联，不能把任务标成完成。电脑休眠或断电则必须显示暂停/不可达，并且实际执行等待电脑恢复。

## 4. Google Play、系统权限与侧载必须分开评估

Google Play 当前政策明确禁止普通应用利用 Accessibility API 自主发起、规划并执行动作/决策；静态、用户定义的确定性自动化有不同规则。真正为残障用户服务的 verified accessibility tools 有特定豁免，通用个人助手不因此自动具备资格。非该类别的应用还需单独、明显的披露和明确同意。[政策原文](https://support.google.com/googleplay/android-developer/answer/10964491?hl=en)

这项限制针对通过 Accessibility API 自动执行的方式；手机通过 E-Moti API 请求电脑执行 Relay 任务不是同一个技术入口。是否上 Play、国内商店还是用户自己构建安装，会改变分发审核过程，但不会让 Android API、敏感窗口限制和厂商后台规则消失。

Android Advanced Protection Mode 会把无障碍服务限制为经过验证的工具，并限制未知来源安装等能力；启用时应显示观测功能不可用和原因，保留聊天、任务与用户主动分享。不能把要求用户关闭保护或假报 `isAccessibilityTool=true` 当作默认产品流程。[Google 官方用户说明](https://support.google.com/android/answer/16339980?hl=en)、[开发者检测 API](https://developer.android.com/privacy-and-security/advanced-protection-mode)

原生端应把“能力未授予”“操作系统限制”“App 未暴露内容”“采集暂时中断”分别建模。这些状态是工程观测能力的一部分，不能统一回报成“没有看到”。

## 5. 澎湃 OS 4 的适配判定

小米已有 [HyperOS 4 官方页面](https://hyperos.mi.com/)，不能以旧知识否认用户系统版本。但 **HyperOS 名称不能代替实际 Android API level**；目前没有该用户具体型号、完整构建号和地区包信息。适配要读取 `Build.VERSION.SDK_INT`、版本信息、设备型号，以及当前每项能力和权限状态，不能只做“HyperOS 4”字符串判断。

小米官方文档分别说明（其中 Powerkeeper 页面标注更新于 2022-12-07；这些是官方机制说明，不能替代 HyperOS 4 的当前菜单与真机行为验证）：
- 自启动默认不允许，由用户在明确知情后选择开启：[自启动管理](https://dev.mi.com/xiaomihyperos/documentation/detail?pId=1624)。
- Powerkeeper 可因异常后台耗电、持锁等限制或终止应用；用户设置会改变策略：[Powerkeeper](https://dev.mi.com/xiaomihyperos/documentation/detail?pId=1628)。
- 后台弹出页面是单独受限能力：[后台页面](https://dev.mi.com/xiaomihyperos/documentation/detail?pId=1625)。
- 小米提供 [Android 17 适配指南](https://dev.mi.com/xiaomihyperos/documentation/detail?pId=2297)，但页头仍是 2026-05-06 的预览阶段说明；涉及最终 Android 行为时以 Google 最新正式文档及真机为准。

因此建议：
1. 正常聊天和前台任务页无需申请自启动、无障碍或后台弹窗。
2. 用户主动开启连续观测时，再展示所需系统入口、当前服务状态及耗电信息。
3. 允许用户按自己意愿设置后台运行策略；检测能力中断并恢复游标，不能靠静默重开服务掩盖中断。
4. 国内机型若无 Google Play services，阶段结果推送需要评估小米推送或自选通知渠道；不能把 FCM 存在当成默认条件。任务正确性不依赖推送一定送达。
5. 不把超级小爱的系统集成能力当作第三方 App 已开放 SDK。官方宣传可以启发交互，不能证明 E-Moti 有相同系统权限。

本批没有安装 Android SDK、连接 HyperOS 4 或测量耗电。兼容性状态是“有官方 API 路径，待设备验收”，不是“已经兼容”。

## 6. root、ADB、Shizuku 是三个不同层次

| 路线 | 是否必须 root | 用户额外操作 | 对 E-Moti 的用途 |
|---|---|---|---|
| 普通 Android 原生 API | 否 | 按能力授予 Usage Access、通知访问、录屏会话等 | 默认路线 |
| ADB / scrcpy | 否 | 开发者选项、USB/无线调试与设备授权；部分小米控制动作另受安全调试设置影响 | 用户主动的实验/开发工具，可做手机屏幕观测，不依赖修改系统 |
| Shizuku 的 ADB 模式 | 否 | 以调试方式启动辅助服务；Android 11+ 可无线调试；无 root 模式重启后一般要重新启动 | 少量标准 API 不覆盖的可选高级适配，不作为安装前提 |
| Shizuku 的 root 模式或系统特权扩展 | 是或需厂商特权 | 已有 root/系统签名环境 | 不属于第一版方案，单独评估具体能力与维护 |
| 直接读取其他 App 私有目录/数据库、内核输入或系统级无提示采集 | 普通原生应用不可直接实现；可能需要 root、系统签名或目标 App 主动导出 | 设备与系统强相关 | 不作为“了解用户”的必要条件；root 也不保证破解加密、绕过硬件保护或获得可靠语义 |

[Shizuku 官方说明](https://shizuku.rikka.app/guide/setup/)明确 ADB 权限有限且 ROM 差异存在；其使用手册有部分 MIUI 时代指导，不能未经 HyperOS 4 真机验证就当作当前菜单路径。用户需要的首批聊天、远程控制电脑、App 使用轨迹、可选屏幕观察，**没有一项必须以 root 为前提**。

## 7. 可复用项目：读到的实现与不应照搬的部分

下面的“维护”依据本次 API 返回的 pushed_at 与固定 main/master 提交，不代表每个发行版已包含该改动。没有在本环境运行这些 Android 项目。

| 项目 / 固定提交 | 本次实际确认 | 许可证与维护 | E-Moti 决策 |
|---|---|---|---|
| [ActivityWatch aw-android](https://github.com/ActivityWatch/aw-android/tree/bb634609364872b9c7d38b3a4452fa228c1f9e4b) | Kotlin 的 UsageStats、无障碍浏览器 URL/标题、媒体会话信息；Rust 本地后端、已有测试 | MPL-2.0；2026-10-26 推送，未归档 | 最匹配“手机痕迹”研究；优先做可选、明确字段的导入/适配，不把整套 Rust 数据库嵌入 E-Moti 的长期记忆 |
| [Mobilerun，原 DroidRun](https://github.com/droidrun/mobilerun/tree/11dcdebdec9ea99f172dd7e80af7ba1eadbeb6c8) | Python Agent、Android Portal 驱动、UI tree/screenshot、支持带 token 的 Portal HTTP 驱动；不仅是 ADB 路径 | 主库 MIT；2026-10-28 推送 | 可研究动作/观察协议与状态查询；依赖及手机 Portal 必须分别核许可证 |
| [Mobilerun Portal](https://github.com/droidrun/mobilerun-portal/tree/4962c54cb1c5a2b5b2f68e228bb91ffb33d2b113) | 真正 Android 无障碍应用，有本地 HTTP、WebSocket 事件、截图与操作能力 | 实际 LICENSE 为 AGPL-3.0-or-later；2026-10-29 UTC 推送；GitHub 元数据 NOASSERTION 不代表无许可证 | 遵守本仓不引入 GPL 系代码的规则，不复制其 Kotlin 源码。可作为独立研究工具，不能当作 MIT SDK 打包进 E-Moti |
| [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM/tree/86f55382982fb054e8fc98ca80609dff8a2cdc3c) | Python 手机 Agent；ADB 输入/截图，有 HDC 与其他平台目录；截图失败可返回黑图及敏感标记 | Apache-2.0；main 最后提交 2026-03-06，未归档 | 可复用经过审查的小型动作适配或协议；它不是已实现的手机长期被动观测产品，也不证明最新 HyperOS 已验证 |
| [Mobile-Agent v3.5](https://github.com/X-PLUG/MobileAgent/tree/81fa28b564ef7a695521500bc15a0e1324b2b394/Mobile-Agent-v3.5) | 实机 Android ADB 连接、ADB Keyboard、手机/桌面/浏览器执行与 AndroidWorld 评测代码 | 主仓 MIT；2026-10-28 推送；模型与嵌入子项目须另核许可 | 作为可选 GUI 执行器/评测参考，不代替 E-Moti 任务权威和人格；论文/README 分数不是本项目实测 |
| [scrcpy](https://github.com/Genymobile/scrcpy/tree/a60891aea193d92e7e5c3942700eca63f9d19a5f) | ADB 上的 Android 显示/控制，桌面支持 Win/macOS/Linux；官方明确无需 root | Apache-2.0；2026-10-26 有推送，固定 master 提交 10-08 | 用户主动开发模式下复用成熟观测工具；不将其调试授权条件伪装成普通 APK 权限 |
| [screenpipe](https://github.com/screenpipe/screenpipe/tree/93a0fba0aa94c1aeeb8cd78795ad943b4dc435e4) | 当前 README 列 macOS、Windows、Linux；检查树中的 android 命名路径仅见图标资源 | 当前 LICENSE 为 Screenpipe Commercial License，source-available；2026-10-29 UTC 推送 | 未找到可证明已交付的 Android collector；当前版本不能按旧 MIT 印象复制/集成。旧 MIT 发布版本保留其旧许可证，使用时必须另行固定审查 |

### ActivityWatch：值得复用的具体实现与当前缺口

已读源码：

- [UsageStatsWatcher.kt](https://github.com/ActivityWatch/aw-android/blob/bb634609364872b9c7d38b3a4452fa228c1f9e4b/mobile/src/main/java/net/activitywatch/android/watcher/UsageStatsWatcher.kt)：检查 Usage Access，查询使用事件；定时入口采用每小时 `setInexactRepeating`，不能描述成全局实时事件流。
- [SessionEventWatcher.kt](https://github.com/ActivityWatch/aw-android/blob/bb634609364872b9c7d38b3a4452fa228c1f9e4b/mobile/src/main/java/net/activitywatch/android/watcher/SessionEventWatcher.kt)：断点/重叠增量会话处理，适合研究离线补采和去重。
- [WebWatcher.kt](https://github.com/ActivityWatch/aw-android/blob/bb634609364872b9c7d38b3a4452fa228c1f9e4b/mobile/src/main/java/net/activitywatch/android/watcher/WebWatcher.kt)：读取 Chromium/Firefox 等地址栏，分屏包名校验、后台有界写队列、浏览器升级后的探测；原生库初始化不阻塞无障碍主线程。
- 同一文件 `logBrowserEvent` 仍把 `incognito` 写成 `false // TODO`。所以**不能宣称 Android 端已可靠排除无痕浏览**。这一点应阻止直接启用“默认采集所有浏览历史”。
- [MediaWatcher.kt](https://github.com/ActivityWatch/aw-android/blob/bb634609364872b9c7d38b3a4452fa228c1f9e4b/mobile/src/main/java/net/activitywatch/android/watcher/MediaWatcher.kt)：监听实际 MediaSession 元数据；实现主动说明它不以逐条通知内容作为媒体跟踪基础。
- [#255](https://github.com/ActivityWatch/aw-android/issues/255) 的 Android 14+ 前台服务启动失败、[#261](https://github.com/ActivityWatch/aw-android/issues/261) 的白屏/ANR 是具体工程教训；均已关闭，不能把旧问题写成当前版本仍未修复。未复现它们，也不使用社区帖中的崩溃比例作为独立统计。

MPL 是文件级 copyleft，可与其他许可的代码形成 larger work，但涉及其代码的文件仍需履行源码/声明义务；不能把复制来的文件改标成纯 MIT。[Mozilla 官方 FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/)。第一阶段外部数据导入降低耦合，之后仅在确有收益时引入隔离、保留许可的采集组件。

### Mobilerun：能力真实，但授权和许可不能继承错

主框架的 [android_device.py](https://github.com/droidrun/mobilerun/blob/11dcdebdec9ea99f172dd7e80af7ba1eadbeb6c8/mobilerun/agent/utils/android_device.py) 确有 `AndroidPortalHttpDriver`，并要求 auth token；因此不能继续声称它只有 ADB 路径。

Portal 的 [无障碍配置](https://github.com/droidrun/mobilerun-portal/blob/4962c54cb1c5a2b5b2f68e228bb91ffb33d2b113/app/src/main/res/xml/accessibility_service_config.xml) 声明了读取窗口、截图、手势及 `isAccessibilityTool=true`。**源项目这样声明，不等于通用 E-Moti 助手具备 Play 政策资格**。也不应复用自动确认系统权限对话框的行为。SDK 主库 MIT、手机端 AGPL、模型许可，是三项独立判断。

## 8. 另一条值得跟踪的官方路线：AppFunctions / 系统 Assistant

Android [AppFunctions](https://developer.android.com/ai/appfunctions) 允许目标 App 显式暴露函数，适合有约定的搜索、创建或查询能力，比识别按钮可靠。官方当前仍标 experimental，Android 16+，caller 权限与平台认证/allowlist 有限制；Jetpack 版本也在变化。[发布记录](https://developer.android.com/jetpack/androidx/releases/appfunctions)、[权限条目](https://developer.android.com/reference/android/Manifest.permission#EXECUTE_APP_FUNCTIONS)

可先研究让 E-Moti 的“查看任务/提交明确请求”成为受控函数，供支持的平台调用。不能假定微信/B站已发布 E-Moti 所需函数，也不能说 E-Moti 已能作为通用 caller 获得全部系统 Agent 能力。

另一可选入口是用户选择 E-Moti 为系统 Assistant，并在用户唤起会话时取得 AssistStructure/截图；[VoiceInteractionSession](https://developer.android.com/reference/android/service/voice/VoiceInteractionSession) 明确数据可能因用户、策略或安全窗口而缺失。这适合“看一下当前屏幕”，不等于全天后台活动记录，也未在 HyperOS 4 验证替换入口。

## 9. 下一批 Android 真机验收

| 场景 | 应看到的结果 | 当前状态 |
|---|---|---|
| 仅授予联网，其他观测全关 | 正常聊天与任务管理；不读取手机活动 | 待原生客户端实现/真机 |
| 拒绝 LAN 权限、电脑离线、Wi-Fi 切移动网络 | 明确状态；请求可查询，不产生第二份任务 | 待配对/传输实现 |
| 同一任务断网重发 10 次 | 相同请求 ID 返回同一任务；不重复派工 | 应由服务端协议测试覆盖 |
| Usage Access 撤回后重新授予 | 暂停立即生效；不把停用期间的历史偷偷补入 | 待 collector + 服务端联合验收 |
| MediaProjection 结束、锁屏、旋转、切单 App 共享 | 会话取消/尺寸正确；晚到 OCR/VLM 无效 | 待真机 |
| 分屏浏览器、无痕模式、支付/密码窗口 | 未知或不可观测时明确标记；不猜内容 | 待真机，不依赖 ActivityWatch incognito 字段 |
| B站开启/暂停媒体、微信通知隐藏正文 | 只报告真实可用字段，保留来源与时间 | 待版本矩阵 |
| HyperOS 杀进程、重启、受限省电 | 手机上报采集空窗；电脑任务状态仍可恢复 | 待真机 |
| AAPM/系统限制禁用无障碍 | 观测降级，聊天和工作请求可继续 | 待具体 ROM |
| 撤回观察源 / 删除观察摘要 | 取消队列并阻断旧来源复活，长期事实按已确认来源管理 | 服务端协议可先测试；端到端待验收 |

验收记录至少包含设备型号、地区包、HyperOS 完整 build、Android SDK、目标 App 版本、各授权状态、采集延迟/缺失率和电量区间。没有这些证据，不给“HyperOS 4 全功能兼容”结论。
