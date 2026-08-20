# E-Moti Plugin Runtime V2

V2 将插件能力分为 Action、Skill、Context、Memory Proposal、UI Panel、Service Definition 与 Provider。每项注册带所有者，卸载插件时反向撤销。第三方插件默认关闭；敏感权限需单独授权。连续失败三次进入隔离，日志会对凭证字段脱敏。

E-Moti 没有照搬 DeepSeek Harness/Cordis 协议。项目只吸收“可组合插件、可撤销 effect、能力定义与 Provider 分离”的设计，并保留本地游戏核心对存档、金币、背包、关系和成长状态的最终权威。
