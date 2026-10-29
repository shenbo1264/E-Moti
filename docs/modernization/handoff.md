# 给后续 Coding Agent 的交接

## 2026-10-29 当前入口

先读[Claude产品/前端、Codex后端的完整交接](../handoff/20261029/README.md)。用户更正多端范围为Android/HyperOS、iOS和华为手机原生鸿蒙；原Mac桌面目标取消。当前主线是手机与同角色记忆闭环、真实外部任务与长程监督；下文原P1记忆holdout保留为并行质量工作，不覆盖新的优先顺序。

## 2026-10-28 的后续增量

用户已将手机互通、主动建议、长程监督和平台权限评估纳入优先范围。先读[多端交接](mobile/handoff.md)、[实际验证](mobile/verification.md)与[多端架构](mobile/architecture.md)。这批新增任务 journal 和短时观测内核，保持下述记忆不变量；手机、网络、Relay 实连和完整观测派生撤回尚未实现。原 P1 记忆 holdout 仍有价值，当前下一条产品主线按多端 M1 推进。

## 先确认当前事实

本批从公开 main `b9f200955123790a5c66abcaf4e2567b3659a90e` 开始，不以旧聊天或旧方案代替源码。开始时已核验 PR #4 合并、无 open PR。开发分支为 `codex/personal-memory-lifecycle-20261025`；具体交付 commit、最终复核时间和文件校验值见随包记录与 [verification.md](verification.md)。后续开工请重新 fetch/main/PR 检查，不能沿用这里的“无 open PR”结论。

读取根目录 `AGENTS.md`，然后看 [差距矩阵](gap-matrix.md)、[架构](architecture.md)、[迁移](migration-and-recovery.md) 和 [路线图](product-roadmap.md)。本批不改 Relay、Game Companion 或 Body 固件，不改变角色资源或默认角色。

## 必须保住的不变量

1. E-Moti 无外部系统也能启动、互动和管理记忆；没有模型时回退本地表达，不宣称仍具有同等自由对话能力。
2. 角色/owner/scope/时间/退役状态先于排序；embedding 高分或 pinned 不能覆盖这些检查。
3. 一份长期事实真源。旧 JSON、旧对话、memory_log、插件缓存不能绕过 V2 有效性检查再次注入 prompt。
4. 纠正/遗忘连同派生失效和 epoch 在一次事务中提交。批量写入、低层 upsert、插件与迁移不能成为旁路。
5. 任意含事实的派生内容必须保留来源与版本；不可用时先隔离再重建。原始源被删除后，不因摘要生成失败而继续提供旧摘要。
6. 异步工作读取 epoch 后，提交与展示前再次比较；晚到的旧结果、取消后音频、旧 pending 不得恢复。
7. 人格来源是当前角色包/配置；修改用户事实不改人格。LLM 文案不是真实事件证明。
8. 不把历史不可召回说成物理删除；不把 hash 稳定说成真实模型人格一致；不把本地耗时说成端到端延迟。

## 源码导航

| 任务 | 入口 | 主要回归 |
|---|---|---|
| 生命周期/事务/迁移 | `emotional_memory.py`、`memory_document.py`、`legacy_memory_migration.py` | `test_memory_lifecycle.py`、`test_memory_adversarial.py` |
| 受控写入/画像/章节 | `emotional_memory_service.py`、`emotional_memory_policy.py`、`emotional_memory_reflection.py` | lifecycle、既有 emotional_memory tests |
| 排序与可选语义扩展 | `emotional_memory_retrieval.py`、`memory_fusion.py` | `test_memory_retrieval_fusion.py`、`test_memory_fusion.py` |
| 稳定人格/实际表达 | `persona.py`、`companion_dialogue_policy.py`、`expression_expressor.py` | `test_persona.py`、原角色包/策略 tests |
| 真正模型输入/缓存 | `plugin_enabled_controller.py`、`memory_integration_bridge.py`、`expression_request.py`、`expression_event_pipeline.py` | `test_memory_prompt_lifecycle.py`、`test_memory_prompt_budget.py` |
| 用户可管理闭环 | `memory_album_controller.py`、`memory_album_qt.py`、`memory_album_view_model.py` | `test_memory_album_lifecycle.py` 与原 Qt 集成 tests |
| 插件候选与来源 | `plugin_story_bridge.py` | `test_plugin_memory_lifecycle.py` 与原 Plugin Runtime tests |
| 对照实验 | `tools/memory_benchmark.py`、`tests/fixtures/memory_benchmark.json` | `test_memory_benchmark.py`、before/after JSON |
| 旧入口兼容 | `plugin_enabled_controller.py` 的 alias/keyed write/expressor replacement | `test_controller_memory_compatibility.py` |
| 语音失效 | `voice_async.py`、`voice_tts.py`、`app.py` | `test_voice_invalidation.py`，真实模型与播放设备另验 |

## 可执行复现

在独立测试环境安装项目与 pytest，使用临时存档。完整依赖声明在 `pyproject.toml`；Linux 离屏 Qt 可能还需要发行版的 Qt/X11 动态库。

```bash
python -m venv .venv
# 激活该虚拟环境后：
python -m pip install -e . pytest
python -m pytest -q
python tools/memory_benchmark.py --output memory-benchmark-local.json
```

Linux/headless 与本次可比的设置：`TZ=UTC`、`QT_QPA_PLATFORM=offscreen`、`QTWEBENGINE_DISABLE_SANDBOX=1`，并将仓库 `src` 的绝对路径加入 `PYTHONPATH`，使既有子进程 CLI 测试可导入项目。QtWebEngine 的 sandbox 开关仅用于隔离验收容器，不应顺手改进产品默认启动设置。既有 Live2D 本地服务器测试需要允许 `127.0.0.1` 监听。

基线对照使用同一新 runner，而不是运行旧仓库不存在的工具：

```bash
git worktree add --detach ../E-Moti-baseline b9f200955123790a5c66abcaf4e2567b3659a90e
python tools/memory_benchmark.py --repo ../E-Moti-baseline --output memory-benchmark-baseline.json
```

全量测试存在一个已经在未修改基线复现的 Linux 平台失败：视频导入测试只创建 Windows `ffmpeg.cmd`，Linux 选中系统 ffmpeg 后无法解码测试用假视频。最终记录必须保留这项失败，不为得到全绿而跳过或调整期望。

## 人格模板使用

`examples/persona/curious-companion.json` 是可选模板，适合“好奇、自然、有判断、偶尔吐槽”的风格。复制到用户自己的角色包目录并命名 `persona.json`，根据目标角色填写/删除可选 `character_id`；不要默认覆盖 bundled packs。schema 版本、field limits、非法文件回退见 `persona.py` 和测试。后续人格成长只能提交带来源和前后 diff 的候选，不能在普通聊天中直接写此文件。

## 下一个最有价值的开发任务

优先 P1：冻结独立的中文多会话 holdout，加入否定/纠正/临时偏好/角色扮演/游戏角色事实；接一个可关闭的 embedding provider，比较同预算词法和混合检索。使用真实模型输出评价事实答对、误召回、过时引用、遗忘泄露和人格行为；只有确有收益才扩大依赖。

其次完善用户控制：持久化待确认候选、可查看画像来源、明确遗忘与永久删除、损坏恢复引导、关系章节的受控后台重建。再推进主动陪伴节奏和完整语音打断。完整外部状态 envelope 与 Body surface 协议位于 P3，不能把它们描述成当前已可联动。

每项 PR 都要说明问题、真实入口、用户行为改变、测试证据和未验证环境。应优先扩展本批 API，不另开一套同职能 memory service。不要改原有失败测试让新结果显得更好；不要用新生成的“理想回答”代替调用真实表达链路。
