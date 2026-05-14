# AI 桌面伴侣电子宠物 Demo 产品技术 Spec

状态：草案 v0.1

目标提交目录：`D:\学工文档\光核\电子宠物\首选`

参考底座：

- Shinsekai：AI 角色演出、结构化 JSON 事件、LLM/TTS/ASR 适配器、PySide6 桌面 UI。
- VPet：桌宠状态数值、时间衰减、触摸/拖拽/投喂/休息/工作学习娱乐、ABC 动画、资源/MOD 思想。

## 1. 产品定义

本 demo 是一款“可养成的 AI 桌面伴侣电子宠物”。“宠物”不限定为动物形态，可以是类人伴侣、原创 OC、虚拟伙伴或 UGC 角色。核心要求是：玩家可以通过明确操作影响它，它会根据自身状态和玩家行为给出可见反馈，并在短时间内展示成长和陪伴关系。

暂时命名为E-Moti (一抹甜)

英文解构： E (Electronic 电子的) + Moti (Emotion 情绪 / Motivation 动力)。

中文谐音： 一抹甜。

情绪价值： 当玩家在桌面前工作学习娱乐到专注力（Focus）耗尽、进入低状态时，这个伴侣就像是投递到桌面上的 “一抹甜”。它弱化了 “养宠物” 的负担感，强调它是你疲惫生活里的情绪补给站。

一句话：

> 一个住在桌面上的 AI 伴侣。玩家通过轻触、投喂/赠礼、安抚、休息、共同学习和共同娱乐影响她的状态；本地状态机保证游戏闭环，AI 负责把反馈表达得像一个有记忆、有情绪、有边界的伙伴。

## 2. 设计目标

### 2.1 课题目标

- 3-5 分钟内让评委看懂：这是一个会回应玩家的电子宠物/桌面伴侣。
- 10 秒内看到角色、状态、操作入口。
- 30-60 秒内看到一次明确闭环：玩家操作 -> 角色反馈 -> 状态变化。
- 结束前讲清楚项目亮点、差异化、开源吸纳和 AI 使用边界。

### 2.2 产品目标

- 把 Shinsekai 的 AI 角色生命感转化成“桌宠陪伴反馈”。
- 把 VPet 的桌宠玩法骨架转化成可控、轻量、可演示的游戏循环。
- 支持原创 OC 作为主角色，伊卡洛斯作为 UGC 角色包样例。
- 即使 LLM/TTS 不可用，核心游戏闭环也能离线演示。

### 2.3 非目标

- 不做完整长期养成商业游戏。
- 不做纯聊天助手。
- 不做纯视觉小说。
- 不直接移植 VPet 的 C# WPF Core。
- 不做复杂商业化经济、抽卡、付费数值、联网交易、创意工坊、长期日程、联网多人。

## 3. 核心用户体验

### 3.1 首屏

首屏必须包含：

- 角色主体：大图、GIF、APNG 或序列帧动画。
- 状态面板：专注、能量、稳定、心情、信任。
- 操作入口：轻触、投喂/赠礼、安抚、休息、共同学习、共同娱乐。
- 资源入口：金币、背包、商店。
- 当前目标：例如“让信任达到 20，解锁她第一次主动称呼你”。
- 反馈区：角色短句、状态变化提示、音效/表情变化。

### 3.2 MVP 演示闭环

流程：

1. 玩家点击“轻触”。
2. 本地状态机结算：`focus -2, mood +4, trust +1`。
3. UI 立即显示变化值：`专注 -2 / 心情 +4 / 信任 +1`。
4. MotionLayer 播放 `TouchHead` 动画。
5. AIExpressor 根据状态生成短句。
6. 角色说：“我记录下来了。这不是指令，是你靠近我的方式。”
7. 状态面板刷新。
8. 当前目标进度刷新。

验收点：不依赖用户阅读长文本，也能看懂“操作影响角色，角色有反馈，状态发生变化”。

## 4. 系统架构

```text
UI 操作 / 桌面触摸 / 快捷按钮
  -> CompanionActionLayer
  -> CompanionStateEngine
  -> InventoryService / ShopService
  -> CompanionSnapshot
  -> MotionLayer
  -> ShinsekaiAIExpressor
  -> EventValidator
  -> UIBridge
  -> Shinsekai Worker / TTS / 音效 / 对话显示
  -> SaveManager
```

### 4.1 模块职责

`CompanionStateEngine`

- 持有状态数值。
- 处理动作结算。
- 处理时间 tick。
- 计算高层模式。
- 计算目标进度和解锁。

`CompanionActionLayer`

- 定义玩家动作。
- 将 UI 点击、触摸区域、拖拽、快捷菜单转成标准动作。
- 阻止当前状态下不允许的动作。

`MotionLayer`

- 管理 VPet 风格动作类型。
- 支持 `Single` 和简化 `A_Start / B_Loop / C_End`。
- 根据动作和模式选择动画资源。

`InventoryService`

- 管理金币、背包物品、堆叠数量。
- 处理购买入库、使用消耗、赠礼消耗。
- 把物品效果转成标准动作结算请求。

`ShopService`

- 提供固定商品池。
- 根据等级、信任、目标进度控制商品解锁。
- 处理价格、购买限制和商店刷新。

`ShinsekaiAIExpressor`

- 接收 `CompanionSnapshot`。
- 构造 prompt。
- 调用 Shinsekai LLM 管线。
- 输出兼容 Shinsekai 的 JSON 事件。

`EventValidator`

- 校验 LLM JSON。
- 限制字段、资源 id、effect 白名单。
- LLM 失败时返回 fallback。

`UIBridge`

- 把状态、动作、motion、AI 事件映射到 PySide UI。
- 固定显示状态面板和操作按钮。
- 调用 Shinsekai 原有对话、选项、TTS、音效通道。

`SaveManager`

- 保存状态、目标、角色包、最近互动、AI 使用配置。
- 保存格式用 JSON 或 YAML，避免依赖 VPet 的 LPS 格式。

## 5. 状态模型

### 5.1 数值

```text
focus       专注/精力，0-100
charge      能量补给，0-100
stability   心智稳定，0-100
mood        情绪亮度，0-100
trust       信任/亲密，0-100
exp         默契经验，>=0
level       默契等级，>=1
```

初始值：

```text
focus: 72
charge: 65
stability: 78
mood: 58
trust: 5
exp: 0
level: 1
```

### 5.2 高层模式

```text
Glow:
  条件：mood >= 75 且 stability >= 70
  表现：更主动、更明亮、反馈更亲密

Calm:
  条件：默认正常状态
  表现：稳定互动

Frayed:
  条件：mood < 35 或 charge < 25 或 focus < 20
  表现：短句、疲惫、拒绝高消耗行为

Overload:
  条件：stability < 25
  表现：进入保护状态，只允许安抚和休息
```

模式优先级：`Overload > Frayed > Glow > Calm`。

### 5.3 时间 tick

默认每 15 秒结算一次：

```text
charge -= 1
focus -= 0.5
若距离上次互动超过 60 秒：mood -= 1
若 mood >= 75：trust += 0.2
若 charge < 20 或 focus < 15：stability -= 1
若当前状态为休息：focus += 3, stability += 2, charge -= 0.3
```

数值需要 clamp 到 0-100。

## 6. 玩家动作

### 6.1 动作表

| 动作 | 输入 | 立即结算 | 限制 | 反馈类型 |
|---|---|---|---|---|
| 轻触 | 点击头部/按钮 | focus -2, mood +4, trust +1 | Overload 下效果减半 | TouchHead motion + 短句 |
| 投喂 | 背包食物/快捷按钮 | 按物品配置恢复 charge/mood | charge >= 95 时拒绝 | Eat motion + 物品消耗 |
| 赠礼 | 背包礼物/快捷按钮 | 按物品配置提升 mood/trust | 同类礼物短时收益递减 | Gift motion + 物品消耗 |
| 安抚 | 按钮 | stability +10, mood +4, focus -2 | 无 | Comfort motion |
| 休息 | 按钮 | 进入 Resting 状态 | 已休息时可唤醒 | Sleep A/B/C |
| 共同学习 | 按钮 | focus -12, charge -5, trust +4, exp +8, coins +8 | focus < 20 或 Overload 禁止 | Work/Study motion |
| 共同娱乐 | 按钮 | focus -6, charge -4, mood +12, trust +2, coins +3 | charge < 10 禁止 | Play motion |
| 拖拽/提起 | 鼠标拖动 | mood 可能 + 或 -，根据模式决定 | Overload 下抗拒 | Raised motion |

### 6.2 动作失败反馈

当动作被拒绝时，仍然要有反馈：

```text
共同学习被拒绝：
  条件：focus < 20
  本地反馈：不改变 exp
  AI fallback：现在不行。我会把注意力弄碎的。先让我休息一下。
```

拒绝不是错误，而是“角色有边界”的陪伴感来源。

### 6.3 背包与商店经济

MVP 实现轻量但完整的背包和商店闭环。目标不是做复杂经济系统，而是让投喂、赠礼、学习、娱乐和目标解锁有可见资源循环。

核心闭环：

```text
共同学习/共同娱乐/完成目标 -> 获得 coins
coins -> 商店购买 food/gift/tool
物品进入背包
玩家从背包使用或赠送物品
本地状态机结算效果
角色播放动作并通过 AI 表达反馈
```

背包规则：

- 物品按 `item_id` 堆叠。
- 使用物品必须消耗数量。
- 物品效果由本地配置决定，AI 不能临时创造效果。
- 食物主要影响 `charge/mood`。
- 礼物主要影响 `mood/trust`。
- 工具主要触发一次性目标、特殊台词或轻量状态修正。

商店规则：

- MVP 使用固定商品池，不做随机抽卡。
- 商品数量控制在 8-12 个。
- 每个商品包含 `price`、`category`、`effects`、`unlock_condition`。
- 商店可以按等级或信任解锁新商品，但不做复杂库存刷新。
- 初始金币建议为 20，保证 30 秒内能演示一次购买和一次使用。

示例物品：

| 物品 | 类型 | 价格 | 效果 | 用途 |
|---|---|---:|---|---|
| 热牛奶 | food | 12 | charge +12, mood +2 | 演示投喂 |
| 能量糖 | food | 18 | charge +20, stability -2 | 有取舍的投喂 |
| 星形发夹 | gift | 24 | mood +8, trust +3 | 演示赠礼 |
| 安抚毯 | tool | 30 | stability +12 | 低状态修复 |
| 学习贴纸 | tool | 16 | 下一次学习 exp +4 | 目标联动 |

## 7. 动画与资源规格

### 7.1 动画类型

Spec 功能层支持以下动作名：

```text
Default      待机
TouchHead    轻触/摸头
Eat          投喂
Gift         赠礼
Comfort      安抚
Sleep        休息
Say          说话
Study        共同学习
Play         共同娱乐
Raised       拖拽/提起
SwitchUp     状态改善
SwitchDown   状态恶化
```

### 7.2 单角色 MVP 动画数量

MVP 单角色不要求为每个功能制作完全独立动画。基础交付采用 `awesome-codex-pet` 式固定 atlas：`8 列 x 9 行`，单格 `192x208`，总尺寸 `1536x1872`，透明背景。

基础 atlas 需要 9 行动作，共 57 个有效帧：

| Atlas 行 | 帧数 | 对应运行时动作 | 覆盖的 Spec 功能 |
|---|---:|---|---|
| `idle` | 6 | `Default` / `Say` | 待机、说话、常规反馈 |
| `waving` | 4 | `TouchHead` / `Gift` | 轻触、收到礼物、打招呼 |
| `waiting` | 6 | `Sleep` / `Comfort` | 休息、安抚、等待互动 |
| `review` | 6 | `Study` | 共同学习、专注状态 |
| `jumping` | 5 | `Play` | 共同娱乐、心情提升 |
| `failed` | 8 | `SwitchDown` / action rejected | 状态恶化、动作拒绝、Overload |
| `running` | 6 | `Raised` / in-place move | 拖拽、提起、桌面小移动 |
| `running-right` | 8 | `MoveRight` | 右移或拖拽跟随 |
| `running-left` | 8 | `MoveLeft` | 左移或拖拽跟随 |

这个 9 行基础包已经覆盖：轻触、投喂/赠礼、安抚、休息、共同学习、共同娱乐、拖拽/提起、状态恶化、说话反馈。投喂和赠礼在 MVP 中可先通过 `waving`/`waiting` 加物品图标、音效和状态变化表现，不强制独立行。

增强版建议再补 4 个专属动作：

| 增强动作 | 优先级 | 价值 |
|---|---|---|
| `eat` | 高 | 让投喂更像真实玩法 |
| `gift` | 高 | 强化背包/商店存在感 |
| `comfort` | 中 | 强化陪伴情绪价值 |
| `sleep` | 中 | 强化状态恢复和低状态演示 |

因此单角色动画需求分两档：

```text
MVP 基础：9 行 atlas，57 个有效帧。
演示增强：9 行 atlas + 4 个专属 Single/GIF 动作。
```

### 7.3 动画段

MVP 支持：

```text
Single
A_Start
B_Loop
C_End
```

优先级：

- 必须：`Default/Single`、`Say/Single`、`TouchHead/Single`、`Sleep/Single`、`SwitchDown/Single`。
- 建议：`TouchHead/A_B_C`、`Sleep/A_B_C`、`Study/Single`、`Play/Single`。
- 可选：`Raised/A_B_C`、`Eat/Gift` 夹层动画。

### 7.4 资源包结构

```text
assets/companion/<character_id>/
  manifest.yaml
  prompt.md
  spritesheet.webp
  motions/
    default/calm/single/default.gif
    say/calm/single/say.gif
    touch_head/glow/single/touch.gif
    sleep/frayed/single/sleep.gif
  sounds/
    attention.wav
    disappointed.wav
    switch.ogg
  voice/
```

### 7.5 角色包字段

```yaml
id: original_oc
name: 光核伴生体
type: companion
license: original
modes: [Glow, Calm, Frayed, Overload]
default_mode: Calm
prompt_file: prompt.md
spritesheet: spritesheet.webp
motion_manifest:
  default:
    calm:
      single: motions/default/calm/single/default.gif
effects:
  ATTENTION: sounds/attention.wav
  DISAPPOINTED: sounds/disappointed.wav
```

伊卡洛斯角色包必须标注为 UGC/样例，不作为原创主角答辩。

## 8. AI 事件规格

### 8.1 输出格式

LLM 输出兼容 Shinsekai 的 JSON 对象流，每轮最多 4 个对象：

```json
{"character_name":"光核伴生体","speech":"我听见你靠近了。今天的频率比昨天更稳。","sprite":"2","effect":"ATTENTION"}
{"character_name":"STAT","speech":"专注 70 / 能量 65 / 稳定 78 / 心情 62 / 信任 6","sprite":"-1","effect":""}
{"character_name":"CHOICE","speech":"轻触 / 投喂 / 安抚 / 休息 / 共同学习 / 共同娱乐","sprite":"-1","effect":""}
```

### 8.2 字段约束

```text
character_name:
  允许：当前角色名、STAT、CHOICE、NARR

speech:
  1-80 字，STAT 可更长但不超过 120 字

sprite:
  -1 或当前角色资源 id

effect:
  空字符串或白名单：ATTENTION, DISAPPOINTED, SHOCKED, SWITCH, OVERLOAD
```

### 8.3 AI 不允许决定的内容

AI 不允许直接修改：

- 状态数值。
- 动作结果。
- 目标完成状态。
- 解锁物品。
- 存档。

AI 只能读取本地状态快照，并生成表达。

### 8.4 Fallback

LLM 不可用、超时、JSON 不合法时，使用本地 fallback：

```json
{"character_name":"光核伴生体","speech":"信号有点乱，但我还在。先做一个简单动作吧。","sprite":"1","effect":"DISAPPOINTED"}
{"character_name":"STAT","speech":"专注 {focus} / 能量 {charge} / 稳定 {stability} / 心情 {mood} / 信任 {trust}","sprite":"-1","effect":""}
{"character_name":"CHOICE","speech":"轻触 / 投喂 / 安抚 / 休息","sprite":"-1","effect":""}
```

## 9. UI 规格

### 9.1 主界面布局

```text
┌─────────────────────────────┐
│  角色动画区                 │
│                             │
│  [桌面伴侣主体]             │
│                             │
├───────────────┬─────────────┤
│  反馈气泡      │  状态面板    │
│  最近一句话    │  当前目标    │
├───────────────┴─────────────┤
│  操作按钮：轻触 投喂 安抚 休息 学习 娱乐 │
│  资源入口：背包 商店 赠礼               │
└─────────────────────────────┘
```

### 9.2 状态显示

状态条需要同时显示：

- 当前值。
- 最近变化值。
- 异常提示。
- 高层模式。

示例：

```text
模式：Glow
专注 70 (-2)
能量 65
稳定 78
心情 62 (+4)
信任 6 (+1)
目标：信任 20 解锁主动称呼
```

### 9.3 操作入口

MVP 必须用按钮提供明确操作，不允许只靠自然语言输入。

MVP 的主按钮保持 6 个，避免首屏过载。赠礼、物品使用和购买从背包/商店入口进入。

自然语言输入是增强项：

- 玩家可以说“今天一起学习吧”。
- 系统将其映射为 `study_together`。
- 映射失败时作为普通聊天。

## 10. 存档规格

存档文件：`data/companion/save.json`

```json
{
  "character_id": "original_oc",
  "character_name": "光核伴生体",
  "focus": 70,
  "charge": 65,
  "stability": 78,
  "mood": 62,
  "trust": 6,
  "exp": 8,
  "level": 1,
  "coins": 20,
  "mode": "Calm",
  "current_goal": "unlock_first_nickname",
  "unlocks": [],
  "inventory": [
    {"item_id": "warm_milk", "count": 1},
    {"item_id": "star_hairpin", "count": 0}
  ],
  "shop_unlocks": ["basic_food", "basic_gift"],
  "last_interaction_at": "2026-05-11T15:30:00+08:00"
}
```

## 11. MVP 范围

### 必须实现

- 1 个原创主角色。
- 5 个状态数值。
- 4 个高层模式。
- 6 个主按钮动作、背包赠礼动作、拖拽/提起动作。
- 15 秒 tick。
- 状态面板。
- 角色反馈区。
- 9 行基础 spritesheet，覆盖 57 个有效动画帧。
- 轻量背包。
- 轻量商店。
- 8-12 个可购买/可使用物品。
- LLM JSON 表达接入。
- LLM fallback。
- 3-5 分钟演示脚本。
- AI 使用和开源使用说明。

### 应该实现

- TTS。
- 轻触/拖拽区域。
- 简化 ABC 动画。
- 投喂/赠礼专属增强动画。
- 伊卡洛斯 UGC 角色包样例。
- 目标达成解锁一句新称呼或新动作。

### 暂不实现

- 复杂经济系统。
- 随机抽卡。
- 联网交易。
- Steam 创意工坊。
- 多人联机。
- 完整 ASR。
- T2I 实时生成。
- MCP 外部工具。

## 12. 里程碑

### M1：离线状态机

输出：

- `CompanionStateEngine`
- `CompanionAction`
- tick 规则
- 控制台或简单 UI 验证

验收：

- 点击动作后状态变化正确。
- tick 会自动改变状态。
- mode 会根据规则切换。

### M2：桌宠 UI 闭环

输出：

- 状态面板。
- 操作按钮。
- 反馈气泡。
- 简单动画切换。

验收：

- 10 秒内看懂角色、状态、操作。
- 30 秒内看到一次完整闭环。

### M3：Shinsekai AI 表达

输出：

- prompt builder。
- JSON event validator。
- fallback。
- 接入 Shinsekai parser/worker。

验收：

- AI 正常时生成个性化反馈。
- AI 失败时 demo 不崩。
- AI 不直接改状态。

### M4：背包与商店经济

输出：

- `InventoryService`。
- `ShopService`。
- 物品配置。
- 金币获取和消费。
- 背包 UI 与商店 UI。

验收：

- 学习或娱乐后能获得金币。
- 商店能购买物品。
- 背包能使用或赠送物品。
- 物品效果由本地状态机结算。

### M5：VPet 风格交互与动画

输出：

- 轻触区域。
- 拖拽/提起。
- 休息/学习/娱乐 motion。
- 状态切换 motion。
- 9 行基础 spritesheet 接入。

验收：

- 不同操作有不同动作和状态结果。
- 低状态会限制动作。
- 每个核心动作至少能映射到一行动画或增强动作。

### M6：演示与交付

输出：

- demo 脚本。
- README。
- AI 使用申报。
- 开源使用说明。
- 可运行包或启动说明。

验收：

- 3-5 分钟完整演示。
- 能讲清楚 Shinsekai、VPet 和原创内容边界。

## 13. 风险与处理

### LLM 输出不稳定

处理：

- 每轮最多 4 个 JSON。
- EventValidator 严格校验。
- fallback 兜底。
- 关键规则本地决定。

### 被误判为聊天助手

处理：

- 首屏突出状态和按钮。
- 所有关键演示从按钮动作开始。
- 聊天框弱化为反馈区。
- 展示动作限制和状态变化。

### 被误判为 VPet/Shinsekai 换皮

处理：

- 原创主角色和主题。
- 原创状态命名和目标线。
- 明确开源吸纳点。
- 不直接复制 VPet 动画作为主资产。

### Demo 范围失控

处理：

- MVP 只做轻量背包和固定商店，不做复杂经济、完整 ASR、实时 T2I、MCP。
- TTS 可作为增强项，不作为核心闭环。

## 14. 开源与 AI 使用边界

### Shinsekai

- 用途：AI 事件管线、LLM/TTS/ASR 适配思想、PySide 桌面演出参考。
- License：MIT，保留版权和许可声明。

### VPet

- 用途：桌宠玩法、状态系统、动画组织、交互设计参考。
- License：代码 Apache 2.0。
- 动画素材：有额外授权声明。建议只做参考，最终使用原创或可授权资源。

### AI

- 用途：技术分析、spec 草案、文案、部分角色反馈、可能的素材辅助。
- 人工负责：主题取舍、玩法规则、状态数值、演示流程、代码整合、最终测试。
- 运行时 AI 边界：AI 只生成表达，不决定核心状态。

## 15. 验收清单

- 10 秒内看到角色、状态、操作入口。
- 30-60 秒内完成一次操作闭环。
- 至少一个状态异常能限制动作。
- 至少一次完成“获得金币 -> 商店购买 -> 背包使用/赠送 -> 状态变化”。
- 单角色基础 spritesheet 覆盖 9 行动作、57 个有效帧。
- 每个核心按钮动作都有动画、音效或状态变化反馈。
- 至少一个目标能在 3-5 分钟内达成或接近达成。
- 关闭 LLM 后仍能演示核心闭环。
- 打开 LLM 后反馈更有角色感。
- README 说明开源和 AI 使用边界。
- 演示脚本能说明“类人伴侣也属于电子宠物”的设计理由。
