# 原创二次元桌宠美术方向

## 定位

角色是原创二次元 Q 版桌宠，核心幻想是“桌面学习搭子”，辅以少量 AI 终端配件。`光核` 是课题/计划语境，不是角色本体设定，也不进入角色命名。

## 风格约束

- 2.5-3 头身，适合 `192x208` 单格显示。
- 深色像素描边，低细节、高识别。
- 小身体、大表情，动作轮廓清晰。
- 主色可使用奶白、浅蓝灰、暖黄、低饱和浅紫灰。
- 点缀色可使用少量青蓝发光元素。
- 配件控制在 1-2 个，例如耳机、悬浮书签、小终端屏、发光胸针。

## IP 边界

- 不使用 Hatsune Miku 的双马尾、葱绿色主色、V 家制服结构或可识别轮廓。
- 不复刻现有 Codex pet 的具体角色设计。
- 可参考的是 `8x9` spritesheet 工程规格、Q 版像素桌宠比例和动作行组织方式。

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
