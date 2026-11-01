# 遗忘后不追问索回

2026-10-31。保留此前教师姓名、每周安排及表达修复的全部未提交改动，未推送。本批生产修改只在 `companion_dialogue_policy.py` 和 `expression_refinement.py`，不修改存储或角色配置。

## 原因与处理

遗忘后原内容和相关历史已从模型输入移除，但模型会把“当前不知道”接成“你再告诉我”。无需把已删除信息或话题重新放进 prompt 来判断是否可追问：对于没有有效答案的个人事实回忆问题，默认简短回答目前不知道，不反问答案、不邀请重新登记，不解释为什么不能猜。用户主动要求共同规划或重新登记时，保留完成任务必要的澄清。

前两次规则收紧已停止索回，但模型仍换说法重复“不知道”，或把当前没有内容说成“过去没存过”。最终规则只对无答案的个人回忆问题要求一个短分句、最多 16 个汉字，不复述问题；具体口气由角色决定，其他对话不受这项短答限制。无新增模型调用、没有截断或替换实际输出的后处理。

## 基线与中间问题

使用应用实际 `deepseek-flash` 配置，通过生产 DesktopDialogueService 执行，数据均为独立合成存档。完整请求、草稿、修订输出、最终回答、持久事实、epoch、token 和延迟均保留。

- `schedule-before.json` 真实复现遗忘后“你告诉我是周几，我就能记住这一条”，重启后又问“你每周几去游泳来着”。
- `teacher-before.json` 本轮已简短表示不知道，不能算本次新增改善。
- `*-after.json` 已无索回，但出现“脑子里一片空白”重复解释，以及未知事实控制中“没存过”的无依据过去断言。
- `*-final.json` 修正过去断言，但教师即时遗忘后仍说“没印象……真的答不上来”，游泳重启仍说“不知道……记忆里还没有”。这两条属于本次简洁性失败，文件没有覆盖。
- `controls-before.json` 的明确规划场景出现 `provider_error`，没有合格最终模型回答，不能作为澄清语气的有效基线；失败保留，失败调用的未知计费不包含在成功调用统计中。

所有重启召回步骤均先调用生产 `clear_dialogue_history()`，关闭并重新创建控制器；请求前 recent_dialogue 为空。自然遗忘本身走现有本地命令，真实模型验证发生在后续即时与重启查询，不能把本地遗忘计作模型调用。

## 最终 accepted 结果

| 遗忘后的查询 | 最终回答 |
| --- | --- |
| 教师姓名，即时 | 这个我还不知道。 |
| 教师姓名，清空历史重启 | 唔，这个我还不知道呢。 |
| 游泳安排，即时 | 这个我还不知道呢。 |
| 游泳安排，清空历史重启 | 唔，这个我还不知道。 |

4 次均没有索回追问、邀请补录、重复解释或“从未保存”的断言。教师更正 saved 为江屿，空历史重启请求仅含江屿、不含林澈；游泳改期 saved 为每周日，空历史重启请求仅含周日、不含周六。两条链路遗忘后即时与重启请求均不含旧新值，存储只保留独立的用户姓名许安。未发生存储、召回或遗忘退化。

3 个控制场景全部 completed：未知个人事实简短不知道；明确规划回答“行，下周哪几天有空？报给我，我再跟你一起排”；拟人玩笑回应橡皮度假带回沙子、海风。必要澄清与角色玩笑没有被短答规则误禁。

## 实际调用与耗时

| 记录 | 成功调用 | 实际 token | API 总耗时 ms |
| --- | ---: | ---: | ---: |
| teacher-before | 9 | 20,224 | 18,716 |
| teacher-after | 9 | 21,364 | 27,523 |
| teacher-final，中间残留 | 9 | 22,574 | 27,455 |
| [teacher-accepted.json](teacher-accepted.json) | 9 | 21,223 | 17,807 |
| schedule-before | 8 | 19,340 | 21,762 |
| schedule-after | 8 | 19,767 | 21,041 |
| schedule-final，中间残留 | 8 | 20,419 | 19,253 |
| [schedule-accepted.json](schedule-accepted.json) | 8 | 20,186 | 13,175 |
| controls-before，另有一次失败 | 6 | 10,536 | 12,173 |
| controls-after | 8 | 16,982 | 23,535 |
| controls-final | 8 | 17,873 | 23,269 |
| [controls-accepted.json](controls-accepted.json) | 8 | 16,483 | 12,027 |

accepted 没有 fallback 或格式失败。所有中间文件保留；不是选取一次输出覆盖失败历史。本结果只证明这些真实场景，不宣称长期绝对稳定。

## 本地回归

修改前及最终短答文案补充后，表达修订、桌面表达流程、教师更正和每周安排相关 **29 项通过**。完整回归在第一版规则后启动，后续两次文案补充分别通过相关测试，并由 accepted 真实请求验证，没有重复运行整套无关测试。

[full-pytest.log](full-pytest.log)：**1693 passed / 2 failed / 5 skipped / 3 warnings**，683.16 秒。不能称全量全绿。两项失败：

- `test_window_secondary_controls_do_not_wait_for_slow_llm_expression`：主动反馈耗时 0.125 秒，超过 0.1 秒断言。
- `test_portrait_pack_smoke_reports_idle_motion_sequence`：取得的帧顺序从第二帧开始，与预期第一帧开始不同。

两项均在原代码、原断言下单独复查通过：**2 passed，1.81 秒**，见 [timing-recheck.log](timing-recheck.log)。没有放宽阈值、修改动画或界面代码；全量环境下出现的计时/帧序波动原因未进一步定位，本批保留为验证限制。此前 38 条开发记忆契约保持有效，本批没有改记忆实现；不以它们替代本次真实链路验证。`git diff --check` 通过。

## 复现

```powershell
$env:PYTHONUTF8='1'
$env:QT_QPA_PLATFORM='offscreen'
python tools/teacher_correction_flash_eval.py --output artifacts/codex_handoff/forget-followup/teacher-replay.json
python tools/schedule_correction_flash_eval.py --output artifacts/codex_handoff/forget-followup/schedule-replay.json
python tools/companion_flash_eval.py --dataset docs/modernization/evidence/forget-followup-20261031/controls.json --output artifacts/codex_handoff/forget-followup/controls-replay.json
```

新增控制样本在修改前冻结：未知个人事实不追问，明确请求规划可问空闲日期，拟人玩笑仍正常回应。评审为知情独立 AI 复核，不是人工盲评，详见 [review.md](review.md)。
