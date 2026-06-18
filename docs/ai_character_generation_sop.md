# AI Character Generation SOP

本文档把现有原创角色“星汐”的制作方式整理成可复用流程，用于后续按用户偏好生成新的桌面伴侣角色包。目标是让项目不再只绑定单一角色，而是能产出可验证、可导入、可解释的个性化角色资产与人格设定。

## 1. 适用范围

本 SOP 适用于生成新的原创 companion pack：

- 人格设定：名称、称号、描述、表达语气、关键词、状态文案、动作文案。
- 美术资产：角色透明图集、动作帧、道具图标、预览图和 GIF。
- 配套数据：`character.json`、`dialogue_style.json`、`motion_manifest.json`、`shop_items.json`。

不适用于：

- 复制已有 IP、同人角色、商业角色、Vocaloid、Bandori、VPet、Shinsekai 或其他项目的角色设定、源码、素材、prompt、音频。
- 让 LLM 接管养成状态机。
- 让角色包直接修改存档、背包、关系、目标、长期记忆或金币数值。

## 2. 当前证据基线

现有角色包位于：

```text
assets/companion/original_oc/
```

当前包结构为：

```text
character.json
dialogue_style.json
motion_manifest.json
shop_items.json
spritesheet.png
item_icons/*.png
preview/contact-sheet.png
preview/gifs/*.gif
preview/qa_diagnostics_2026-05-13/*
```

关键工具：

- `tools/art/validate_companion_atlas.py`：校验图集尺寸、RGBA 模式、manifest 行列与动作帧范围。
- `tools/art/build_companion_preview.py`：生成 contact sheet 和各动作 GIF。

当前运行时代码已经支持按 `character_id` 读取角色包、列出内置和用户角色包、通过角色库 UI 切换角色，并通过导入工具把已校验的完整角色包复制到用户 `character_packs` 目录。生成 draft 仍然不能直接进入运行时；必须补齐正式素材、通过人工 QA 和导入门禁后再导入。

## 3. 角色包硬规格

每个新角色使用独立目录：

```text
assets/companion/<character_id>/
```

`<character_id>` 必须使用小写 ASCII、数字和下划线，例如：

```text
aurora_mender
quiet_nebula
```

必须包含：

```text
character.json
dialogue_style.json
motion_manifest.json
shop_items.json
spritesheet.png
item_icons/
preview/
```

图集固定规格：

- `sheet_columns`: 8
- `sheet_rows`: 9
- `frame_width`: 192
- `frame_height`: 208
- PNG 尺寸：1536 x 1872
- PNG 模式：RGBA
- 背景：透明

基础动作行：

| Motion | Row | Frames | 用途 |
| --- | ---: | ---: | --- |
| Default | 0 | 6 | 待机呼吸 |
| MoveRight | 1 | 8 | 向右移动 |
| MoveLeft | 2 | 8 | 向左移动 |
| TouchHead | 3 | 4 | 靠近或触碰回应 |
| Play | 4 | 5 | 娱乐互动 |
| SwitchDown | 5 | 8 | 低状态反馈 |
| Sleep | 6 | 6 | 休息 |
| Raised | 7 | 6 | 被提起 |
| Study | 8 | 6 | 共同行动 |

可以复用行的动作：

- `Comfort` 可复用 `Sleep`
- `Eat` 可复用 `TouchHead`
- `Gift` 可复用 `TouchHead`
- `Shop` 可复用 `Play`
- `Tick` 可复用 `Default`

## 4. 用户偏好采集表

生成前先让用户回答这些问题。不要直接问“你想要什么 AI 伴侣”这种过宽问题。

```text
1. 角色气质：安静陪伴 / 活泼吐槽 / 冷静可靠 / 梦幻治愈 / 其他
2. 关系节奏：慢热 / 自然熟悉 / 主动亲近 / 明确保持边界
3. 表达密度：短句 / 普通 / 更会聊天但不刷屏
4. 视觉风格：像素 / Q 版 / 半身小人 / 轻科幻 / 软萌 / 极简
5. 主色与禁用色：例如蓝白为主，避免高饱和粉紫
6. 角色身份隐喻：星云旅人 / 桌面管理员 / 小小守夜人 / 记忆修补师 / 其他
7. 不能出现的元素：具体 IP、校园监督、恋爱暗示、过度拟人、宗教、暴力等
8. 希望她记住什么：昵称 / 习惯 / 喜欢的称呼 / 不需要记忆
9. 可接受的主动性：只被动回应 / 低频主动问候 / 能根据上下文轻声提醒
10. 道具主题：食物 / 小饰品 / 纪念物 / 工具 / 混合
```

输出时必须把“用户明确禁止项”写入生成 brief。

## 5. 人格设定生成流程

### 5.1 生成角色 brief

先把用户回答归纳成角色 brief：

```text
角色必须是原创桌面伴侣，不是学习工具、效率助手、课程监督者或品牌吉祥物。
她/他/它通过本地状态、动作和经过验证的表达事件回应用户。
LLM 只增强语言表达和上下文感，不能写入养成状态。
```

brief 应包含：

- `character_id`
- 角色中文名和可选英文名
- 一句话定位
- 视觉关键词
- 性格关键词
- 说话边界
- 禁用元素
- 道具主题
- 关系推进方式

### 5.2 生成 `character.json`

模板：

```json
{
  "character_id": "<character_id>",
  "name": "<角色名>",
  "title": "<短称号>",
  "description": "<一句话说明她是什么、如何回应玩家>",
  "spritesheet": "spritesheet.png",
  "motion_manifest": "motion_manifest.json",
  "default_mode": "Calm",
  "modes": ["Glow", "Calm", "Frayed", "Overload"],
  "mode_descriptions": {
    "Glow": "<高稳定/亲近状态文案>",
    "Calm": "<日常平稳状态文案>",
    "Frayed": "<疲惫/分心状态文案>",
    "Overload": "<保护/低负荷状态文案>"
  },
  "motion_labels": {
    "Default": "<待机文案>",
    "TouchHead": "<靠近回应文案>",
    "Comfort": "<安抚文案>",
    "Sleep": "<休息文案>",
    "Study": "<共同行动文案>",
    "Play": "<娱乐文案>",
    "Raised": "<被提起文案>",
    "Eat": "<投喂文案>",
    "Gift": "<礼物文案>",
    "Shop": "<商店文案>",
    "Tick": "<时间流逝文案>",
    "SwitchDown": "<低状态文案>"
  },
  "relationship_decorations": [
    {
      "unlock_id": "unlock_first_nickname",
      "item_id": "<gift_item_id>",
      "label": "<装饰名>",
      "icon": "item_icons/<gift_item_id>.png"
    }
  ]
}
```

约束：

- `modes` 建议先沿用当前四档，避免每个角色自定义状态机。
- `motion_labels` 可以个性化，但 motion key 不要改。
- `relationship_decorations` 只能引用本角色包内的原创图标。

### 5.3 生成 `dialogue_style.json`

模板：

```json
{
  "tone": "<一句话语气>",
  "keywords": ["<关键词1>", "<关键词2>", "<关键词3>", "<关键词4>", "<关键词5>"],
  "fallback_style": "<LLM 不可用时的短句风格>"
}
```

约束：

- 不写“必须监督用户学习”“替用户规划人生”等工具化人格。
- 不写会修改状态、解锁关系、赠送物品、读取隐私的承诺。
- `fallback_style` 要能在无 LLM 时成立。

## 6. 美术生成流程

### 6.1 参考图阶段

先生成一张原创角色设定图，不直接生成图集。

参考 prompt 结构：

```text
Create an original desktop companion character design sheet.
No copyrighted characters, no fan art, no existing franchise style copying.
Small readable silhouette, transparent background friendly, consistent outfit.
Visual style: <用户风格>.
Personality: <人格关键词>.
Palette: <主色和禁用色>.
Include front view, side hint, facial expressions, small accessory details.
Avoid: <禁止项>.
```

验收：

- 轮廓在 192 x 208 小尺寸下仍可读。
- 配色不贴近现有知名角色。
- 没有文字水印、签名、logo。
- 没有明显第三方 IP 特征。

### 6.2 动作拆分阶段

按 motion 逐组生成动作草图，再统一重绘为同一角色。每个动作只改变姿态，不改变基础服装、发型、配色和比例。

动作 brief：

```text
Generate animation keyframes for the same original desktop companion.
Canvas per frame: 192x208, transparent background, full body visible, centered.
Keep exact same character identity, outfit, palette, hair, accessories.
Motion: <Default/MoveRight/MoveLeft/TouchHead/Play/SwitchDown/Sleep/Raised/Study>.
Frame count: <N>.
No text, no logo, no background, no copyrighted style.
```

建议：

- 先做 `Default`、`TouchHead`、`Sleep` 三个动作，确认角色一致性。
- 再补 `MoveLeft`、`MoveRight`、`Play`、`SwitchDown`、`Raised`、`Study`。
- 如果时间不够，允许 `Comfort/Eat/Gift/Shop/Tick` 复用基础行。

### 6.3 图集拼装阶段

把动作帧拼成固定 8 x 9 图集：

```text
row 0: Default
row 1: MoveRight
row 2: MoveLeft
row 3: TouchHead
row 4: Play
row 5: SwitchDown
row 6: Sleep
row 7: Raised
row 8: Study
```

空余帧处理：

- 同一行少于 8 帧时，剩余格可以透明留空。
- 不要把其他动作塞进空余格，避免 manifest 与图集语义错位。
- 角色脚底/重心尽量保持一致，减少播放时跳动。

### 6.4 道具图标

每个 `shop_items.json` 条目必须有对应 `item_icons/*.png`。

道具生成 prompt：

```text
Create a small original item icon for a desktop companion game.
Transparent background, readable at 32x32 and 64x64.
Item: <道具名>.
Theme: <角色主题>.
No text, no logo, no copyrighted symbol.
```

道具类别先限制为：

- `food`
- `gift`
- `tool`

效果字段必须使用本地已有 deterministic key，例如：

- `charge`
- `mood`
- `stability`
- `trust`
- `study_bonus_exp`

不要新增会绕过本地状态机的效果字段。

## 7. 质量验收

### 7.1 JSON 校验

```powershell
python -m json.tool assets\companion\<character_id>\character.json
python -m json.tool assets\companion\<character_id>\dialogue_style.json
python -m json.tool assets\companion\<character_id>\motion_manifest.json
python -m json.tool assets\companion\<character_id>\shop_items.json
```

### 7.2 图集校验

```powershell
python tools\art\validate_companion_atlas.py --atlas assets\companion\<character_id>\spritesheet.png --manifest assets\companion\<character_id>\motion_manifest.json
```

通过标准：

```text
OK atlas 1536x1872 RGBA
```

### 7.3 预览生成

```powershell
python tools\art\build_companion_preview.py --atlas assets\companion\<character_id>\spritesheet.png --manifest assets\companion\<character_id>\motion_manifest.json --output assets\companion\<character_id>\preview
```

人工检查：

- `preview/contact-sheet.png` 的每一行动作语义正确。
- `preview/gifs/*.gif` 不出现错帧、跳帧、明显裁切。
- 透明背景正常。
- 小尺寸下脸、主体轮廓、关键道具仍可辨认。

### 7.4 代码侧回归

现阶段新增角色包后，至少跑：

```powershell
python -m pytest tests\test_character_pack.py tests\test_motion.py tests\test_shop_items.py tests\test_art_tools.py
```

如果实现了角色选择 UI、导入器或运行时切换，再补：

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py
python -m pytest
```

## 8. 安全与开源检查

发布前必须检查：

- 角色 brief、prompt、图片、道具没有指向具体第三方 IP。
- 文档和提交记录不包含 API key。
- 不提交 `data/companion_save.json`。
- 不提交临时生成失败图、模型缓存、参考项目素材。
- 如果使用外部生成模型，记录模型名、日期、输入约束和人工筛选结论，但不要记录密钥。

建议在角色包内保留一个人工可读 provenance 文件：

```text
assets/companion/<character_id>/provenance.md
```

内容只记录：

- 生成日期
- 使用的工具或模型
- 原创性声明
- 用户偏好摘要
- 禁用项
- 人工 QA 结论

## 9. 与 LLM 核心能力的边界

角色人格可以强烈影响 LLM 表达，但不能越过状态边界。

允许：

- 把 `dialogue_style.json`、角色 brief、当前动作、关系展示文案作为只读 prompt context。
- 让 LLM 生成更自然的短句、称呼、语气和情绪反馈。
- 让 LLM 根据屏幕观察和搜索摘要调整表达方式。

禁止：

- LLM 直接写入 `CompanionState`。
- LLM 输出金币、背包、关系解锁、目标、记忆写入或存档变更。
- 角色包自带脚本在运行时控制鼠标、键盘、剪贴板或窗口。
- 角色人格把产品定位改成学习监督、效率管家或光核吉祥物。

## 10. 后续实现 backlog

### 2026-06-05 实现状态

已完成第一版角色个性化运行时地基：

- `src/guanghe_companion/character_registry.py`
  - 扫描内置角色包和用户角色包目录。
  - 内置目录来自 `assets/companion/*`；用户目录为应用数据目录下的 `character_packs/*`。
  - 校验 `character.json`、`dialogue_style.json`、`motion_manifest.json`、`shop_items.json`、图集尺寸和图标路径。
  - 坏包不会进入角色库 UI。

- `src/guanghe_companion/character_session.py`
  - 为每个 `character_id` 生成独立会话路径。
  - 存档、对话历史、长期记忆和表达设置按角色隔离。

- `src/guanghe_companion/controller.py`
  - 支持用非默认 `character_id` 启动。
  - 支持 `switch_character()` 切换角色会话。
  - 商店和库存已改为当前角色的 item catalog，不再硬读全局默认商店。

- `src/guanghe_companion/app.py`
  - 控制中心新增“角色库”页。
  - 角色库可列出内置角色包和用户 `character_packs` 目录中的已校验角色包。
  - 切换角色后会刷新角色说明、输入框称呼、商店、背包、motion catalog 和 spritesheet。
  - 已打开桌宠窗口时，会同步刷新桌宠窗口角色资源。

- `src/guanghe_companion/character_inspiration.py`
  - 支持基于联网搜索结果生成“原创灵感 brief”。
  - 来源只作为抽象特征，不直接复制角色名、台词、立绘或专有设定。
  - 本地二创模式只返回授权策略，不下载、不内置、不分发受保护素材。

- `src/guanghe_companion/character_generation_workflow.py`
  - 根据 brief 生成 draft 角色包目录。
  - 输出 JSON 草稿、art prompts、provenance 和 QA checklist。
  - 不生成正式 `spritesheet.png`，不写入 `assets/companion/`，必须人工 QA 后再导入。

仍未完成 / 仍需确认：

- UI 中直接完成“draft 生成 -> 美术 QA -> 导入”的完整向导。
- UI 中直接调用“灵感导入器”和“AI 资产生成工作流”。
- 图像生成模型、ComfyUI 或其他美术生成后端接入。
- 角色包 license/provenance 的完整 UI 展示与导入确认流程。

为了真正支持用户个性化选择，后续建议按包实现：

1. 角色包 schema 校验器
   - 校验 `character.json`、`dialogue_style.json`、`shop_items.json`、`motion_manifest.json`。
   - 校验图标路径、动作 key、数值效果字段。

2. 角色包注册表
   - 扫描 `assets/companion/*/character.json`。
   - 排除缺文件、JSON 错误、图集错误的包。
   - 给 UI 返回可展示的角色名、称号、预览图。

3. 角色选择 UI
   - 启动页或设置页选择角色。
   - 切换后重新加载 character pack、motion catalog 和 shop items。
   - 明确提示：切换角色不迁移或改写已有存档状态。

4. 用户生成角色导入流
   - 从用户目录导入角色包。
   - 先验证再复制到应用数据目录。
   - 失败时给出具体原因，不半导入。

5. AI 工作流脚本
   - 根据问卷生成 brief 和 JSON 草稿。
   - 生成美术 prompt。
   - 不直接写生产资产，先输出到 `generated/` 或临时目录等待人工 QA。

## 11. 最小可执行流程

一次完整角色生成应按这个顺序走：

```text
用户问卷
-> 角色 brief
-> character.json 草稿
-> dialogue_style.json 草稿
-> shop_items.json 草稿
-> 原创参考图
-> 动作帧生成
-> spritesheet.png 拼装
-> item_icons 生成
-> JSON 校验
-> 图集校验
-> 预览生成
-> 人工视觉 QA
-> 将 `portrait_candidate.json` 明确标为 `status=approved`、`approval_required=false`、`runtime_manifest_safe=true`
-> `python tools\validate_character_draft.py <draft_dir>`
-> 定向测试
-> `python tools\import_character_pack.py <complete_pack> --target-root <user_character_packs>`
```

验收口径：

```text
角色包是原创的。
角色人格是可解释的。
资产规格是可验证的。
LLM 表达是核心体验，但状态机仍由本地确定性代码控制。
用户可以选择角色，但角色不能越权改写养成系统。
```
