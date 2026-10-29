# 实施与验证记录

日期：2026-10-25。目标仓库：`shenbo1264/E-Moti`。开始与交付前的远端核验均指向 main `b9f200955123790a5c66abcaf4e2567b3659a90e`；最后一次核验为 16:07:54 UTC，open PR 为空。改动位于本地分支 `codex/personal-memory-lifecycle-20261025`。没有发布 Release、推送远端、修改仓库可见性或操作真实用户存档。根目录 `AGENTS.md` 要求没有明确请求时不 push/open PR，本次交付可审查的完整源代码与补丁。

## 1. 实际完成的范围

- 保留 Emotional Memory V2 / CoreBondProfile / Character Pack / Plugin Runtime 的主体接口，升级生命周期与单一权威事务存档。
- 让有效 V2 记忆、当前角色人格和受限插件上下文真正进入 `ExpressionRequest` 与最终 LLM prompt。
- 支持事实来源、owner、scope、版本、置信度、有效期；事务内纠正、遗忘、退役来源与 epoch 更新。
- 章节/画像依赖来源内容指纹，失效后不继续进入模型；旧聊天、旧长期记忆通道、感知/工具缓存与晚到表达按 epoch 隔离。
- 角色切换先完成角色/记忆/人格更新，再生成表达；更换 LLM 设置保留实际角色 performance profile。
- 回忆册新增显式添加、候选确认/拒绝、完整正文纠正、来源检查；原称呼入口及旧 keyed host API 接入权威 V2。
- 取消旧语音队列，阻止内置 HTTP/Edge/SAPI provider 在取消后重新开始旧播放；实际设备另验。
- 复用并集成 Graphiti RRF，保留 Apache-2.0 来源；可选语义评分 adapter 尚未接默认 embedding provider。
- 一次迁移保留原 JSON；坏结构不静默丢弃；旧共享目录的非默认 owner 能按来源隔离迁移；损坏/缺失权威库拒绝无提示回源。

本批没有修改 `assets/`、`plugins/`、`packaging/` 中的原有角色资源、插件包和打包文件。没有新增第三方运行依赖，SQLite 使用 Python 标准库。

## 2. 全量测试：保留失败与分母

| 被测版本/运行 | 通过 | 失败 | 总数 | 用时 | 解释 |
|---|---:|---:|---:|---:|---|
| 未改基线，原容器环境 | 1176 | 9 | 1185 | 96.20 s | 含时区、子进程导入路径、loopback 限制及 archive 无 git index 等环境问题 |
| 未改基线，可比环境 | 1184 | 1 | 1185 | 90.09 s | 唯一剩余为 Linux FFmpeg 测试夹具 |
| 本批首轮整合 | 1332 | 2 | 1334 | 114.56 s | 发现一次新接口兼容回归，以及同一 FFmpeg 基线失败 |
| 本批最终全量 | **1333** | **1** | **1334** | **123.25 s** | 新增 149 项测试；0 error、0 skip；唯一失败与基线一致 |

最终环境：Python **3.12.14**、pytest **9.1.1**、PySide6 **6.11.0**、Linux x86_64，`TZ=UTC`、`QT_QPA_PLATFORM=offscreen`。Qt 所需 native 库在临时验收目录中提供；既有本地 HTTP/Live2D 测试允许监听 loopback。没有为通过测试而改变原有 FFmpeg 用例或隐藏失败。

唯一失败是：

```text
tests/test_portrait_video_source_pack_import.py::test_import_portrait_video_to_source_pack_cli_runs_from_repo_root
```

该既有测试只创建 Windows `ffmpeg.cmd`。Linux 的 `shutil.which("ffmpeg")` 选择了系统真实 FFmpeg，测试生成的假 MP4 无法解码。它在完全未改的基线中已复现；这不是对 Windows 真机视频导入成功或失败的判断。

首轮新增失败是 `test_expression_request_from_snapshot_keeps_only_readonly_summary_fields`：对未启用个人上下文的旧调用者，三个空扩展字段改变了精确返回集合。修复为“仅携带有内容的扩展，缺省保留旧白名单结构”，expressor 使用安全缺省值。原用例未修改；相关 **144 项通过**，随后才执行上述最终全量。

原始输出以 gzip **无损**保存，不改失败内容或退出状态：[基线原环境](evidence/pytest-baseline-raw-environment.txt.gz)、[基线可比环境](evidence/pytest-baseline.txt.gz)、[首轮整合](evidence/pytest-after-initial.txt.gz)、[最终全量](evidence/pytest-after.txt.gz)、[最终 JUnit XML](evidence/pytest-after.xml.gz)。解压前后 SHA-256 与汇总在 [verification.json](evidence/verification.json)；基线生产树哈希和环境区别在 [baseline-verification.json](evidence/baseline-verification.json)。

### 最终全量命令

```bash
PATH=/tmp/emoti-venv/bin:$PATH \
PYTHONPATH=/workspace/scratch/ac4f72a6307d/E-Moti/src \
TZ=UTC \
LD_LIBRARY_PATH=/tmp/emoti-native/usr/lib/x86_64-linux-gnu \
QT_QPA_PLATFORM=offscreen \
QTWEBENGINE_DISABLE_SANDBOX=1 \
python -m pytest -q --disable-warnings \
  --junitxml=docs/modernization/evidence/pytest-after.xml
```

临时目录属于本次验收环境，其他机器应替换为自己的虚拟环境、仓库与 Qt 库路径。QtWebEngine sandbox 开关只用于隔离验收容器，不修改产品默认设置。

## 3. 同一数据集、同一 runner 的 Memory Benchmark

| 指标 | 基线 | 本批最终 | 含义 |
|---|---:|---:|---|
| 整例通过 | 12/38 | **38/38** | 38 条开发中的合成契约用例 |
| 正向 service recall 检查 | 11/11 | **11/11** | 目标 ID 能进入检索结果 |
| 正向最终 prompt 事实交付 | 0/11 | **11/11** | 确认真正到达模型输入 |
| 无关召回案例 | 0/3 | **0/3** | 当前三个负例，不外推总体误召回 |
| 过时事实暴露案例 | 4/6 | **0/6** | 中间上下文/最终 prompt，未生成回答 |
| 遗忘/派生/迁移泄露案例 | 8/10 | **0/10** | 已撤回来源及已知派生路径 |
| 角色/owner/场景污染案例 | 4/5 | **0/5** | 按角色、owner、scope 检查 |
| 禁止的事件仍被写入 | 1/6 | **0/6** | 宿主写入规则，不是模型叙事幻觉率 |
| 人格配置 hash 稳定 | 2/2 | **2/2** | 配置稳定，不是模型人格行为评分 |
| 缺少能力的案例 | 6 | **0** | 不支持计失败，不隐藏跳过 |
| 执行异常 | 0 | **0** | 分母保持完整 |

最终本地 context+snapshot+typed request+prompt 构造耗时中位数 **3.95 ms**、P95 **9.65 ms**，38 个样本；基线约 **1.06 ms / 1.48 ms**。本批确实多做了本地事务、来源检查并发送原先遗漏的记忆，不应把这两组工作量不同的结果用作“性能提升”。也不包含模型推理、网络、UI 绘制、ASR/TTS、Windows 常驻负载。

粗略 prompt token 估算中位数从 **1078** 到 **1593.5**，最终最大 **1710**；算法是 `ceil(UTF-8字节数/4)`，不是 provider tokenizer 或真实 usage。模型人格行为、虚构经历回答率、真实响应时间与实收 token 明确为 **not_run**。

完整数据：[before](evidence/memory-benchmark-before.json)、[after](evidence/memory-benchmark-after.json)。它们使用相同 dataset SHA-256 `76fabb6dc77f8a034c746fe5c25c76c1d87f8f7cf7fad635ad7220ab9bf72de2`，相同 runner SHA-256 `ed9c6b00f5a1110cc82a8035fa4e643a1f83ecc48cb425113782f907846da6f7`。最终被测 `src/*.py` 合并哈希为 `e4c06867aa6f2688c3bcd9141f7ae954feaf47bfe83d7641bca9e1488b9a25a7`。

after JSON 中 `git_revision` 是测试当时尚未提交的 HEAD（基线），**不表示测试的是原代码**；被测仓库路径、实际导入模块和 source tree hash 记录了修改后工作树。交付提交的生产源码与该 source tree hash 一致，随包 manifest 提供对应关系。基线 archive 的 revision 则明确标为没有 git 元数据。

## 4. 实际 Bad Cases 与修复

1. **检索有结果、模型收不到。** 旧 V2 注入 context 后在 typed request 丢失，service recall 的满分掩盖了最终 prompt 的 0/11；本批同时检查两个边界。
2. **删除原条目、章节/画像仍提旧事实。** 来源指纹与撤回传播使派生物先失去资格，不等摘要重写成功才清理。
3. **事实已到期、旧聊天仍带回原句。** 最初37例通过后新增 `expired_fact_with_history`，观察到“青藤城”旧聊天绕回；到期 now 推进一次屏障，并加入最终38例重新对照。
4. **旧对象或新 ID 重放已遗忘事件。** 单条/批量底层写入统一检查来源与退役记录，不能只靠 UI 调一次 delete。
5. **权威数据库丢失后自动导回旧 JSON。** 缺表、缺行、缺文件、预置空库均作故障；receipt 保留初始化证据。DB 与 receipt 同时丢失及过时整目录备份另有明确恢复边界。
6. **新 owner 目录隔离让旧用户历史不可见。** 首次迁移按 owner 筛回旧共享目录；第17个跨 owner 章节来源也不能借显示上限隐藏。
7. **界面显示改了称呼，模型却读不到。** 原称呼/旧 keyed API 接入 V2，LLM 设置替换保持实际角色 profile，独立确认与过期重放分开处理。
8. **取消后晚到音频继续播放。** 任务取消事件、provider generation 和 UI 角色/epoch 检查共同封住队列与合成返回路径。

这些包括固定基线缺陷和本轮集成过程发现的回归，原始来源与分类见 [source-audit.md](source-audit.md)、[memory-core-review.md](memory-core-review.md)。不能把所有中间实现问题都归因于原项目。

## 5. 实际运行检查及明确未验证部分

**实际执行过**：本地 Python 单元/集成测试、临时存档迁移/重启/故障注入、角色切换、真实 controller→typed request→prompt 链路、受控 fake LLM 回调、线程队列取消、Qt 窗口离屏构建及中文截图。`tools/render_memory_album_smoke.py` 可复现 [回忆册截图](evidence/memory-album-smoke.png)，加载了验收环境临时 Noto 中文字体，不改动角色资源。

**没有执行**：真实 LLM 回答或长期人格盲评、真实 embedding 质量、Windows 桌面/安装器/长时常驻、真实 ASR/TTS/麦克风/扬声器、真实用户屏幕与摄像头、Relay/游戏/Body 联调、断电压力、物理全副本擦除。外部项目做了源码/文档/issue 核验，没有在本机部署它们的完整服务来复现其宣传分数。

固定配置 hash、38 条开发契约和有限 fake provider 回归都不能证明自然用户场景“100%正确”或“零泄露”。下一阶段真实模型与独立 holdout 设计见 [benchmark-spec.md](benchmark-spec.md) 和 [product-roadmap.md](product-roadmap.md)。
