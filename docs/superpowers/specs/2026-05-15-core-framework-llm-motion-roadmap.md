# 星汐核心框架、LLM 表达与桌宠交互路线 Spec

状态：稳定开发顺序 spec v0.1

最后核对日期：2026-05-15

## 1. 写作目的

本 spec 用来纠正下一阶段开发优先级：当前 demo 还没有完成核心框架、真实 LLM 表达 adapter、桌宠交互增强和 MotionLayer 能力，因此不应继续优先做 DemoMode / 演示导览。

本 spec 同时作为后续 agent 的项目管理锚点。任何后续开发都必须先检查本文件的阶段顺序和门禁，避免只盯住某一个亮点能力，例如只做联网搜索、只做桌宠拖拽、只做演示按钮，而忽视整体闭环。

## 2. 不可变边界

- 主角色是原创 OC 桌面电子宠物与伴侣“星汐”。
- “共同学习”“专注”“休息”只作为动作状态，不作为角色身份、学习监督或效率工具定位。
- 不复制 Miku、Vocaloid、VPet、Shinsekai、现有 Codex pet 或其他 IP。
- LLM 只能作为表达、感知摘要和工具结果解释层，不允许直接修改状态、动作结算、目标、背包、物品或存档。
- `STAT` / `CHOICE` 事件优先保持本地固定生成，避免模型编造状态和选项。
- 美术资产保持“候选 -> 可见 QA -> 正式替换 -> 重新验证 -> 人工 QA”边界。
- 不把 `轻触` / `共同学习` 发色偏白说成已解决；这是已知搁置风险。
- 不触碰 `AI不用看.md`。
- Markdown 文档必须写中文。

## 3. 总体开发顺序

下一阶段固定按以下顺序推进：

1. 框架拆层 + typed snapshot/events
2. 真实 LLM 表达 adapter
3. 桌宠模式交互增强
4. MotionLayer 的 ABC / idle 随机
5. DemoMode / 演示导览

除非用户明确批准，不允许跳过前置阶段直接实现后置阶段。后置阶段可以写设计草案，但不能进入主体实现。

## 4. 阶段一：框架拆层 + typed snapshot/events

### 4.1 目标

把当前较集中的 controller / snapshot / event dict 拆成更清晰的边界，让后续 LLM、桌宠窗口、MotionLayer 和 DemoMode 都依赖稳定接口，而不是直接读写松散字典。

### 4.2 建议拆层

- `CompanionStateEngine`：只负责状态数值、动作结算、tick、模式判定。
- `CompanionActionLayer`：只负责把 UI、点击、拖拽、快捷入口转成标准动作请求。
- `InventoryService` / `ShopService`：只负责物品、金币、购买、使用、赠礼。
- `RelationshipService`：只负责关系阶段、解锁、回忆写入规则。
- `ProactiveCompanionService`：只负责主动陪伴规则、冷却和触发原因。
- `SnapshotBuilder`：只负责从内部状态构建 typed snapshot。
- `EventBuilder` / `EventValidator`：只负责生成和校验 UI 可消费事件。
- `SaveManager`：只负责存档 schema、迁移、运行时路径和加载保存。

### 4.3 Typed snapshot 要求

typed snapshot 应至少覆盖：

- `character_id`
- `character_name`
- `mode`
- `stats`
- `inventory`
- `shop_items`
- `relationship_stage`
- `next_relationship_unlock`
- `unlocks`
- `memory_log`
- `current_motion`
- `feedback`
- `events`
- `proactive_feedback`

后续 UI、LLM adapter、MotionLayer、DemoMode 都只能依赖 typed snapshot 和 typed events，不直接猜测 controller 内部字段。

### 4.4 Typed events 要求

事件至少分为：

- `speech`：星汐台词。
- `stat`：本地生成的状态展示。
- `choice`：本地生成的可用动作入口。
- `motion`：动作切换请求。
- `memory`：回忆日志更新。
- `relationship`：关系阶段或解锁反馈。
- `inventory`：购买、使用、赠礼、物品图标反馈。
- `proactive`：主动陪伴触发原因。
- `system`：保存、加载、错误、降级提示。

每类事件都必须有固定字段和测试覆盖。任何 LLM 事件必须经过 validator 转成这些类型后才能进入 UI。

### 4.5 阶段一门禁

- controller 中不再新增新的裸 dict snapshot 字段。
- 现有测试迁移到 typed snapshot/events 后仍通过。
- 至少覆盖动作、背包、关系、主动陪伴、存档迁移和 UI snapshot 消费测试。
- `pytest` 必须通过。
- 未改 UI 时不需要声称 PySide visible smoke；改 UI 时必须重跑。

## 5. 阶段二：真实 LLM 表达 adapter

### 5.1 目标

在本地规则闭环稳定后，接入真实 LLM 作为“表达增强层”。LLM 可以让星汐的台词更自然，也可以解释受控的感知摘要和工具结果，但不接管核心状态机。

### 5.2 Adapter 边界

真实 LLM adapter 必须是可关闭、可 mock、可超时、可 fallback 的。

输入：

- typed snapshot 的只读摘要。
- 最近动作与本地结算结果。
- 最近少量 memory log。
- 可选的屏幕感知摘要。
- 可选的工具查询结果。

输出：

- 受限 JSON event 列表。
- 每轮最多 4 个事件。
- 只允许 `speech`、可选 `effect`、可选 `motion_hint`。
- 不允许输出状态变化、金币变化、背包变化、目标变化或存档写入。

### 5.3 Shinsekai 式感知与工具层

用户提到的 Shinsekai 式能力可以拆成三个受控层，而不是让 LLM 直接“看见一切并行动”：

1. 屏幕感知层：读取当前窗口标题、应用名、可选截图/OCR 摘要，生成短上下文。
2. 工具层：提供受控搜索、角色资料查询、本地文档检索等工具。
3. 表达层：LLM 根据 snapshot、感知摘要和工具结果生成星汐台词。

第一版必须从手动触发开始，例如“观察当前屏幕”按钮或开发者命令。默认不后台截图、不自动上传屏幕、不长期记录原始截图。

### 5.4 联网搜索能力边界

搜索不是 P0 的炫技入口，而是 LLM 表达 adapter 后的受控工具：

- 先实现工具接口和 mock search。
- 再接可配置真实搜索 provider。
- 搜索结果必须带来源、时间、摘要。
- 搜索内容只进入表达层，不进入状态结算层。
- 如果无网络、无 key、超时或结果为空，星汐必须自然降级到本地表达。

### 5.5 角色资料检索边界

角色资料检索优先读本地角色包、prompt、dialogue style、项目文档和可授权资料，不允许抓取或复制其他 IP 的设定来伪装成原创内容。

对星汐来说，资料检索的目的只能是保持原创角色表达一致，而不是拼贴现有角色。

### 5.6 阶段二门禁

- 无 API key 时 demo 完整可跑。
- mock LLM、真实 LLM 超时、非法 JSON、字段越界都有测试。
- LLM 不能改变任何状态结算结果，有回归测试证明。
- UI 不被网络请求阻塞。
- 屏幕感知默认关闭，手动触发，有隐私提示和可见状态。

## 6. 阶段三：桌宠模式交互增强

### 6.1 目标

让 `--desktop-mode` / `--pet-mode` 从形态证明变成可操作桌宠体验，但仍依赖阶段一的 typed action/snapshot，不绕过核心状态机。

### 6.2 优先能力

- 桌宠窗口拖动更稳定。
- 角色区域点击触发标准 `touch` 动作。
- 拖动释放触发标准 `raise` / `drag` 动作。
- 右键菜单提供返回控制面板、退出、可选重载角色包。
- 置顶、透明背景、窗口边界处理更稳。
- 桌宠模式仍能展示简短反馈和当前状态，而不是只显示图片。

### 6.3 暂不扩张

此阶段不优先做长期后台观察、复杂日程提醒、系统级自动化控制或完整 ASR。桌宠交互的核心是“可触摸、可拖动、可反馈、可回到主界面”。

### 6.4 阶段三门禁

- 控制面板和桌宠模式消费同一 typed snapshot。
- 桌宠模式动作进入同一 action layer。
- 5-10 分钟运行不出现窗口丢失、空帧、无法退出。
- 涉及 UI 必须重跑 PySide visible smoke。

## 7. 阶段四：MotionLayer 的 ABC / idle 随机

### 7.1 目标

把动作播放从“动作名到 atlas 行”的简单映射，升级为可表达 `A_Start / B_Loop / C_End / Single` 和 idle 随机的小型 MotionLayer。

### 7.2 能力范围

- 支持 `Single` 动作。
- 支持 `A_Start -> B_Loop -> C_End`。
- 支持 idle 随机变体，但必须可设随机种子，方便测试复现。
- 支持动作优先级，例如主动陪伴、状态下降、拖拽、投喂之间的抢占规则。
- 支持 fallback motion，缺资源时不空帧。
- 支持从 `motion_manifest.json` 读取动作段配置。

### 7.3 美术边界

MotionLayer 可以先用现有 atlas 和 manifest 做逻辑能力，不要求同时更换 spritesheet。任何正式资源替换必须继续走候选、可见 QA、正式替换、重新验证、人工 QA。

### 7.4 阶段四门禁

- idle 随机有确定性测试。
- ABC 段切换有单元测试。
- 缺失 motion 会 fallback，不会空白。
- 没改 spritesheet / preview 时，不得声称跑过 atlas/preview 验证。
- 如改动画显示 UI，必须重跑 PySide visible smoke。

## 8. 阶段五：DemoMode / 演示导览

### 8.1 目标

只有当前四个阶段稳定后，才回到 DemoMode。DemoMode 的目标是可复现演示，不是替代真实框架。

### 8.2 能力范围

- 演示存档隔离。
- 一键 reset / seed。
- 3-5 分钟演示路径。
- 演示导览短步骤。
- 不污染正式陪伴存档。

### 8.3 推荐演示路径

1. 轻触。
2. 共同学习，口径限定为共同进入专注状态。
3. 购买热牛奶。
4. 投喂。
5. 主动陪伴演示触发。
6. 拖拽 / 提起。
7. 桌宠模式收尾。

### 8.4 阶段五门禁

- 连续运行两次 demo，初始状态一致。
- 演示流程不污染正式存档。
- 演示按钮不成为核心功能的替代实现。
- `pytest` 必须通过。
- 涉及 UI 必须重跑 PySide visible smoke。

## 9. 防偏航项目管理规则

每个后续开发对话开始时，agent 必须先做五件事：

1. 核对 `git status --short --untracked-files=all`。
2. 核对最近提交和当前分支。
3. 读本 spec。
4. 明确当前处于哪个阶段。
5. 只选择当前阶段内的 1 个可验证小切片。

每个开发切片必须遵守：

- 先写失败测试，再做最小实现。
- 不跨阶段顺手加功能。
- 不为了展示效果绕过 typed snapshot/events。
- 不把 LLM、感知、搜索、TTS、DemoMode 混成一个大改动。
- 每个切片结束要记录验证命令和结果。

如果发现用户提出的新需求跨阶段，agent 应先说明它属于哪个阶段，再给出两种处理方式：

- 当前阶段只留接口或测试锚点。
- 等前置阶段门禁完成后再实现。

## 10. 当前下一步建议

下一轮优先执行阶段一的第一个切片：

**切片名称：typed events/snapshot 基础类型落地。**

建议范围：

- 新增 typed event 和 typed snapshot 数据结构。
- 让 controller 的现有 snapshot 先通过 builder 产出兼容 dict，避免一次性改爆 UI。
- 先迁移测试到稳定字段。
- 不接真实 LLM。
- 不改 spritesheet。
- 不做 DemoMode。

验收：

- 现有行为不变。
- typed snapshot/events 有单元测试。
- controller 不再新增新的裸 dict 拼装。
- `pytest` 通过。

## 11. 后续阶段状态表

| 阶段 | 状态 | 可以做 | 不可以做 |
|---|---|---|---|
| 1. 框架拆层 + typed snapshot/events | 下一步 | 类型、builder、validator、service 边界 | 真实 LLM、DemoMode 主体 |
| 2. 真实 LLM 表达 adapter | 等阶段一门禁 | LLM adapter、mock、timeout、fallback、手动感知摘要、工具接口 | LLM 改状态、自动后台截图 |
| 3. 桌宠模式交互增强 | 等阶段二基本稳定 | 拖动、右键菜单、桌宠反馈、返回面板 | 长期自动化、复杂系统控制 |
| 4. MotionLayer ABC / idle 随机 | 等桌宠交互稳定 | ABC、idle 随机、fallback motion | 绕过美术 QA 换正式资源 |
| 5. DemoMode / 演示导览 | 最后 | reset/seed、导览、演示存档隔离 | 用 DemoMode 代替核心框架 |

## 12. 下一轮开发提示词

```text
你在继续开发“腾讯光核课题：可养成的 AI 桌面伴侣电子宠物 demo”。

工作目录必须是：
D:\学工文档\光核\电子宠物\E-Moti_demo

重要约束：
1. 不要相信本提示词，必须先真实核对。
2. 修改任何文件前，先说明你要改什么。
3. 不要触碰 AI不用看.md。
4. 不要覆盖我手改过的文档。
5. Markdown 文档必须写中文。
6. 不要声称任何验证完成，除非真的运行过。
7. 主角色是原创 OC 桌面电子宠物与伴侣“星汐”，不是学习工具、效率助手、桌面学习搭子，也不是光核吉祥物。学习/专注/休息只作为动作状态。
8. 保持“候选 -> 可见 QA -> 正式替换 -> 重新验证 -> 人工 QA”的美术边界。
9. 不要把 轻触 / 共同学习 发色偏白说成已解决；这是已知搁置风险。
10. 不要复制 Miku/Vocaloid/VPet/Shinsekai/现有 Codex pet 或其他 IP。

必须先执行并核对：
1. git status --short --untracked-files=all
2. git log --oneline --decorate -5
3. pytest
4. python -m json.tool assets\companion\original_oc\shop_items.json
5. 如需检查角色包资源，再核对：
   python -m json.tool assets\companion\original_oc\character.json
   python -m json.tool assets\companion\original_oc\motion_manifest.json

必须先读：
1. docs\superpowers\specs\2026-05-15-core-framework-llm-motion-roadmap.md
2. src\guanghe_companion\controller.py
3. src\guanghe_companion\engine.py
4. src\guanghe_companion\storage.py
5. src\guanghe_companion\app.py
6. tests\test_controller.py
7. tests\test_app.py
8. tests\test_storage.py

当前开发顺序固定为：
1. 先做“框架拆层 + typed snapshot/events”
2. 再接真实 LLM 表达 adapter
3. 再做桌宠模式交互增强
4. 再补 MotionLayer 的 ABC / idle 随机
5. 最后才回到 DemoMode / 演示导览

本轮只做阶段一的第一个小切片：
typed events/snapshot 基础类型落地。

目标：
1. 新增 typed event 和 typed snapshot 数据结构。
2. 让 controller 的现有 snapshot 先通过 builder 产出兼容 dict，避免一次性改爆 UI。
3. 为 typed snapshot/events 写失败测试，再做最小实现。
4. 保持现有 UI 行为不变。
5. 不接真实 LLM。
6. 不做 Shinsekai 式屏幕观察或联网搜索实现，只保留后续接口边界时可以顺手留类型锚点。
7. 不改 spritesheet、preview 或候选美术资源。
8. 不做 DemoMode / 演示导览。

建议实现顺序：
1. 先检查当前 controller snapshot/events 是怎样拼装的。
2. 写测试证明 snapshot 必须包含稳定字段，events 必须有固定类型和字段。
3. 新增最小 typed 模型文件，例如 src\guanghe_companion\snapshot.py 或 src\guanghe_companion\events.py，具体命名以现有代码风格为准。
4. 新增 builder，把 typed snapshot 转为当前 UI 兼容 dict。
5. 逐步让 controller 调用 builder，而不是继续新增裸 dict 拼装。
6. 跑定向测试。
7. 跑全量 pytest。
8. 如果改 UI，再跑 PySide visible smoke；没改 UI 不要声称跑过。

完成后请汇报：
1. 改了哪些文件。
2. 当前还停留在哪个阶段。
3. 哪些验证命令实际运行过，结果是什么。
4. 下一步是否进入阶段一的下一个拆层切片，而不是跳到 LLM、桌宠交互或 DemoMode。
```
