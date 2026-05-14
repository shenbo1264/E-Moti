# 原创二次元桌面伴侣电子宠物美术方向

## 定位

角色是原创二次元 Q 版桌面伴侣电子宠物，核心幻想是“可养成、会回应玩家的一抹甜”：可爱/漂亮、亲近、有陪伴感，能通过表情、动作和状态反馈给玩家提供情绪补给。学习、专注、休息、触摸、安慰、玩耍、收礼等是她会进入的具体状态/动作，不是基础身份。

角色必须是原创 OC，不是 `光核` 吉祥物；`光核` 只作为课题/计划语境，不进入角色本体设定，也不进入角色命名。

## 风格约束

- 2.5-3 头身，适合 `192x208` 单格显示。
- 深色像素描边，低细节、高识别。
- 小身体、大表情，动作轮廓清晰。
- 主色可使用奶白、浅蓝灰、暖黄、低饱和浅紫灰。
- 点缀色可使用少量青蓝发光元素。
- 配件控制在 1-2 个，例如耳机、悬浮书签、小终端屏、发光胸针。
- 学习/专注感只在 `review`、`waiting`、`failed` 等动作状态中表达，不把角色整体设计成单一学习工具。

## IP 边界

- 不使用 Hatsune Miku 的双马尾、葱绿色主色、V 家制服结构或可识别轮廓。
- 不复制 Miku、Vocaloid 或任何现有 IP 的发型、服装、配色和轮廓组合。
- 不复刻现有 Codex pet 的具体角色设计。
- 可参考的是 `8x9` spritesheet 工程规格、Q 版像素桌宠比例和动作行组织方式。

## 制作顺序

先确认单张基准参考图和稳定身份要素，再进入逐行动画与 spritesheet 制作；不要在基准参考未定稿前直接生成完整 atlas。基准图必须先验证：192x208 可读、2.5-3 头身比例稳定、深色像素描边清晰、1-2 个配件可持续复现。

## 接入目标

最终角色包目标：

```text
assets/companion/original_oc/
  character.json
  dialogue_style.json
  motion_manifest.json
  spritesheet.webp
  preview/
    contact-sheet.png
    gifs/
      idle.gif
      waving.gif
      waiting.gif
      review.gif
      failed.gif
```

正式替换运行资源前，候选 atlas 必须通过几何 QA、视觉 QA 和 PySide6 smoke test。
