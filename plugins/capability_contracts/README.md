# E-Moti Capability Contracts

这个内置插件只定义稳定接口，不绑定供应商。现有 DeepSeek、Edge TTS、SenseVoice、屏幕摘要与搜索模块可以在正式合入时各自注册成 Provider。

把 Definition 与 Provider 分开之后，替换模型或语音服务不需要修改 Controller 和调用方。
