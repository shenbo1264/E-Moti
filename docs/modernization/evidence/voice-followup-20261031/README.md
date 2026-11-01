# 自然称呼、责任归因与建议边界

2026-10-31，基于 `1f681e4` 和上一轮尚未提交的教师姓名修复继续修改。未推送，未修改用户存档。生产改动只在 `companion_dialogue_policy.py` 和 `expression_refinement.py`，保留原角色配置、记忆实现及最多两次模型调用。

## 修改

- 普通分享、纠正和吐槽不拿用户姓名作开头或结尾装饰；明确要求称呼、询问姓名和区分人物仍准确使用名字，老师和宠物名字作为内容保留。
- 自责须有当时证据和具体 assistant 错句。用户改字、更新现实安排不转移成角色责任。
- 没有求助时检查软语气建议，如“别急、慢慢来、下次试试、要不要”；明确求助保留完整帮助，保留角色的个人看法、拟人和玩笑。
- 修订只改具体问题；删推断不能再补感官亲历。记忆缺失只能说不知道，不能推断用户从未告诉过角色。

## 真实 V4.1 Flash

使用应用实际 `deepseek-flash` 凭据，保存每次请求、原始草稿、修订、最终回答、usage 和延迟，无密钥。8 个新场景在修改前冻结，包括多轮分享、用户改错字、现实改期、吐槽、主动求助、主动叫名和玩笑。三组均 8 completed，无格式 fallback。

| 记录 | API 调用 | 实际 token | API 耗时 |
| --- | ---: | ---: | ---: |
| [before.json](before.json) | 31 | 58,554 | 82,331 ms |
| [after.json](after.json)，中间版 | 31 | 63,474 | 86,675 ms |
| [final.json](final.json) | 31 | 62,265 | 75,536 ms |

新样本基线已经基本避免三类目标问题，因此不能声称这 8 例证明了显著改善。最终 8 例也未发现三类目标问题；明确叫名仍回答“许安，晚安”，明确求助仍给出感谢话，分享和玩笑仍有角色自己的比喻。另一代理的知情 AI 评审见 [review.md](review.md)，不是人工或盲评。

为隔离规则作用，另用三条真实历史问题回答和相同上下文做旧新规则回放，[replay.json](replay.json) 保存来源与原请求：

| 真实问题 | 旧规则 | 新规则 |
| --- | --- | --- |
| “江屿，唔，我记下了。许安。” | 原样保留突兀许安 | “江屿，唔，我记下了。” |
| “那宁波就当是我随口猜错了” | 删除自责 | 同样删除自责；不算新增改善 |
| “要不先歇一歇，缓过来再打” | 删除建议，另加追问 | 删除建议，停在“那局输得挺惨啊。” |

回放旧/新各 3 次调用，分别 7,818 / 7,426 tokens，19,644 / 13,190 ms。这是实际模型的受控编辑实验，不是新增完整对话验收；多余建议的旧来源没有结构化审阅输入，因此使用完整原生成请求，不补造上下文。

## 教师记忆回归

最终 [teacher-accepted.json](teacher-accepted.json) 通过生产服务完成：

1. 更正 saved，持久保存“用户的吉他老师叫江屿”，用户本人许安保持独立。
2. 主动清空聊天历史，关闭并重新创建控制器；recent_dialogue 为空，实际模型请求含江屿、不含林澈，回答“江屿。这个我记着呢。”
3. 自然遗忘 forgotten；即时和再次清空历史重启后的真实请求均不含新旧姓名，均回答不知道，用户许安仍在存档。

遗忘由既有本地命令执行，该步骤不计模型调用。实际模型检查位于其后的查询。前两轮教师记录也保留为 teacher-regression.json / teacher-final.json，没有覆盖失败证据。

teacher-accepted 共 9 次真实调用、18,693 tokens、API 总耗时 17,364 ms。

## 中间失败与未解决事项

- after 首例删去生长时长猜测，却新增“看到了”。补充最小修订和最终事实核对后，final 改成“圆滚滚的小芽，像仙人球偷偷冒了个小气泡”。
- teacher-final 遗忘后新增“你还没跟我提过这件事”。补充空记忆不能证明从未说过后，teacher-accepted 只说不知道。
- final 感谢代写里新增了用户没有给出的“今天”。保留为事实细节 partial；不能宣称所有生成都完全有据。
- final 游泳改期回答“我记着周日”，实际 memory_result=ignored、存储仍周六。基线和中间版也存在这个非教师计划领域的持久化缺口。本批未修，不算记忆通过。

final 8 例和 replay 的进程早于最后“空记忆不等于从未说过”规则补充启动；该边界以最新 teacher-accepted 实测，其他既有结果按当时原请求保留。整个评测是有限合成样本，不代表长期绝对稳定。

## 复现

```powershell
$env:PYTHONUTF8='1'
$env:QT_QPA_PLATFORM='offscreen'
python tools/companion_flash_eval.py --dataset docs/modernization/evidence/voice-followup-20261031/cases.json --output artifacts/codex_handoff/voice-followup-20261031/replay-dialogues.json
python tools/voice_refinement_replay.py --baseline 1f681e4 --output artifacts/codex_handoff/voice-followup-20261031/replay-editing.json
python tools/teacher_correction_flash_eval.py --output artifacts/codex_handoff/voice-followup-20261031/replay-teacher.json
```

修改前相关测试 22 passed；最终规则补充后相关测试再次 22 passed。完整回归 1688 passed / 5 skipped / 3 项既有警告，298.89 秒，见 [full-pytest.log](full-pytest.log)。完整回归在最小修订和空记忆两条文案补充前启动；两条后续文案由相关测试与真实模型复查覆盖，没有再次重复全套测试。38 条记忆契约沿用上轮有效记录，本批没有更改记忆实现。`git diff --check`、新增回放工具编译通过。
