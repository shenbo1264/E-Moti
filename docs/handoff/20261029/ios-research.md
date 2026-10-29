# E-Moti：iOS 手机适配补充研究

检索日期：2026-10-29（America/Los_Angeles）。本文件更正之前把用户的 iOS 手机需求理解成 macOS 桌面需求的问题。当前用户主设备为 Android/HyperOS 4；没有已确认的 iPhone 型号、iOS 版本、Apple 开发者账号或 Mac 开发环境。本轮完成官方资料核查，没有构建 iOS 应用或运行真机测试。

## 1. 结论与范围

建议采用 Swift/SwiftUI 原生薄客户端，共用 E-Moti 宿主的身份、角色、记忆与任务协议。聊天、语音入口、任务批准/取消、状态查看和主动分享均可通过普通应用接口实现，无需越狱。长程任务继续在电脑或其他持续在线宿主执行，手机负责交互、同步与通知。

手机观察需要按接口和条件分别实现。iOS 不能照搬 Android 的 UsageStats、NotificationListener 或 AccessibilityService。当前官方 API 已有新变化：iOS 27 的 ScreenCaptureKit 支持用户选择后的屏幕流；iOS 26.4 的 FamilyActivityData 支持特定条件下非 token 化的应用/网站信息。不能再笼统写成“iOS 无法观察”或“ScreenCaptureKit 只适用于 Mac”。这些能力也不能推导为所有 iPhone、所有地区均可用。

最低 iOS 版本留给客户端依赖和实际目标设备确定。**iOS 27 仅是可选屏幕能力分支，不自动成为整个客户端最低版本。** macOS/Xcode 是构建条件，不构成新增 Mac 桌面产品需求。

## 2. 能力矩阵

| 能力 | 普通 iOS 应用的实现与条件 | E-Moti 取舍 |
|---|---|---|
| 聊天、下达远程任务、查看进展 | URLSession HTTPS；需要实时前台流时可用 WebSocket 或其他标准流协议 | 与 Android 共用宿主协议，保留消息/请求标识和离线状态 |
| 局域网发现和连接电脑 | 本地网络授权；声明 NSLocalNetworkUsageDescription；浏览 Bonjour 时声明 NSBonjourServices | 支持手动地址或配对入口，拒绝授权时清晰提示，不绕过权限 |
| 分享网页、文字、图片、文件 | Share Extension 接收用户通过系统分享面板交付的内容 | 优先实现，保留来源与用户分享动作 |
| Siri / Shortcuts 入口 | App Intents 将本应用支持的操作和实体暴露给系统 | 可增加“询问 E-Moti”“查看任务”“发送请求”，仍服从宿主授权 |
| 手机任务通知 | APNs；前台/重连后读取宿主权威快照 | 通知只表示有更新，不作为唯一事件日志 |
| 持续后台执行 | 系统特定后台模式；BGContinuedProcessingTask 用于用户前台发起的可完成工作 | 不将永久监督 Relay 的正确性寄托在手机后台 |
| 常规 Screen Time | FamilyControls、DeviceActivity、ManagedSettings；需授权及分发 entitlement | 可评估本机使用情况管理；不默认当作远端个人画像原料 |
| 非 token 化使用数据 | iOS 26.4+、专用 entitlement、approvedWithDataAccess；正式安装还有 EU 地区/账号条件 | 中国普通用户路径不依赖它 |
| 用户启动的屏幕观察 | iOS 27+ ScreenCaptureKit；较低系统可评估 ReplayKit 广播扩展 | 单独可选能力，按系统版本选择，不能默认静默常开 |
| 通用跨应用通知读取 | UNUserNotificationCenter 只管理本应用通知；新 AccessoryNotifications 有配件、地区及用途限制 | 不为一般 Agent 画像实现通知抓取入口 |
| 直接读取微信数据库、全局 UI 树、任意应用私有数据 | 普通第三方应用受 sandbox 与 entitlement 限制，没有在本次核查中发现适用的通用公共 API | 不承诺；用户主动分享或授权屏幕会话另行处理 |

普通网络能力依据：[URLSession](https://developer.apple.com/documentation/foundation/urlsession)、[URLSessionWebSocketTask](https://developer.apple.com/documentation/foundation/urlsessionwebsockettask)、[TN3179 本地网络隐私](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy)。这是技术可行性与方案判断，不代表现有 E-Moti 已有可供手机调用的认证接口。

## 3. 主动分享与 App Intents

Apple 的 Share Extension 接收用户从分享面板选择的链接、图片、视频或文件。应让用户选择目标角色/会话，并展示实际分享内容，不能把一个网页链接自动描述成已经读取了完整浏览历史。[官方 Share Extension 文档](https://developer.apple.com/documentation/foundation/supporting-suggestions-in-your-app-s-share-extension)、[扩展数据交换](https://developer.apple.com/library/archive/documentation/General/Conceptual/ExtensibilityPG/ExtensionScenarios.html)。

App Intents 描述应用自己的动作和数据，供 Siri、Shortcuts、Spotlight 等系统体验调用。它不会直接把 Siri 的所有跨应用个人上下文交给 E-Moti。其他应用是否可参与某个工作流，还取决于它们公开的操作及系统能力。[App Intents](https://developer.apple.com/documentation/appintents)、[创建第一个 App Intent](https://developer.apple.com/documentation/appintents/creating-your-first-app-intent)。

## 4. Screen Time：必须区分旧授权与新增数据访问

常规 FamilyControls 支持个人设备所有者授权；普通 approved 状态下，应用/网站选择主要使用 opaque tokens。DeviceActivity 提供日程、阈值和使用情况报告，ManagedSettings 提供限制能力。E-Moti 不需要为了获取使用信息而默认启用应用封锁。正式分发前，主应用及相关扩展的 Family Controls entitlement 需要按 Apple 流程申请和审核。[个人授权说明](https://developer.apple.com/videos/play/wwdc2022/110336/)、[分发 entitlement](https://developer.apple.com/documentation/familycontrols/requesting-the-family-controls-entitlement)。

新增数据接口的官方 Markdown metadata 和正文已直接读取：

- `FamilyActivityData`、`approvedWithDataAccess`、`DeviceActivityData.activityData(filteredBy:using:)` 均标注 **iOS/iPadOS 26.4+**。
- 相应授权可取得实际应用 bundle identifiers、已访问网站的域名和类别名称；不是微信聊天内容或任意网页正文。
- 必须具备 `com.apple.developer.family-controls.app-and-website-usage`，并获得用户明确授权。
- 官方允许使用 Apple provisioning profile 在各地区开发测试；**正式用户安装仅限设备位于 EU 且 Apple Account 地区为 EU**。
- 每台设备同一时刻只有一个应用可持有该数据访问授权；授权给另一个应用会改变原应用的授权状态。

来源：[FamilyActivityData](https://developer.apple.com/documentation/familycontrols/familyactivitydata)、[approvedWithDataAccess](https://developer.apple.com/documentation/familycontrols/authorizationstatus/approvedwithdataaccess)、[导出接口](https://developer.apple.com/documentation/deviceactivity/deviceactivitydata/activitydata(filteredby:using:))、[专用 entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.family-controls.app-and-website-usage)。

Apple 开发者协议对 FamilyControls 的主要用途及数据使用作了限定，集中在家庭控制和个人设备使用管理。不能仅凭用户在 E-Moti 打开开关，就把它作为任意远端模型训练或画像数据源。上述新导出 API 存在，也不能自动证明 E-Moti 的具体用途、分发与远端处理都已获准。当前应把这部分保持为独立可选研究项，针对实际用途核验。[Apple Developer Program License Agreement，3.3.3(P)](https://developer.apple.com/support/terms/apple-developer-program-license-agreement/)。

## 5. 屏幕观察：iOS 27 新路径与旧系统路径

**已核实的新路径：** ScreenCaptureKit 框架及 SCContentSharingPicker 的官方 availability 均包含 iOS 27.0+；官方 iOS 样例声明 iOS 27 与 Xcode 27。用户可在系统 picker 中选择全屏捕获或应用内捕获，样例用 `screen-capture` 后台模式继续全屏流；麦克风是另一个选择。官方说明新的屏幕流方案无需 ReplayKit broadcast extension。[框架](https://developer.apple.com/documentation/screencapturekit)、[iOS 样例](https://developer.apple.com/documentation/screencapturekit/capturing-screen-content-on-ios)、[系统 picker](https://developer.apple.com/documentation/screencapturekit/sccontentsharingpicker)。

**版本状态：** 部分搜索缓存和旧 release notes 仍出现 Beta 字样；Apple Newsroom 的 2026-09-14 页面已宣布 iOS 27 推出，当前 Xcode 要求表也将 Xcode 27、27.1 与 27.2 RC 分列。因此这里记录为已有正式系统版本中的 API 路径，仍需在目标 iPhone 和所选 SDK 上验证；不把样例、编译成功或模拟器等同于手机采集验收。[正式发布](https://www.apple.com/newsroom/2026/09/major-updates-for-apples-software-platforms-are-now-available/)、[当前 Xcode 支持表](https://developer.apple.com/xcode/system-requirements)。

**较低系统：** `RPSystemBroadcastPickerView` 让用户选择广播提供者，`RPBroadcastSampleHandler` 接收视频/音频样本和开始、暂停、恢复、结束回调；当前官方页面标记该 picker 在 iOS 27 deprecated，不能解释成旧系统完全不能用。[ReplayKit picker](https://developer.apple.com/documentation/replaykit/rpsystembroadcastpickerview)、[SampleHandler](https://developer.apple.com/documentation/replaykit/rpbroadcastsamplehandler)。

E-Moti 实现时应将“开始观察、当前会话、停止、授权撤回”显式展示；手机预处理/抽帧与 OCR/VLM 输出都带设备、角色、时间、会话标识和有效期。屏幕会话结束后，已经排队的识别结果必须被当前授权版本拒绝。具体受保护内容、锁屏中断、目标应用切换、帧率和耗电需真机测量。本轮未复制样例代码，没有许可证已处理或可运行采集的声明。

## 6. 通知与跨应用内容的准确边界

普通 `UNUserNotificationCenter.getDeliveredNotifications` 读取的是**本应用**仍在通知中心的通知，不能当作 Android NotificationListener。[官方 API](https://developer.apple.com/documentation/usernotifications/unusernotificationcenter/getdeliverednotifications(completionhandler:))。

新 AccessoryNotifications 确实提供用户授权的其他应用通知转发，但面向配件 companion app 和相关扩展，正式用户安装受 EU 地区与账号限制。更关键的是 Apple 协议 3.3.7(J) 明确限制把 Forwarding Information 用于 profiling、training models，限制发往其他设备或远端存储。因此它不适合作为本项目通用“采集聊天语料、理解用户”的通道；本交接不展开实体硬件开发。[AccessoryNotifications](https://developer.apple.com/documentation/accessorynotifications)、[官方接收流程](https://developer.apple.com/documentation/accessorytransportextension/receiving-ios-notifications-on-an-accessory)、[协议 3.3.7(J)](https://developer.apple.com/support/terms/apple-developer-program-license-agreement/)。

Apple 的运行时安全文档明确第三方应用被 sandbox 隔离，跨应用信息访问依赖系统明确提供的服务。基于本次 API 核查，不能为普通 E-Moti App 承诺全局辅助功能节点读取、任意通知历史和微信私有数据库读取。用户分享与已授权屏幕观察仍是独立可行路径。[iOS 运行时安全](https://support.apple.com/en-au/guide/security/sec15bfe098e/web)。

本产品不以越狱为前提，也没有验证任何越狱路径。不要把“可能取得更高权限”写成产品已支持功能。

## 7. 后台执行、通知与长程任务

一般 iOS 应用进入后台后会被挂起，只有声明并符合用途的系统模式获得相应执行机会。`BGContinuedProcessingTask` 自 iOS 26 起支持用户在前台发起、后台继续的可完成工作；仍可能被用户取消或被系统终止，不是永久 daemon。[后台模式](https://developer.apple.com/documentation/xcode/configuring-background-execution-modes)、[持续处理任务](https://developer.apple.com/documentation/backgroundtasks/bgcontinuedprocessingtask)、[长任务指导](https://developer.apple.com/documentation/backgroundtasks/performing-long-running-tasks-on-ios-and-ipados)。

APNs 可通知 E-Moti 有新消息或任务进展；后台通知可能被延迟、合并、节流或丢弃，不能承载唯一的任务真相。架构应保持宿主持久日志，手机唤醒、重连或前台进入时按游标/快照补齐状态，展示最近更新时间；不要要求无期限后台 WebSocket 保活。[后台推送](https://developer.apple.com/documentation/usernotifications/pushing-background-updates-to-your-app)、[APNs 请求](https://developer.apple.com/documentation/usernotifications/sending-notification-requests-to-apns)。

## 8. 构建与验收条件

原生 iOS 客户端需要匹配 SDK 的 Xcode/Mac 构建环境，以及真机签名。当前 Xcode 表显示 Xcode 27/27.1 需要 macOS Tahoe 26.6+；实际开发时根据部署目标选工具版本，不要求用户为了先做 Android 购买 Mac。[Xcode 支持表](https://developer.apple.com/xcode/system-requirements)。

免费 Personal Team 可安装到个人设备测试，但 provisioning 有期限，Apple 官方账户文档目前列为 7 天；高级能力和 TestFlight/App Store 等分发需要相应开发者计划、签名与能力许可。免费安装、获准 entitlement 和正式可分发是三个不同状态。[开发者账户说明](https://developer.apple.com/help/account/basics/about-your-developer-account)。

必须保留未验证项：iOS 工程/构建、真实设备、系统版本覆盖、分享扩展、推送凭据、能力审批、屏幕会话、锁屏/切后台、功耗、OCR/VLM 和实际 Relay 协议。当前项目不能仅因提供 iOS 设计文档而标记这些完成。

## 9. 给 Claude / Codex 的直接实施约束

- Claude：为 iOS 设计与 Android 同一人格、任务和记忆体验；权限页依据实际能力状态展示，不显示无法兑现的全局观察开关。实现客户端与平台扩展时保留来源、会话和授权撤回状态。
- Codex：提供端无关的认证、任务与记忆协议；长程监督在宿主；观察输入与用户命令区分；处理过期、撤回、重连及派生聊天/摘要/TTS 的来源失效。
- 共同：先完成普通权限下聊天、分享、远程任务和真实回执；iOS 屏幕流作为明确版本条件的可选能力；Screen Time 数据与配件通知不加入中国普通用户路径的必要依赖。
- 本轮范围为 Android/HyperOS、iOS 手机和华为手机原生鸿蒙；任何 macOS 讨论只保留为旧研究或 iOS 构建条件，不继续增加 Mac 桌面验收任务。
