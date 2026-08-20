E-Moti 插件起步模板

1. 复制 plugin 目录。
2. 修改 emoti-plugin.json 中的 id、name、description 和 permissions。
3. 在 plugin.py 的 activate(ctx) 中注册动作、技能、上下文或页面。
4. 运行：python tools/validate_emoti_plugin.py <你的插件目录> --activate
5. 运行模板测试，再打包为 ZIP。

插件运行在应用进程内。只声明实际需要的权限；不要在 manifest 或设置里写 API Key。
