# E-Moti 最后一次本地全量复测报告

## 结论

当前交接包中的跨平台 Overlay 已完成最后一次本地复测。测试覆盖情感记忆、召回、回忆册控制器、探头时刻、插件 Manifest、依赖、权限、可撤销注册、服务接口、安装卸载、静态审计、故障隔离、隔离恢复、插件中心控制器、递归密钥扫描、预览工具和一键合入合同。

## 基线

```text
upstream repository: shenbo1264/E-Moti
upstream main commit: e840d77dc35d95c507d65f5de5c5ff2bac65f363
local mode: portable integration overlay + real Xingxi assets
remote writes: none
```

## 最终结果

| 项目 | 结果 |
|---|---:|
| Compileall | 通过 |
| Overlay pytest | 166 passed |
| Overlay 总覆盖率 | 79% |
| Plugin Host Smoke | 通过 |
| Plugin Runtime V2 Smoke | 通过 |
| Overlay 合同 Smoke | 通过 |
| Capability Contracts 激活 | 通过 |
| Local Expression Fallback + 依赖激活 | 通过 |
| Stargazing 插件激活 | 通过 |
| 插件中心预览 | 生成成功 |
| 回忆册/探头/插件预览 | 生成成功 |
| 插件生命周期 GIF | 生成成功 |
| 公开配置密钥扫描 | 通过 |
| 内置插件目录密钥扫描 | 通过 |
| 热牛奶—记忆—召回 Smoke | 通过 |
| 探头时刻不改养成状态 | 通过 |
| 私有 Provider 报告泄露密钥 | 未发现 |

## 关键行为

- 第一次热牛奶长期记忆：1 条。
- 普通重复热牛奶长期记忆：0 条。
- 第一次共同学习：1 条。
- 关系章节：《我们的第一份小默契》，来源 3 条。
- 热牛奶相关问题能够召回对应记忆。
- 无关像素美术问题召回数量为 0。
- 探头时刻完成后形成共同经历，金币、背包、信任等状态保持不变。
- 星图角落第一次互动生成《第一次一起看星星》；第二次不重复生成；停用插件后动作撤销，回忆保留。
- 本地插件安装、启用、停用、卸载和 ZIP 打包链路通过。
- 故障插件连续失败三次后隔离，宿主继续运行。

## 私有 Provider Smoke

课程包中的 DeepSeek 与 MiMo 配置已在内存中读取，报告没有输出 Key。当前容器网络不可达：

```text
online_verified: false
secrets_in_report: false
```

这只能证明配置读取、请求构造、硬超时和脱敏报告可用，不能证明供应商返回成功。Codex 需在可联网的本地 Windows 环境完成真实响应测试。

## 仍需 Codex 完成

- 将 Overlay 接入完整上游仓库并处理真实接口漂移；
- 正式 PySide6 GUI Smoke；
- 宿主 LLM/TTS/ASR/屏幕摘要/搜索 Provider 接线复核；
- Windows 便携版和安装器构建；
- 正式客户端录屏；
- 公开候选包与最终公众号完成度同步。

Linux 中通过的 Overlay 测试不能代替 Windows GUI 与打包验收。
