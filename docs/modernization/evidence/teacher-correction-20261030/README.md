# 教师姓名更正、重启召回与遗忘

基线 `1f681e4`，本批修改 `chat_memory_extraction.py`。没有推送，也没有修改真实用户存档。

## 问题与修复

原流程没有将“写错”识别为纠正；教师姓名被模型归为 `scene=other` 时被忽略。若直接放行姓名提议，原姓名模板又会将老师姓名写成用户姓名。

现在只对已有授权的教师事实进行关系绑定的更正：新原话和目标必须保留同一“我的某某老师”主语，姓名值必须来自原话。教师姓名有独立字段，不能替换用户姓名或其他老师。兼容模型返回 name/legal_name 分类，自动模式直接保存，审核模式仍待确认。继续使用现有来源校验、correct、epoch、索引和历史失效机制，不新增长期事实库或迁移。

## 真实 V4.1 Flash 结果

通过应用当前 `deepseek-flash` 配置及生产 DesktopDialogueService 执行，完整模型请求、回答、token、耗时、存储事实和上下文见三个 JSON。所有数据为独立合成存档。更正后主动调用生产 `clear_dialogue_history()`，关闭并重新创建控制器；重启请求的 recent_dialogue 为空，不依赖聊天历史回答。

| 场景 | 修复前 | 修复后 |
| --- | --- | --- |
| 吉他老师林澈→江屿 | 回答已记下，但 memory_result=ignored，存储仍为林澈 | saved，持久事实为“用户的吉他老师叫江屿” |
| 清空历史并重启 | 回答林澈，实际请求含林澈、不含江屿 | 回答江屿，实际请求含江屿、不含林澈 |
| 自然遗忘后即时查询 | 不知道姓名 | 不知道姓名，实际请求不含新旧名 |
| 遗忘后清空历史并重启 | 不知道姓名 | 不知道姓名，实际请求不含新旧名 |

独立样本“钢琴老师周远→顾宁”也完成保存、空历史重启召回顾宁，以及遗忘后的即时和重启不泄露。两组修复后存档均保留用户姓名许安，没有把老师姓名写成用户姓名。

自然遗忘走既有本地命令处理，该步骤没有调用模型；真实模型检查发生在遗忘后的两次查询。修复后更正回答为“江屿，唔，我记下了。许安。”，末尾称呼较突兀，保留原始输出，不据此宣称人格全面达标。

| 记录 | 真实调用 | 实际总 token | API 总耗时 |
| --- | ---: | ---: | ---: |
| [before.json](before.json) | 9 | 19,016 | 27,007 ms |
| [after.json](after.json) | 9 | 17,302 | 19,056 ms |
| [independent.json](independent.json) | 9 | 18,424 | 25,009 ms |

after/independent 的真实验证进程在最终“老师目标不能反向变成用户姓名”保护加入前已启动；这条保护不改变这两组正确关系请求。该反向错误另有先失败后通过的持久存储测试覆盖。

## 复现

```powershell
$env:PYTHONUTF8='1'
$env:QT_QPA_PLATFORM='offscreen'
python tools/teacher_correction_flash_eval.py --output artifacts/codex_handoff/teacher-correction/replay.json
python tools/teacher_correction_flash_eval.py --independent --output artifacts/codex_handoff/teacher-correction/replay-independent.json
```

工具要求应用已配置 deepseek-flash；不读取环境变量中的其他模型凭据，不输出密钥。每次创建独立存档，真实请求和数据保留供检查。旧的已失败用户更正不会从历史自动重放，需要重新明确更正。

## 本地验证

新增测试先复现 6 项失败，再验证 auto/review、personal/other、name/teacher_name、无历史重启召回、错误人物目标拒绝、遗忘和身份保留。相关测试合计 31 passed。38 条开发记忆契约另行通过；这些是本地契约，不算真实模型效果证据。

完整回归：1688 passed / 5 skipped / 3 warnings，299.22 秒，见 [full-pytest.log](full-pytest.log)。警告为既有 websockets 弃用和端口占用用例中的 uvicorn 线程退出。38 条契约结果见 [memory-contracts.json](memory-contracts.json)。`git diff --check` 通过。
