# 平台范围更正与实施决定

日期：2026-10-29。用户已明确：此前 macOS 指的是 iOS 手机，鸿蒙指华为手机鸿蒙。本文替代旧多端方案中的 Mac 桌面里程碑；旧平台研究保留历史来源，不再作为该需求的任务清单。

## 1. 当前平台矩阵

| 平台 | 目标 | 建议客户端 | 当前状态 |
|---|---|---|---|
| Windows 桌面 | 保留独立桌宠、控制面板、人格记忆与宿主能力 | 继续 Python/PySide6 | 已有工程；真实用户机器与安装器随改动验收 |
| Android / HyperOS 4 手机 | 首先完成聊天、记忆管理、远程任务、主动分享；再接授权观察 | Kotlin / Jetpack Compose | 尚无APK和真机联通 |
| iPhone / iOS | 同一人格、聊天、分享、任务与状态；观察能力按实际系统开放 | Swift / SwiftUI | 本轮补官方研究；尚无iOS工程或IPA |
| 华为手机原生 HarmonyOS | 同一交互协议；原生分享、权限、后台与观察适配 | ArkTS / ArkUI，必要时原生桥接 | 原官方研究保留；尚无HAP或真机验收 |

上述技术选型是基于当前需求的主方案。若新证据表明成熟跨平台方案能显著减少维护成本，同时满足原生权限/扩展需求，可以提出具体替代；不先搬迁 Python 核心，不为统一UI牺牲必要能力。可选网页只承担轻量聊天/任务入口，不冒充原生系统采集。

## 2. Android / HyperOS

沿用 [Android研究](../../modernization/mobile/android-research.md) 和固定来源。普通聊天、远程任务、主动分享不需要 root。Usage Access、Notification Access、Accessibility、MediaProjection 分别处理；ADB/scrcpy/Shizuku 只是可选高级/测试途径。HyperOS 4 尚缺具体机型、地区、build和API级别；这些在真机验收时记录，不阻止先做宿主和客户端。

涉及Android 17目标API37的LAN连接，按官方本地网络权限机制适配。后台存活、锁屏、系统停止采集都属于客户端状态，不通过假“实时”掩盖。工作继续由宿主负责。

## 3. iOS 新增结论

详见 [iOS官方研究](ios-research.md)。已核查的方向：

- 普通客户端可通过HTTPS连接宿主，支持聊天、任务、记忆管理和Share Extension；App Intents可暴露E-Moti自身支持的操作。无需越狱。
- 连接局域网电脑要处理本地网络隐私；Bonjour发现配置单独声明。签名后的真机验证不能由模拟器替代。[Apple TN3179](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy)
- iOS27的ScreenCaptureKit有官方iOS样例，使用系统picker开启屏幕会话；较低系统可独立评估ReplayKit。iOS27仅作为可选能力条件，不擅自提高整个App最低版本。[官方样例](https://developer.apple.com/documentation/screencapturekit/capturing-screen-content-on-ios)
- iOS26.4+新增FamilyActivityData及非token化数据授权；正式用户安装仍受EU实际地区、EU Apple Account和专用entitlement等条件限制。中国用户默认路径不依赖这条能力，也不能由它推断可读取聊天正文。[官方授权说明](https://developer.apple.com/documentation/familycontrols/authorizationstatus/approvedwithdataaccess)
- AccessoryNotifications是受限的配件通知通道，其用途条件不允许把转发信息用来构建一般用户画像/训练模型；不作为E-Moti手机语料采集捷径。[框架](https://developer.apple.com/documentation/accessorynotifications)、[协议3.3.7(J)](https://developer.apple.com/support/terms/apple-developer-program-license-agreement/)
- 长程监督在宿主，APNs用于更新提示。后台处理与推送均不能代替持久任务和恢复查询。[后台任务](https://developer.apple.com/documentation/backgroundtasks/performing-long-running-tasks-on-ios-and-ipados)、[后台推送](https://developer.apple.com/documentation/usernotifications/pushing-background-updates-to-your-app)

原生iOS构建需要匹配SDK的Xcode/Mac和签名条件。这是开发环境要求，**不新增macOS桌面产品**。尚未确认用户持有iPhone或Mac；当前先完成Android不依赖这两项。

## 4. 华为手机鸿蒙

沿用 [华为/OpenHarmony证据](../../modernization/mobile/platforms-research.md) 中的手机相关部分。面向原生华为手机独立构建，不能把Android APK、鸿蒙PC或二合一特权路径当成手机能力。

聊天、分享、任务接口优先；用户授权录屏和三方辅助功能扩展按实际手机SDK、签名和发布用途验证。应用使用统计、直接截屏、免授权采集等系统权限不能被普通应用设置开关替代。OpenHarmony底层文档存在接口，不等于华为商业手机已批准本应用使用；root也不作为普通产品依赖。

## 5. 版本和权限如何进入产品

共用协议只表达能力与数据来源；客户端根据实际OS/API/授权/区域返回能力状态，前端显示可用、需授权、暂停、系统限制或未知。工作功能不要求观察权限。不要为了三个客户端看起来一样，把不可用能力显示成已开启。

未验证项统一保留：三端安装包、真实系统授权、具体App覆盖、锁屏/重启/后台、功耗、OCR/VLM、真实模型和Relay。资料核查与原型构建分别记录，不把其中一项代替其他验收。
