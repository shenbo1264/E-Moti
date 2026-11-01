# 每周安排改期与感谢代写

2026-10-31。在 `codex/desktop-acceptance` 上保留此前未提交的教师姓名及语气修复，继续修改。未推送，未修改真实用户存档。

## 实现

`chat_memory.py` 沿用既有受控自述解析，识别“我每周六去游泳”和“我以后改成周日去游泳了”。按活动独立记录每周安排，只有同一活动存在唯一的已授权每周事实时，才继承重复频率并改期；没有原安排时请求澄清，不把单个周日猜成每周日。周日/周天和周/星期作规范化处理。普通冲突继续待确认，auto/review/off 保持原设置边界。

旧明确记忆通过现有 `_fact_view` 参与匹配，无须扫描历史、修改旧存档格式或批量迁移。写入复用 remember/supersedes、来源与 epoch 机制；旧时间、派生内容和历史沿原路径失效。新增按活动理解“忘记我的游泳安排/时间”，不影响跑步等其他活动。

感谢代写的生成和一次修订规则明确：不能补没有给出的时间、日期、地点、受益结果或扩大完成范围；用户已给出的“今天”保留。改期回答只接住有据的新时间，不猜新旧日期的提前、推迟或工作日/周末关系。没有新增调用、人格配置或 UI 修改。

## 真实 V4.1 Flash 结果

使用应用配置的 `deepseek-flash` 和生产 DesktopDialogueService，所有数据为独立合成存档，原始请求、草稿、最终回答、存储、epoch、token 和延迟均保留，不记录密钥。

| 验证 | 修复前 | 最终结果 |
| --- | --- | --- |
| 游泳周六→周日 | ignored，却回答“记下了”；存储仍周六 | saved，存储“用户每周日去游泳”；回答“周日去游泳，记下啦。” |
| 清空历史并重启 | 仍答周六 | history=0，实际请求含周日、不含周六；答周日 |
| 忘记游泳安排 | clarify，旧安排仍在 | forgotten；即时和再次重启请求均不含新旧日程，模型不知道日程 |
| 感谢代写未给时间 | 上轮实际失败加“今天”和“省了我不少事”；本轮 baseline 未复现今天 | “搬书这事多亏你帮忙，真的谢谢。” |
| 明确提供今天 | 应保留时间 | “谢谢你今天帮我搬书。” |

独立场景通过普通聊天保存每周三跑步，再改为周五；空历史重启正确答周五，遗忘后不再答出日程。主例证明旧明确记忆可更正，独立例证明普通自述也可保存和更正。

教师回归再次通过：林澈→江屿保存成功，清空历史重启后请求仅含新名、正确答江屿；自然遗忘后即时和重启的请求均无新旧名，模型不再答出姓名。用户姓名许安始终保留，未被老师名字覆盖。

## 计量与原始证据

| 文件 | 调用 | 实际 token | API 总耗时 ms |
| --- | ---: | ---: | ---: |
| [schedule-before.json](schedule-before.json) | 10 | 22,579 | 31,170 |
| [schedule-after.json](schedule-after.json)，中间版 | 8 | 18,920 | 20,501 |
| [schedule-final.json](schedule-final.json) | 8 | 20,469 | 28,646 |
| [schedule-independent.json](schedule-independent.json) | 10 | 25,214 | 32,905 |
| [teacher-regression.json](teacher-regression.json) | 9 | 19,398 | 17,681 |
| [thanks-before.json](thanks-before.json) | 5 | 12,003 | 21,189 |
| [thanks-after.json](thanks-after.json)，中间版 | 5 | 11,902 | 18,206 |
| [thanks-final.json](thanks-final.json) | 5 | 11,307 | 11,914 |
| [thanks-replay.json](thanks-replay.json) | 2 | 4,772 | 11,160 |

确定性改期/遗忘不需要抽取模型；表内调用包括真实表达生成和修订。历史感谢失败回放给旧/新规则相同实际回答和上下文，本次两者均删掉“今天”和受益扩写，所以不声称旧规则必失败或统计显著提升。

## 失败记录与限制

- 中间版感谢虽不加今天，仍写“书都搬好啦”，扩大完成范围；补充数量与完成范围边界后，最终不再出现。
- 中间版游泳说“挪到周末”，但原周六也是周末；补充新旧时间关系的依据要求后，最终只确认周日。
- 遗忘后的最后查询偶尔追加“你平时是哪几天去呀”这类追问，原文保留；没有重新泄露或保存日程。本批不宣称长期人格质量全部达标。
- 教师和跑步复测在最后两条表达文案补充前启动，存储实现与最终版相同；最后文案由 schedule-final / thanks-final 覆盖，不重复无关模型调用。
- 当前直接支持明确的单日每周安排和同活动改期；不推断含糊的代词、多日课程或没有原频率的单次周日事件。

独立知情 AI 复核见 [review.md](review.md)，不是人工盲评。

## 验证与复现

新测试先复现 4 项改期失败，再复现 4 项自然遗忘失败；修复后相关 102 项通过，最终表达文案补充后相关 29 项通过。最终代码完整回归 **1695 passed / 5 skipped / 3 项既有警告**，297.23 秒，见 [full-pytest.log](full-pytest.log)。38 条开发记忆契约通过，见 [memory-contracts.json](memory-contracts.json)；它们是本地契约，不替代上面的真实模型验收。`git diff --check` 和新增工具编译通过。

```powershell
$env:PYTHONUTF8='1'
$env:QT_QPA_PLATFORM='offscreen'
python tools/schedule_correction_flash_eval.py --output artifacts/codex_handoff/schedule-thanks/replay-schedule.json
python tools/schedule_correction_flash_eval.py --independent --output artifacts/codex_handoff/schedule-thanks/replay-independent.json
python tools/companion_flash_eval.py --dataset docs/modernization/evidence/schedule-thanks-20261031/thanks-cases.json --output artifacts/codex_handoff/schedule-thanks/replay-thanks.json
python tools/teacher_correction_flash_eval.py --output artifacts/codex_handoff/schedule-thanks/replay-teacher.json
```
