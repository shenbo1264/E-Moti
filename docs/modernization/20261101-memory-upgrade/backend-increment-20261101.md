# Windows 后端增量与 Claude 接入

本次从已合并的 main `238f361c856584c7f93cc15dca5cbf5a387393e8` 建立独立目录 `E:/E-Moti/.worktrees/memory-generalization`，分支 `codex/memory-generalization`。接手时没有开放 PR，原有 Codex、Claude 工作目录保持原样。用户提供的累计开发包已通过适用性检查并导入为本地提交 `2f3978f`；本页描述其后的增量，不把包内已有实现算成本次新增。没有推送或发布。

## 生命周期和来源

- `remember(..., occurred_at=...)` 分开发生与记录时间。构造 `EmotionalMemoryService(time_basis="unix", timezone_name="Asia/Shanghai")` 只适用于明确使用 Unix 的新档案。重启省略参数时读取已保存基准；缺少标记的旧档案保持 logical，不猜日期。
- `correct(id, title, summary, now, ...)` 表示原事实错误，旧来源退役。`change(id, title, summary, now, effective_at, ...)` 表示现实变化，关闭旧有效区间并保留合法历史。未来变化应保留为计划，不能记为已经发生。
- `forget(id, now, expected_epoch=...)` 撤销整条修订链，历史查询也不能恢复。`purge(...)` 从当前权威内容及派生层移除整条链的正文，保留不含正文的 ID、版本和来源摘要墓碑防重放。该接口不承诺擦除 SQLite 旧页或用户备份。
- `expand_sources({id: fingerprint}, expected_epoch, now, scope)` 仍返回已验证卡片，并增加 `bundle.source_spans` / prompt `source_spans`：`memory_id, memory_fingerprint, version, source_id, source_fingerprint, start, end, text, scope`。只有认证 claim 的连续片段可显示为原话。旧存档缺少 span 或与已撤销片段重叠时，`retrieval.source_span_status` 和 `unavailable_sources` 给出原因；不能回退显示整段 `original_quote`。
- L1、关系进展和预算裁剪后的经历计数共同使用 `event_id/run_id`，缺少事件 ID 才使用来源关联。执行者报告完成还需要用户验收，不能凭参与者字段增加共同经历。

原有唯一事实权威仍为同 SQLite 内的 JSON。画像、章节、FTS、向量及模型判据均为派生信息，没有新增长期事实库。对现有真实存档未执行修改或迁移；测试使用独立目录。

## 桌面与 Host

Host 通过同一 controller 的 `DesktopDialogueService` 完成提取、提交、检索、生成和发布。工作线程执行网络请求，Qt owner 线程处理提交与结果。不要在网络回调另建同角色存储权威。

Host 结果新增 `input_version`、`committed_version`，继续包含 `request_id`、`context_epoch` 和 `revision`。请求运行中 `committed_version` 为 null；该请求合法更正造成版本增长时，成功结果返回更新后的版本。客户端先处理撤销事件清除旧卡片/音频/缓存，再按同一 `request_id` 接受自身成功提交；不能仅因 `input_version != committed_version` 把成功判为过期。其他请求及外部更正仍受撤销屏障约束。取消表示停止接收与发布，不虚称已中断远程 provider 的计算。

Claude 继续负责现有桌面页面和状态文案。`unknown`、`insufficient`、`unavailable` 分别表示缺少可靠证据、证据不完整、当前请求不可使用，不能统一写成“你从没说过”。新增 change/purge 是核心服务接口，现有 Host 路由尚不自动开放这两个操作；界面接入需要使用同一身份与版本约束。

## 查询理解与证据判断

旧第二集 48 问的逐题诊断保留在交付证据中：33 道有证据题有 26 道严格失败。重叠分类为路由错误 21、候选已召回但字面规则拒绝 14、gold 未进入候选决策 10、主体解析问题 3、时间/来源门拒绝 1。分类用于定位，不能把“字段未解析”解释为事实不存在。

`check_eligibility` 集中处理身份、范围、可信时间、撤销、计划/完成、共同经历与执行版本约束。`check_evidence` 继续负责明确字段与字面支持。可选 `MemoryEvidenceJudge(client)` 在工作线程对至多 8 个候选做一次模型判断，输出来源 ID 和逐字片段；宿主重新检查有效性和指纹。结果只绑定本轮问题、用户历史、已解析时间、索引版本与 epoch，不保存新事实，不把向量分数当事实概率。

评测可通过 `--evidence-settings` 显式启用；真实模型日志保存完整请求和原始返回。生产默认是否接入必须依据新的独立质量结果，本页不以协议测试通过宣称通用语义理解已完成。

## 存储与运行

性能依据见 [Windows 实测](storage-performance-windows.md)。本次减少更正/遗忘的重复全量规范化，保留未修改原始行和未知扩展字段；更正目标按主键读取，管理入口仍可编辑尚未生效或到期记录。暂不迁移成行式权威：万条更正仍约 2.9 秒，原 JSON 写入成本仍存在。

性能工具使用可选依赖 `pip install -e ".[performance]"`。Windows IANA 时区数据使用 Python 官方维护的 `tzdata`，按 [ZoneInfo 官方说明](https://docs.python.org/3/library/zoneinfo.html#data-sources) 声明 Windows 依赖。运行工具显式设置 `PYTHONUTF8=1`、`PYTHONPATH=src`，避免本机旧 editable 安装被误加载。

开发包语料 hash 使用原始 LF 字节。Windows `core.autocrlf=true` 曾只改变换行导致冻结校验失败；已与包内原始字节逐项比较并恢复，没有更改问题、gold 或 manifest。前后摘要与失败记录独立保留。

## 评测状态

13 套评测、28 项指标的原计划继续保留，不把计划数量计为已运行。旧两份独立集均为回归集。第三批由独立作者生成并封存，开发阶段不查看题目；首次评分、后续修复回归必须分开记录。

目前已完成的 6 问 Flash 开发诊断包含 4 道有据题，严格交付 3/4；保留中文日期漏解析导致的错误历史引用，以及一次 1024 token 推理耗尽的空返回。后续采用 4096 token，与实际项目客户端预算一致。该诊断未启用 BGE，不能据此声称最终综合质量提升。最终完整结果和真实回答评审另列；未运行的设备、纵向陪伴和外部执行任务继续标记 `not_run`。
