# E-Moti 正式客户端接线图

Overlay 只替换 `app.py` 中的控制器 import，并插入三个页面：星屑回忆册、探头时刻、插件中心。游戏结算仍由原 `CompanionController` 完成；`PluginEnabledCompanionController` 只在边界处追加只读上下文、扩展动作和记忆提案。

重点核验：动态动作按钮、角色切换后的记忆命名空间、插件启停、窗口关闭时卸载插件、桌宠模式与控制面板共享同一控制器。
