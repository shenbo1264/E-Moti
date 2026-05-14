# Shinsekai + VPet 融合开发方案

## 1. 核心判断

课题没有要求“宠物必须是动物”。本项目可以定位为：

> 可养成的 AI 桌面伴侣：一个类人/拟人/OC 角色，像桌宠一样被照看、会回应、会成长、会因玩家操作和自身状态改变表现。

真正需要规避的是：

- 不能只是 AI 聊天窗口。
- 不能只是视觉小说。
- 不能只是 Shinsekai 或 VPet 换皮。

融合后的关键表达：

```text
VPet 提供“桌宠是游戏”的玩法骨架。
Shinsekai 提供“角色像活着”的 AI 表达管线。
原创设计提供“AI 伴侣的情绪价值与成长主题”。
```

## 2. 推荐架构

```text
CompanionStateEngine
  - 状态数值
  - 时间衰减
  - 玩家动作结算
  - 高层模式判定
  - 目标/解锁

CompanionActionLayer
  - 轻触/摸头
  - 拖拽/提起
  - 投喂/赠礼
  - 休息
  - 共同学习
  - 共同娱乐

MotionLayer
  - VPet式动画类型
  - A_Start / B_Loop / C_End / Single
  - idle 随机动画
  - 模式切换动画

ShinsekaiAIExpressor
  - 读取状态快照
  - 构造 prompt
  - 输出 JSON 演出事件
  - TTS/ASR/记忆/工具

UIBridge
  - 状态面板
  - 操作按钮
  - 对话气泡
  - 动画播放
  - 音效/BGM
```

## 3. Demo 最小闭环

### 状态

建议使用 5 个数值：

```text
focus       专注/精力，参考 VPet Strength
charge      能量补给，参考 VPet StrengthFood
stability   稳定，参考 VPet Health
mood        心情，参考 VPet Feeling
trust       信任/亲密，参考 VPet Likability
```

高层模式：

```text
Glow      mood 高且 stability 高
Calm      普通
Frayed    mood 或 charge 较低
Overload  stability 过低
```

### 操作

```text
轻触        focus -2, mood +4, trust +1
投喂        charge +15, mood +2
安抚        stability +10, mood +4, focus -2
休息        focus +12, stability +6, mood 不变或小幅 +
共同学习    focus -12, charge -5, trust +4, exp +8
共同娱乐    focus -6, mood +12, charge -4, trust +2
```

### 时间流动

每 15 秒结算一次：

```text
charge -1
focus -0.5
若长时间未互动，mood 缓慢下降
若 mood 高，trust 缓慢上升
若 charge/focus 过低，stability 下降
若休息中，focus 和 stability 恢复
```

### AI 表达

本地状态先结算，AI 只负责表达：

```json
{"character_name":"伊卡洛斯","speech":"刚才那一下我记录下来了。不是指令，是你的习惯。","sprite":"2","effect":"ATTENTION"}
{"character_name":"STAT","speech":"专注 72 / 能量 61 / 稳定 84 / 心情 76 / 信任 18","sprite":"-1","effect":""}
{"character_name":"CHOICE","speech":"轻触 / 投喂 / 安抚 / 休息 / 共同学习 / 共同娱乐","sprite":"-1","effect":""}
```

## 4. 技术融合策略

### 推荐：Python/PySide 主线

不建议把 VPet 的 C# WPF 代码直接并进 Shinsekai。更稳妥的是：

- 继续用 Shinsekai 的 Python/PySide6/TTS/LLM 基础。
- 在 Python 中重写 VPet 风格的状态机和动作规则。
- 资源组织借鉴 VPet 的 `mode + graph + animat` 思路。
- 动画播放先使用 GIF/APNG/序列帧，不追求完整 WPF 级动画系统。

原因：

- 技术栈统一，demo 风险低。
- Shinsekai 的 AI 管线可以直接用。
- VPet 的玩法逻辑不复杂，重写比跨语言集成更快。

### 资源格式建议

```text
assets/companion/ikaros/
  manifest.yaml
  motions/
    default/calm/single/
    touch_head/glow/a_start/
    touch_head/glow/b_loop/
    touch_head/glow/c_end/
    sleep/calm/a_start/
    sleep/calm/b_loop/
    sleep/calm/c_end/
  sounds/
  voice/
```

`manifest.yaml` 示例：

```yaml
name: 伊卡洛斯
type: companion
modes: [Glow, Calm, Frayed, Overload]
motions:
  default:
    calm:
      single: motions/default/calm/single/default.gif
  touch_head:
    glow:
      a_start: motions/touch_head/glow/a_start.gif
      b_loop: motions/touch_head/glow/b_loop.gif
      c_end: motions/touch_head/glow/c_end.gif
```

## 5. 玩法主题建议

### 方向 A：AI 情绪伴侣

玩家不是“饲养动物”，而是在照看一个拥有情绪阈值和记忆习惯的桌面伙伴。

核心目标：

- 建立信任。
- 帮她维持稳定。
- 解锁更自然的称呼和主动关心。

适合你说的“情绪价值”和“讲故事”。

### 方向 B：虚拟同居桌宠

角色像 VPet 一样待在桌面上，可以被摸、拖、喂、陪玩、陪学习。

核心目标：

- 每天维持状态。
- 通过共同活动升级。
- 解锁动作和台词。

适合强调“这是游戏，不是聊天工具”。

### 方向 C：UGC 角色桌宠框架

原创 OC 是默认角色，伊卡洛斯作为 UGC 样例，展示玩家可以导入不同角色包。

核心目标：

- 同一套状态机和动作规则适配不同角色。
- 不同角色有不同 prompt、动作资源和反馈风格。
- 形成“AI 角色桌宠框架”的雏形。

推荐组合：A + B 为主，C 作为亮点。也就是“先做一个强演示的 AI 情绪伴侣桌宠，再用伊卡洛斯角色包证明可扩展”。

## 6. 开发流程更新

### M1：桌宠玩法骨架

- 实现 `CompanionStateEngine`。
- 实现 5 个状态、4 个模式、6 个动作。
- 每 15 秒状态 tick。
- 操作后能看到状态变化。

### M2：VPet 风格交互

- 增加轻触/摸头区域。
- 增加拖拽/提起。
- 增加休息、共同学习、共同娱乐。
- 增加状态变化提示，例如 `专注 -2 / 心情 +4`。

### M3：动画层

- 实现 `motion` 概念：`Default / TouchHead / Sleep / Say / Work / Play / SwitchUp / SwitchDown`。
- 支持 `Single` 和简化 ABC。
- 每个模式至少有默认动画。

### M4：Shinsekai AI 表达

- 将状态快照注入 prompt。
- 要求 LLM 输出 Shinsekai 兼容 JSON。
- 添加 validator 和 fallback。
- 接入 TTS 作为增强项。

### M5：角色包与演示

- 原创 OC 主线角色。
- 伊卡洛斯 UGC 样例角色。
- 明确标注二创/UGC 边界。
- 准备 3-5 分钟演示脚本。

## 7. 答辩说法

可以这样讲：

> 我把电子宠物理解为“可被照看、会回应、会成长的陪伴实体”，不限定为动物。这个 demo 参考了 VPet 的桌宠玩法骨架，包括状态数值、触摸、拖拽、投喂、休息、工作/学习/娱乐和动画状态机；同时吸收 Shinsekai 的 AI 角色表达管线，让角色能根据状态生成个性化反馈。核心规则由本地状态机控制，AI 只负责表达和陪伴感，所以既稳定可演示，也有情绪价值。
