# Claude / Codex 共享文件单写者约定（2026-11-01）

Claude 工作树：`.worktrees/claude-memory-experience`，分支 `claude/memory-experience`。
起点：Codex 已提交的 `2f3978f`，加一个本地快照提交 `snapshot: Codex backend WIP`。
快照只是 `.worktrees/memory-generalization` 当时未提交的 `src/`、`tools/`、`tests/*.py` 只读副本，用于对真实接口开发和测试，
不代表 Codex 已交付。Codex 提交后，快照提交应被丢弃，Claude 的提交 rebase 到 Codex 的最终提交上。Codex 的工作树没有被改动。

| 文件 | 单写者 | 说明 |
|---|---|---|
| `memory_ledger_view_model.py`、`memory_evidence_view_model.py`、`memory_edit_session.py`（新） | Claude | 分类、时间标签、证据状态文案、编辑草稿状态机 |
| `memory_album_qt.py`、`memory_album_view_model.py`、`memory_settings_qt.py`、`memory_settings_view_model.py` | Claude | 回忆册页面 |
| `memory_album_controller.py` | Claude | Codex 的 `source_expansion`、`_now` 两处改动已原样保留。Claude 只新增方法；Codex 再改时先告知 |
| `app.py`、`ui_*`、`DESIGN.md` | Claude | 聊天回执与设置入口 |
| `proactive_companion.py`、`companion_moments.py` | Claude | 主动陪伴策略与台词 |
| `dialogue_policy` 的人格、证据表达规则 | Claude | 只改文案规则，不改 ExpressionRequest 结构 |
| `assets/companion/xingxi_pixel_pet/persona.json`（新） | Claude | 作者配置，不从聊天写入 |
| `tools/persona_behavior_eval.py`、`docs/modernization/persona-behavior/`（新） | Claude | 人格行为评测 |
| `controller.py`、`plugin_enabled_controller.py` | Codex | Claude 只改三处调用点，见下 |
| `emotional_memory*.py`、`memory_lifecycle.py`、`memory_index.py`、`memory_source_spans.py`、`memory_time.py`、`retrieval_*`、`ondemand_memory.py`、`memory_evidence_judgment.py`、`memory_prompt_budget.py`、`semantic_memory.py`、`memory_hierarchy.py`、`host_*`、`desktop_dialogue_service.py` | Codex | Claude 不改 |
| `expression_request.py`、`expression_expressor.py`、`companion_story_runtime.py` | Codex | 需要改动时先约定 |

## Claude 对 Codex 文件的最小调用点改动

- `plugin_enabled_controller.py`：`MemoryAlbumController(self.story_runtime, clock=...)`，把宿主逻辑时钟传给回忆册，取代 Qt 层传入 `time.time()`。
- `controller.py` 构造 `ProactiveCompanionService` 处：传入 `wall_seconds`、`focus_active`。
- `controller.py` 的 `reject_proactive_request`：传入历史，实现连续拒绝退让。

这三处如与 Codex 冲突，以 Codex 的结构为准，由 Claude 重新接入。

## 需要 Codex 确认的接口事实

- `change()` 要求 `valid_from < effective_at <= now`，未来变化保持为计划。界面只提供“现在变了”，未开放填写未来日期。
- `purge()` 不承诺擦除 SQLite 旧页和用户备份，界面如实说明。
- `expand_sources` 展开的是当前记忆卡，不是完整聊天原文。`source_spans` 只在认证片段存在时显示为原话。
- Host 路由未开放 change/purge，本批只接桌面回忆册。
