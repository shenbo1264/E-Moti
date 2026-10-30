# 当前工程状态与证据

日期：2026-10-29。此文件为交接整理，不新增生产功能。提交和代码应以接手时的最新仓库为准，以下记录用于识别本包已包含的内容。

## 1. 版本

| 版本 | 含义 |
|---|---|
| `b9f200955123790a5c66abcaf4e2567b3659a90e` | 本轮重新核对的 GitHub main；2026-08-20 合入原 Emotional Memory / Plugin Runtime |
| `fa19b2cab14efe63b6b53a4894d76741a6b7c392` | 2026-10-25 本地记忆/人格生命周期升级 |
| `078ef1ca8b4ab714b8c64f2f9cdbe645c80464a2` | 2026-10-28 本地任务日志/短期观察基础 |
| 本交接提交 | 在 `078ef1c` 上修正文档范围、汇总需求和提示词；精确 SHA 见包根 `DELIVERY.json` |

本次只读核查 main、远端分支列表与开放 PR，开放 PR 为零；完整精简记录见 [repository-check.json](evidence/repository-check.json)。两个远端历史分支未改动。本地增量未推送，不能只克隆 main 就认为获得了这两批代码。接手时若远端有新变化，应以实际差异合并。

## 2. 已实现、已测与未验分开

| 能力 | 当前实际状态 | 下一步 |
|---|---|---|
| Emotional Memory V2、CoreBondProfile、章节 | 已增量增加来源/版本/时效/事务与派生失效 | 保持不变量，完成独立holdout和实模型评估 |
| 实际 prompt 的记忆与人格接入 | 已从 PluginEnabled controller 接入 typed request / expressor | 手机继续复用同一路径 |
| 用户管理记忆 | 桌面明确添加、候选确认/拒绝、纠正、遗忘、来源查看已接 | 候选跨重启恢复、移动端管理和物理删除产品范围待完善 |
| 稳定人格 | 当前角色包/performance profile/可选persona已接；配置稳定有测试 | 自动有限演进与真实行为一致性未完成 |
| 检索 | 离线词法与来源过滤保留；复用Graphiti RRF；可选语义评分接口 | 没有默认embedding provider；比较真实收益后接入 |
| 原主动陪伴 | quiet hours、cooldown、daily limit、拒绝后退避有实现 | 与任务建议/报告统一节奏，避免第二套提醒系统 |
| Plugin Runtime | 注册/撤销/依赖/权限契约/插件中心有实现 | 同进程插件不是OS沙箱；不可信插件隔离未完成 |
| LLM/ASR/TTS/视觉 | 原实现保留，记忆失效与语音取消有回归 | 真机/实模型、全双工与UI非阻塞逐项验收 |
| `personal_tasks.py` | SQLite建议/批准/派发前记录/回执/取消/核对状态已实现 | 未接UI、认证传输、真实Relay、runner和推送 |
| `device_context.py` | 默认关闭、RAM短期来源、scope/TTL/ticket/epoch和撤回校验已实现 | 未接原生采集和完整派生历史/TTS/手机缓存撤回 |
| 手机客户端 | Android/iOS/华为手机的目标和研究存在 | 没有APK、IPA或HAP，也没有真机兼容结论 |
| 生态连接 | 职责边界与最小能力已设计 | 没有本批验证的真实Relay远程HTTP接口；未开发硬件固件 |

## 3. 已有实际测试记录

| 批次 | 结果 | 证据 |
|---|---|---|
| 原基线可比环境 | 1184 passed / 1 failed | [2026-10-25验证](../../modernization/verification.md) |
| 记忆/人格升级 | 1333 passed / 1 failed；新增149项 | 同上，保留原始日志 |
| 38条开发Memory Benchmark | 基线12/38，修复38/38；最终prompt正向交付0/11→11/11 | [基准口径](../../modernization/benchmark-spec.md) |
| 任务/设备新增 | 27+30=57项通过 | [2026-10-28验证](../../modernization/mobile/verification.md) |
| 最近一次完整套件 | **1390 passed / 1 failed，1391总数，0 errors、0 skipped** | 同上 |
| Personal Agent本地演示 | 18/18；真实Python/SQLite/typed prompt，手机和执行者输入为模拟 | 同上及原始JSON |

唯一全量失败：`test_import_portrait_video_to_source_pack_cli_runs_from_repo_root` 使用 Windows 的 `ffmpeg.cmd` fixture，Linux 调用系统 FFmpeg 对假MP4解码失败。在未修改的前一批基线上已同环境复现。不要隐藏失败，也不要把它误称为本次新增回归。

记忆基准只验证确定性工程契约和prompt暴露，不测真实模型答对率。persona hash不变只验证配置，不能证明人格行为一致。延迟包含的阶段、token估计、分母均见原始报告。

本轮交接仅编辑文档，没有重复运行完整pytest；通过生产代码指纹与既有记录确认它们仍对应相同源码。轻量检查结果见 [handoff-checks.json](evidence/handoff-checks.json)。

## 4. 两个必须避免的接手错误

**默认角色。** 实际 `src/guanghe_companion/character_pack.py` 的 `DEFAULT_CHARACTER_ID` 是 `xingxi_pixel_pet`。旧 `AGENTS.md` 曾描述 `original_oc` 默认；本交接已纠正文档。保留实际默认和用户选择，不按旧文字改回、重画或删除素材。

**控制器。** `app.py` 导入的是 `PluginEnabledCompanionController as CompanionController`。新入口应复用它的服务链；直接包装基础 controller 可能绕开已修复的记忆与人格上下文。

## 5. 环境与入口

当前声明：Python >=3.11；PySide6==6.11.0；Pillow>=12.1.0；ddgs>=9.0.0；edge-tts>=7.0.0。无需为整理交接升级依赖。安装与运行以项目 README / `pyproject.toml` 为准。

主要源码与测试导航见 [原记忆交接](../../modernization/handoff.md)、[多端交接](../../modernization/mobile/handoff.md)。重点保留 `test_memory_prompt_lifecycle.py`、`test_controller_memory_compatibility.py`、`test_voice_invalidation.py`、`test_personal_tasks.py`、`test_device_context.py` 及原有 UI/插件/角色回归。

后续在合适环境可运行：

```bash
python -m pip install -e . pytest
python -m pytest tests/test_personal_tasks.py tests/test_device_context.py -q
python tools/memory_benchmark.py --output memory-benchmark-local.json
python tools/run_personal_agent_smoke.py --output personal-agent-smoke-local.json
python -m pytest -q
```

Linux离屏Qt配置与Windows打包命令在原验证/根AGENTS中；不要把临时容器路径或测试sandbox设置写入产品启动默认。真实用户存档只用副本验收，运行报告不提交个人对话和凭据。
