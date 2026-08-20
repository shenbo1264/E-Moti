# E-Moti Plugins

本目录存放可独立启用的插件包。

- `capability_contracts/`：内置 Service Definition，给 LLM、TTS、ASR、屏幕摘要和搜索提供稳定接口。
- `stargazing_moment/`：随附示例，展示动作、记忆、上下文和 UI ViewModel 四类贡献。

正式客户端应同时扫描：

```text
<app_root>/plugins/                 # 随应用分发的内置插件
<user_data>/plugins/installed/      # 玩家本地安装的插件
```

第三方插件在子进程隔离完成前保持手动安装和默认关闭。
