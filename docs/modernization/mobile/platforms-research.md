# macOS、原生鸿蒙与跨端执行：官方能力核查

> 2026-10-29范围更正：用户确认此前macOS为口误，实际目标为iOS手机；鸿蒙限定华为手机。本文保留2026-10-28的历史研究，其中macOS栏及相关验收建议不再属于当前任务。现行选择见[平台更正](../../handoff/20261029/platform-scope.md)，真实iOS资料见[iOS研究](../../handoff/20261029/ios-research.md)。下文华为手机相关证据与长程执行机制仍可参考，PC/二合一专属能力不能外推手机。

调研日期：2026-10-28（America/Los_Angeles）。这是多端实现的依据与取舍，**不是 macOS / 鸿蒙真机验收报告**。本次未安装客户端、启用录屏、获取无障碍授权、配置公网入口或连接用户设备。

## 1. 对 E-Moti 的结论

手机聊天、查看任务进展、批准建议和远程向电脑发送命令，可以先共用一个协议。手机活动观测必须使用各操作系统自己的采集模块，无法靠一套网页或一个权限开关获得所有平台相同的数据。长任务的持久执行和 Relay 状态读取应留在电脑上的宿主或用户自行选择的常开节点；手机关闭页面、锁屏或进程被回收，不应中断已经接受的任务。这是本项目的架构选择，具体平台依据见下文。

| 能力 | macOS | 原生 HarmonyOS 手机 | E-Moti 的首批选择 |
|---|---|---|---|
| 聊天、任务查看、用户批准、结果报告 | 普通网络客户端可做 | 普通网络客户端可做 | 统一消息、身份、任务状态协议 |
| 保留桌宠界面 | PySide6 可继续使用；重新做 macOS 打包与验收 | 不能直接把 Windows 桌面布局当成手机产品 | 桌面保留 PySide6，手机采用适合触摸的薄客户端 |
| 当前前台应用名称 | `NSWorkspace.frontmostApplication` | 全局 usageStatistics 属于系统接口；不能承诺普通应用直接查询 | 按能力声明，缺失时显示“不可用” |
| 其他应用可见界面的语义信息 | Accessibility API，用户授权；App Sandbox 有限制 | Accessibility Kit 允许三方辅助扩展；具体节点、启用与分发条件需验证 | 独立可选模块，不等同于读取应用私有数据库 |
| 当前屏幕画面 | ScreenCaptureKit + 用户录屏授权 | AVScreenCapture 有正式录屏路线；系统弹窗、隐私与生命周期限制依然存在 | 用户主动开启的会话，不做默认常开录制 |
| 后台任意代码永远运行 | 桌面进程仍受退出、睡眠和网络影响 | 后台任务受类型、调度、通知和时长约束 | 长任务不依赖手机进程常驻 |
| root / 特权是否必要 | 上述基础路线不需 root；系统授权不可由 root 替代为产品流程 | 基础聊天与授权录屏不需 root；系统接口/ACL 不是用户点开关即可获得 | 不把提权作为正常安装前提 |

## 2. macOS：可复用 Python 核心，需独立平台接入

### 2.1 现有代码实际支持到哪里

本次读到的 `src/guanghe_companion/focus_companion.py::WindowsForegroundActivityReader.sample()` 在 `sys.platform != "win32"` 时明确返回 `available=False`、`source="unsupported_platform"`。当前前台应用观察不是跨平台实现。`voice_tts.py` 的 Windows SAPI provider 和 `voice_service_control.py` 的 PowerShell 服务启动入口也需要平台替代或能力禁用；仅能 import PySide6 不能证明这些路径在 Mac 可用。

Qt 官方提供 PySide6 的 macOS 部署路径，`pyside6-deploy` 可产出 `.app`；当前项目锁定 `PySide6==6.11.0`，本次查阅的在线部署文档已经包含 6.12 行为变化，应按锁定版本验收，不能顺便升级依赖以匹配新文档。[Qt 部署文档](https://doc.qt.io/qtforpython-6/deployment/index.html)、[pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html)。

建议保留领域模型、人格、记忆、插件契约和大部分 Qt UI；增加小型 macOS 平台适配器。ScreenCaptureKit/Accessibility 可通过成熟 Python 原生桥接或单独签名的 Swift helper 接入，但两种方式都应先做真实设备实验，再决定依赖。当前没有把任何 helper 加入生产启动链路。

### 2.2 三种观测能力需要分别实现

**前台应用：** `NSWorkspace.frontmostApplication` 返回正在接收键盘事件的 `NSRunningApplication`。它能回答“现在主要在使用哪个应用”，不直接给出网页 URL、聊天内容或用户意图。用 `bundleIdentifier` 做应用识别比可执行文件名更符合 Mac 生态；不能把这一 API 的结果包装成已经看过页面。[Apple API](https://developer.apple.com/documentation/appkit/nsworkspace/frontmostapplication)。本次通过该页面提供的 `.md` 文档入口读取到实际说明。

**屏幕与系统音频：** ScreenCaptureKit 的官方示例能够选择显示器、应用或窗口，配置 `SCContentFilter` 与输出流；首次运行示例会请求 Screen Recording 授权。Apple 的系统设置把屏幕/系统音频和麦克风分别管理。因此 E-Moti 应独立显示屏幕、系统音频、麦克风状态，并在失去授权或结束采集时停止发送数据。低频截图、变化触发与限定窗口是本项目的设计选择，不需要把持续视频作为默认输入。[官方示例](https://developer.apple.com/documentation/screencapturekit/capturing-screen-content-in-macos)、[录屏与系统音频设置](https://support.apple.com/guide/mac-help/control-access-screen-system-audio-recording-mchld6aa7d23/mac)、[麦克风设置](https://support.apple.com/guide/mac-help/control-access-to-the-microphone-mchla1b1e1fe/mac)。

**UI 语义：** `AXIsProcessTrustedWithOptions` 可以检查当前进程是否是受信任的 Accessibility client；提示授权是异步动作，调用不代表立即获得权限。`AXUIElement` 系列 API 用于读取应用公开的辅助功能属性。读到什么取决于目标应用提供的无障碍树；画布、视频和自绘组件不能假定有完整文本。用户可以在系统设置中撤销授权。[AX 检查 API](https://developer.apple.com/documentation/applicationservices/1459186-axisprocesstrustedwithoptions)、[AXUIElement](https://developer.apple.com/documentation/applicationservices/axuielement_h)、[用户授权说明](https://support.apple.com/guide/mac-help/allow-accessibility-apps-to-access-your-mac-mh43185/mac)。

浏览器 URL 和页面标题优先考虑用户明确安装的浏览器扩展。Chrome 的标签页敏感属性需要 `tabs` 或匹配站点权限；扩展可以通过 Native Messaging 与本地宿主交换消息。按站点选择授权有助于把银行、邮箱和私人聊天排除在采集之外。该路线需要另外验证浏览器支持，不应由“已获录屏权限”自动开启。[标签页权限](https://developer.chrome.com/docs/extensions/get-started/tutorial/popup-tabs-manager)、[Native Messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging)。

### 2.3 分发路径影响能力

Apple 官方把辅助应用使用 Accessibility API 列为 App Sandbox 受限制活动。Mac App Store 分发要求 App Sandbox；Developer ID 签名、商店外公证分发需要 hardened runtime，App Sandbox 可选。因此完整桌面观察与控制能力应先以签名、公证的商店外包评估；不能同时承诺同样的无障碍能力一定可在沙盒版中工作。[App Sandbox 限制](https://developer.apple.com/documentation/security/protecting-user-data-with-app-sandbox)、[分发准备](https://developer.apple.com/documentation/Xcode/preparing-your-app-for-distribution)、[公证](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)。

root、管理员密码和 Full Disk Access 不应成为基础聊天、前台应用识别或标准录屏的默认要求。TCC 授权、代码签名、沙盒 entitlements 与用户是否是管理员是不同问题；开发终端中获得权限也不能替代最终 `.app` 身份下的验收。

## 3. 鸿蒙：区分版本、普通应用能力与系统接口

### 3.1 版本边界

至少记录实际机型、系统完整版本、SDK/API 版本、手机/平板/PC 类型、签名与分发方式。华为官方资料把 HarmonyOS 4.x 及以下与 HarmonyOS 5 及以上分为不同适配路径；当前官方站点还已发布 HarmonyOS 7 / API 26 的适配信息。这里研究的主要是原生 HarmonyOS 路线，不能直接使用 Android 的 `UsageStatsManager`、`AccessibilityService` 或 `MediaProjection` 代码。[华为兼容性说明](https://consumer.huawei.com/cn/support/content/zh-cn16053052/)、[官方开发文档入口](https://developer.huawei.com/consumer/cn/doc/)、[HarmonyOS 7 官方说明](https://consumer.huawei.com/cn/support/content/zh-cn16103427/)。

薄客户端采用 ArkTS/ArkUI 是当前可控的选择，Python 伙伴核心通过网络协议服务它。Qt 已提供 HarmonyOS 平台集成和 HAP 打包，但**官方对成熟度的表述不一致**：2026-09-30 的 Qt 6.12 发布公告称 HarmonyOS 已作为 LTS 平台获得正式支持；本次同一轮核查的 HarmonyOS 专项文档和 Qt 6.12 新特性文档仍保留 technology preview 表述。不能单方面把它归为“完全不支持”或“只有技术预览”，也不能把发布公告当成本项目已适配的证明。[Qt 6.12 发布公告](https://www.qt.io/blog/qt-6.12-released)、[Qt for HarmonyOS](https://doc.qt.io/qt-6/harmonyos.html)、[Qt 6.12 新特性](https://doc.qt.io/qt-6/whatsnew612.html)。

选择 ArkTS/ArkUI 的具体依据是：E-Moti 仍锁定 `PySide6==6.11.0`，Python 依赖、QtWebEngine 和现有桌面界面没有经过手机 HAP 构建与真机验证；Qt 当前鸿蒙指南重点展示 Qt Quick/C++ 组合。Qt 总体支持表与专项页面的 host/target 描述也有差异，后续若评估直接复用 Qt 手机客户端，应固定 SDK/Qt/Python 版本，以实际构建及权限实验确认，不根据这几份措辞不同的页面推断完整兼容性。[Qt 支持表](https://doc.qt.io/qtforpython-6/overviews/qtdoc-supported-platforms.html)。

### 3.2 应用使用轨迹：不可照搬 Android 的用户授权模型

OpenHarmony 官方 `@ohos.resourceschedule.usageStatistics` 文档明确整个模块为系统接口；`queryBundleEvents`、`queryBundleStatsInfos` 等全局查询要求 `ohos.permission.BUNDLE_ACTIVE_INFO`。权限列表给出的等级是 `system_basic`、授权方式是 `system_grant`。旧的 `@ohos.bundleState` 已停用，其普通三方路径仅支持查询自身空闲状态，不能作为全局活动轨迹的替代方案。[系统接口源码文档](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-backgroundtasks-kit/js-apis-resourceschedule-deviceUsageStatistics-sys.md)、[旧模块](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-backgroundtasks-kit/js-apis-deviceUsageStatistics.md)。

这里不能把“支持 ACL”翻译为“普通用户确认后可用”。APL 权限等级、ACL/证书批准和运行时用户授权分别约束不同环节。OpenHarmony 的调试权限配置说明明确调试方法不能作为上架发布方案；华为 2025 年 12 月的官方月刊说明 AGC 已增加 ACL 申请与试用入口，但没有承诺任意系统权限向普通应用开放。**尚未取得商业 HarmonyOS 对本项目全局使用统计场景的批准依据，应把它标记为受限/待确认能力。**[系统权限定义](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/security/AccessToken/permissions-for-system-apps.md)、[受限权限调试说明](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/security/AccessToken/declare-permissions-in-acl.md)、[AGC 官方更新](https://developer.huawei.com/consumer/cn/monthly/202512)。

### 3.3 无障碍：有公开能力，不能简单判定“全部系统专用”

华为当前应用开发页面明确 Accessibility Kit 允许三方开发类似读屏软件的扩展。OpenHarmony 官方的公共 `AccessibilityExtensionAbility` / `AccessibilityExtensionContext` 文档包含事件、节点、`bundleName`、文本属性和目标应用配置；系统专用扩展另有 `-sys` 文档。因此，辅助功能用户启用后的可见界面观察是值得做原型验证的路线。[华为 Accessibility Kit 介绍](https://developer.huawei.com/consumer/cn/app)、[扩展能力](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-accessibility-kit/js-apis-application-accessibilityExtensionAbility.md)、[节点与上下文](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-accessibility-kit/js-apis-inner-application-accessibilityExtensionContext.md)。

这只证明框架存在相关开放能力。它不证明 E-Moti 的持续个人活动分析用途符合分发条件，不证明微信/B站等每个版本都提供完整可读节点，也不证明能够取得屏幕外的历史消息。正式承诺前应在目标 SDK、普通签名、真实设备上分别验证事件、节点字段、隐私区域和授权撤销；不把系统内置小艺的能力当成第三方应用同等开放的证据。

### 3.4 录屏：区分授权会话和直接截图特权

华为当前 AVScreenCapture 开发指南给出 C/C++ 录屏流程、示例、采集回调与资源释放要求。指南说明通话和系统用户切换可以中止采集；麦克风采集还涉及麦克风权限与长时任务。官方对 API 22 的“无隐私弹窗”能力明确限定 PC/2in1 和受限权限。因此普通手机应采用用户可见、明确开始/结束的录屏会话，不设计无弹窗静默常开。[华为 AVScreenCapture 指南](https://developer.huawei.com/consumer/cn/doc/doccenter-capabilities/using-avscreencapture-for-file)、[录屏常见问题](https://developer.huawei.com/consumer/cn/doc/doccenter-capabilities/avscreencapture-faqs)。

OpenHarmony 权限列表中的 `CAPTURE_SCREEN` 是 `system_core` 的直接截图能力；`EXEMPT_CAPTURE_SCREEN_AUTHORIZE` 是豁免录屏授权弹窗的系统权限。不能因为这些特权受限就推断所有用户授权录屏均不可做，也不能反向用录屏会话能力证明已获得系统截图权限。敏感内容可能被系统或应用保护，需当作不可观测内容处理，不应把绕过保护作为兼容目标。[官方权限定义](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/security/AccessToken/permissions-for-system-apps.md)、[华为关于不可截录屏的说明](https://consumer.huawei.com/cn/support/content/zh-cn00431504/)。

**不建议为鸿蒙另立 root 版本计划。**本次没有发现对普通华为手机可持续支持、官方认可的通用提权产品路线；系统权限不足应呈现为能力缺失或寻求正式能力申请，不能写成“root 后即可全部解决”。

### 3.5 后台运行不能承载无限任务循环

华为官方把后台任务分为短时、长时、延迟任务和代理提醒。无合适后台任务时进程可能挂起；延迟任务由系统调度，单次扩展执行窗口受限。OpenHarmony 当前长时任务文档对 `TASK_KEEPING` 的手机使用另有 ACL 条件，普通聊天客户端不能假借音频播放、VOIP 等类型持续空转保活。AppServiceExtensionAbility 也不是通用手机守护进程：华为当前文档限定 PC/2in1，且需要特定企业 ACL。[后台合理使用](https://developer.huawei.com/consumer/cn/doc/doccenter-app-quality/bpta-use-of-background-tasks)、[长时任务 API](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-backgroundtasks-kit/js-apis-resourceschedule-backgroundTaskManager.md)、[AppServiceExtensionAbility](https://developer.huawei.com/consumer/cn/doc/doccenter-capabilities/app-service-extension-ability)。

工程含义：手机离线时保存待同步的用户输入；恢复时使用消息 ID 去重；电脑端继续执行已接受的任务；手机回来后按事件游标补进度。用户消息发送成功、电脑接收、Relay 接受、任务完成应是不同回执。这里不要求新建云服务，也不能把手机通知送达率当作任务执行成功率。

## 4. 跨端连接与长程执行：复用成熟设施，保留应用语义

### 4.1 第一阶段连接选择

可先支持同一受控网络，再提供用户自选的 Tailscale Serve 指南。官方 Serve 仅向 tailnet 内设备提供本地服务；Funnel 才把服务开放到互联网。Serve 可提供 HTTPS，仍受访问控制规则约束。它解决连通与传输接入，不能代替 E-Moti 的设备撤销、owner/角色隔离和任务批准检查。项目不应默认公开 Relay 端口，不应在聊天中回显已有连接密钥。[Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)、[访问控制](https://tailscale.com/docs/features/access-control)、[Funnel](https://tailscale.com/docs/features/tailscale-funnel)。

Tailscale 官方客户端仓库许可证为 BSD-3-Clause，Temporal server 仓库为 MIT；本批只研究其机制与部署选项，没有复制源码、打包二进制或新增运行时依赖。Tailscale 托管服务和不同平台分发包应按各自条款评估，不用单个 GitHub LICENSE 覆盖所有服务。[Tailscale LICENSE](https://github.com/tailscale/tailscale/blob/main/LICENSE)、[Temporal LICENSE](https://github.com/temporalio/temporal/blob/main/LICENSE)。

### 4.2 “可靠”应落在可测的任务行为上

| 用户关心的行为 | 应记录/检验的事实 | 不足以证明它的信号 |
|---|---|---|
| 建议采纳后持续推进 | 已批准的明确任务、执行目标、期限、预算、下一次检查时间 | 角色说“我会一直帮你盯着” |
| 手机退出后还能推进 | 电脑/常开宿主持久任务与恢复记录 | 手机有常驻通知 |
| 不重复下达同一条指令 | 请求 ID、命令摘要、下游幂等键、外部任务 ID、恢复时查询已有任务 | 只有本地去重字典 |
| 阶段汇报真实 | Relay/执行者的权威状态、检查时间、测试/产物引用、已知阻塞 | 模型总结“看起来已经完成” |
| 取消可控 | 取消请求、下游取消回执、仍运行/未知的区别 | UI 按钮立刻变成“已停止” |
| 掉线不误报 | 失联时间、最后一次确认状态、过期标记 | 没收到新消息就判失败/完成 |
| 不串角色、不恢复已遗忘事实 | owner、角色、会话版本、记忆/隐私版本检查 | 两端显示同一个头像 |

Temporal 的成熟做法包括持久执行历史、超时、心跳、重试与取消传播。它的官方文档也明确活动可能重试，需要幂等；心跳可以带恢复进度。因此即使未来引入 Temporal，仍需要 E-Moti/Relay 适配器定义真实副作用和幂等语义。[执行历史](https://docs.temporal.io/workflow-execution)、[故障检测与心跳](https://docs.temporal.io/encyclopedia/detecting-activity-failures)、[任务语义](https://docs.temporal.io/tasks)。

一个重要的实际边界：Temporal 的 Python MCP 集成说明 MCP activities 不自动 heartbeat，给它设置 heartbeat timeout 不会自动赋予取消传播能力；activity 超时也不会终止已运行的 MCP 请求。这说明“套上可靠工作流框架”不能作为工具已停止、远程副作用恰好执行一次的证明。[MCP 集成文档](https://docs.temporal.io/develop/python/integrations/mcp)。

本项目当前是单用户本地宿主，先使用现有 Python 与 SQLite 保存任务状态、批准、外部 ID、检查点和报告即可。等出现多宿主高可用、复杂跨日工作流、多个 worker 调度及运维需求，再评估 Temporal/类似持久执行引擎。手机客户端不负责运行这些工作流；这能减少后台限制与电量对长任务的影响。

### 4.3 统一人格和记忆的跨端含义

以下是设计建议，尚未宣称完整同步已实现：

1. 当前阶段由一个明确的 E-Moti 宿主持有人格/长期记忆真源。手机同步必要的版本和展示信息，不各自维护相互竞争的完整画像。
2. 每个事件携带 owner、角色、设备、发生时间、接收时间、来源类型与有效期。屏幕 OCR、可见节点、用户分享、用户聊天和 Relay 任务状态保留不同来源。
3. 移动端观察内容先进入短期上下文，只有明确、有依据的候选才走现有记忆确认入口；网页/聊天中看到的他人话语不能自动归为用户事实。
4. 撤销采集应让排队事件和晚到结果失效；纠正/遗忘应让所有在线展示端清理相关缓存。离线端无法即时收到撤销，需显示离线状态、限制敏感缓存有效期，恢复连接时先同步失效信息。
5. 任务事实由 Relay/外部执行器提供；E-Moti 记录自己提出、获准、观察和汇报了什么。人格可以用稳定风格说明进展，但不能改写外部权威状态。
6. 手机观测失败和用户安静模式都不应被人格解释成用户关系下降。工作插件关闭后，陪伴本体继续可用。

## 5. 平台验收最小清单

这份清单用于下一批真机开发，当前未执行这些平台验收。

| 平台 | 必须记录的环境 | 最先验证的场景 |
|---|---|---|
| macOS | 硬件架构、OS、Python/Qt 锁定版本、最终 `.app` bundle ID、签名/沙盒状态 | 首次和撤销 TCC；前台应用；单窗口录屏；浏览器 URL 来源；多显示器；应用退出/睡眠；TTS 替代；透明窗/托盘 |
| 原生 HarmonyOS 手机 | 机型、完整版本、API、普通/调试/企业签名 | 正常聊天/断线补发；授权录屏与中断；辅助扩展用户启停；B站/微信节点覆盖；受限 API 的真实错误；锁屏和后台回收 |
| 所有客户端 | owner、角色、连接设备、服务端版本、任务关联 ID | 重复请求；改动后的批准失效；掉线重连；未知结果不自动重发；取消后晚到事件；忘记后离线端重连；禁止采集应用不入队 |

验收应分别输出“代码已实现”“模拟测试通过”“官方文档支持”“真机通过”四类证据。此报告只能支持官方能力与架构判断，不能替代 APK/HAP/.app、商店审核或真实远程任务运行结果。

## 6. 来源核查说明

华为官方文档中心在 2026-09 迁移，若干旧链接读取失败或只返回空壳。本次对 AVScreenCapture、后台任务等结论使用当前官方搜索索引和可读取页面；对具体系统接口与权限级别读取 OpenHarmony 官方仓库原始文件，固定在 `f41b9345badd47c7ab0c263344cd7f4b5a549afb`（API 返回提交时间 2026-05-26）。OpenHarmony 是底层开源证据，不自动等于华为商业设备的功能开放承诺。未用个人博客的权限列表作为最终依据，也未把官方论坛用户的单机问题泛化成平台保证。

来源清单与读取方式见 [platforms-sources.json](platforms-sources.json)。若后续设备 API 与这里不同，应先复查对应版本和正式签名权限，再扩大实现范围。
