# AI 美术资源管线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一套可验证的二次元 Q 版桌宠美术资源管线，让 AI 生成资源能稳定进入现有 PySide6 demo。

**Architecture:** 先把美术方向和 prompt 模板固化为中文文档，再新增独立的 `tools/art` 脚本做 atlas 几何 QA 与预览生成，最后让 MotionLayer 从角色配置读取 spritesheet 文件名。运行时仍只依赖角色包和 MotionLayer，不把生图过程文件耦合进 UI。

**Tech Stack:** Python 3.11、PySide6、Pillow、pytest、JSON 角色包配置。

---

## 文件结构

- Create: `docs/art/art_direction.md`，中文说明原创二次元 Q 版桌宠方向、IP 边界、验收标准。
- Create: `docs/art/prompt_templates.md`，中文保存基准图 prompt、逐行动画 prompt 和负向约束。
- Create: `tools/art/validate_companion_atlas.py`，命令行校验 atlas 尺寸、网格、manifest 帧数和透明通道。
- Create: `tools/art/build_companion_preview.py`，命令行生成 contact sheet 和每行动作 GIF。
- Create: `tests/test_art_tools.py`，测试 atlas 校验和预览生成脚本。
- Modify: `pyproject.toml`，增加 `Pillow` 依赖。
- Modify: `src/guanghe_companion/character_pack.py`，读取 `character.json` 中的 `spritesheet` 字段。
- Modify: `src/guanghe_companion/motion.py`，MotionCatalog 使用角色包提供的 spritesheet 文件名。
- Modify: `tests/test_character_pack.py`，覆盖 spritesheet 字段读取。
- Modify: `tests/test_motion.py`，覆盖 MotionLayer 使用配置中的 spritesheet 路径。

---

### Task 1: 增加中文美术方向和 prompt 模板文档

**Files:**
- Create: `docs/art/art_direction.md`
- Create: `docs/art/prompt_templates.md`

- [ ] **Step 1: 写入中文美术方向文档**

Create `docs/art/art_direction.md`:

```markdown
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
```

- [ ] **Step 2: 写入 prompt 模板文档**

Create `docs/art/prompt_templates.md`:

```markdown
# AI 美术 Prompt 模板

## 基准图 Prompt

```text
为一款 AI 桌面伴侣电子宠物游戏设计一个原创二次元 Q 版像素角色。
角色定位是桌面学习搭子，不是“光核”吉祥物。
风格：可爱的 2.5 头身 chibi，清晰深色像素描边，在 192x208 小尺寸下仍然可读，透明背景。
性格：安静、专注、温和、略带科技感，适合陪伴用户学习。
设计：原创发型，不要双马尾，不要 Hatsune Miku 轮廓，不要 Vocaloid 服装。
服装：简单短外套或小披肩，带少量学习主题细节；可加入一个小型 AI 终端配件，例如耳机、发光胸针或悬浮书签。
配色：奶白、浅蓝灰、低饱和浅紫灰、暖黄色点缀，少量青蓝发光细节。
不要文字、不要 logo、不要场景、不要地面阴影、不要网格。
```

## 逐行动画 Prompt

```text
基于已经确认的原创角色设计，生成一条横向 sprite 动画 strip。
准确帧数：{frame_count}。
每一帧都必须适配一个 192x208 的透明单格。
同一个角色、同一套服装、同一个发型、同一套配色、同一比例、同一个配件。
动作：{motion_description}。
二次元 Q 版像素桌宠风格，清晰深色描边，无文字、无网格、无场景、无地面阴影。
避免 Hatsune Miku 特征：无青绿色双马尾、无 Vocaloid 服装、无复制轮廓。
```

## 动作描述

```text
idle：安静站立，轻微呼吸和眨眼。
waving：小幅友好挥手，适合轻触回应或收到礼物。
review：专注学习姿势，看着小便签或小屏幕，表现认真思考。
jumping：小幅开心跳跃，情绪明亮，但不越出单格。
waiting：平静坐下或休息姿态，适合安抚和休息。
failed：疲惫、过载或轻微拒绝，姿态下沉。
running-right：侧向朝右小跑。
running-left：侧向朝左小跑。
running：原地活跃移动或被提起时的动态姿态。
```
```

- [ ] **Step 3: 验证文档没有英文模板残留**

Run: `Select-String -Path docs/art/*.md -Pattern 'Implementation Plan|Non-Goals|未决事项' -CaseSensitive:$false`

Expected: no output.

- [ ] **Step 4: Commit**

```powershell
git add docs/art/art_direction.md docs/art/prompt_templates.md
git commit -m "docs: add Chinese art direction prompts"
```

---

### Task 2: 增加 atlas QA 脚本

**Files:**
- Modify: `pyproject.toml`
- Create: `tools/art/validate_companion_atlas.py`
- Create: `tests/test_art_tools.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_art_tools.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from tools.art.validate_companion_atlas import validate_atlas


def write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "sheet_columns": 8,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {
                    "Default": {"row": 0, "frame_count": 6, "fps": 4},
                    "TouchHead": {"row": 3, "frame_count": 4, "fps": 6},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_validate_atlas_accepts_valid_8x9_rgba_sheet(tmp_path: Path):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(atlas)
    write_manifest(manifest)

    report = validate_atlas(atlas, manifest)

    assert report.ok is True
    assert report.errors == []
    assert report.width == 1536
    assert report.height == 1872


def test_validate_atlas_reports_wrong_size(tmp_path: Path):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(atlas)
    write_manifest(manifest)

    report = validate_atlas(atlas, manifest)

    assert report.ok is False
    assert "atlas size must be 1536x1872, got 100x100" in report.errors
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_art_tools.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'tools'`.

- [ ] **Step 3: 增加 Pillow 依赖**

Modify `pyproject.toml` dependency line:

```toml
dependencies = ["PySide6==6.11.0", "Pillow>=12.1.0"]
```

- [ ] **Step 4: 实现 QA 脚本**

Create `tools/art/validate_companion_atlas.py`:

```python
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


EXPECTED_COLUMNS = 8
EXPECTED_ROWS = 9
EXPECTED_FRAME_WIDTH = 192
EXPECTED_FRAME_HEIGHT = 208
EXPECTED_WIDTH = EXPECTED_COLUMNS * EXPECTED_FRAME_WIDTH
EXPECTED_HEIGHT = EXPECTED_ROWS * EXPECTED_FRAME_HEIGHT


@dataclass(frozen=True, slots=True)
class AtlasValidationReport:
    ok: bool
    width: int
    height: int
    mode: str
    errors: list[str]


def validate_atlas(atlas_path: Path | str, manifest_path: Path | str) -> AtlasValidationReport:
    atlas = Path(atlas_path)
    manifest = Path(manifest_path)
    errors: list[str] = []

    if not atlas.exists():
        return AtlasValidationReport(False, 0, 0, "", [f"atlas not found: {atlas}"])
    if not manifest.exists():
        return AtlasValidationReport(False, 0, 0, "", [f"manifest not found: {manifest}"])

    with Image.open(atlas) as image:
        width, height = image.size
        mode = image.mode

    if (width, height) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        errors.append(f"atlas size must be 1536x1872, got {width}x{height}")
    if mode != "RGBA":
        errors.append(f"atlas mode must be RGBA, got {mode}")

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("sheet_columns") != EXPECTED_COLUMNS:
        errors.append(f"sheet_columns must be 8, got {payload.get('sheet_columns')}")
    if payload.get("sheet_rows") != EXPECTED_ROWS:
        errors.append(f"sheet_rows must be 9, got {payload.get('sheet_rows')}")
    if payload.get("frame_width") != EXPECTED_FRAME_WIDTH:
        errors.append(f"frame_width must be 192, got {payload.get('frame_width')}")
    if payload.get("frame_height") != EXPECTED_FRAME_HEIGHT:
        errors.append(f"frame_height must be 208, got {payload.get('frame_height')}")

    for name, motion in payload.get("motions", {}).items():
        row = motion.get("row")
        frame_count = motion.get("frame_count")
        if not isinstance(row, int) or row < 0 or row >= EXPECTED_ROWS:
            errors.append(f"{name}.row must be between 0 and 8, got {row}")
        if not isinstance(frame_count, int) or frame_count < 1 or frame_count > EXPECTED_COLUMNS:
            errors.append(f"{name}.frame_count must be between 1 and 8, got {frame_count}")

    return AtlasValidationReport(not errors, width, height, mode, errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate companion atlas geometry.")
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    report = validate_atlas(args.atlas, args.manifest)
    if report.ok:
        print(f"OK atlas {report.width}x{report.height} {report.mode}")
        return 0
    for error in report.errors:
        print(f"ERROR {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_art_tools.py -v`

Expected: 2 passed.

- [ ] **Step 6: 用当前资源跑命令行 QA**

Run:

```powershell
python tools/art/validate_companion_atlas.py --atlas assets/companion/original_oc/spritesheet.png --manifest assets/companion/original_oc/motion_manifest.json
```

Expected: `OK atlas 1536x1872 RGBA`.

- [ ] **Step 7: Commit**

```powershell
git add pyproject.toml tools/art/validate_companion_atlas.py tests/test_art_tools.py
git commit -m "test: add companion atlas validation"
```

---

### Task 3: 增加 contact sheet 和 GIF 预览脚本

**Files:**
- Modify: `tools/art/build_companion_preview.py`
- Modify: `tests/test_art_tools.py`

- [ ] **Step 1: 写失败测试**

Append to `tests/test_art_tools.py`:

```python
from tools.art.build_companion_preview import build_previews


def test_build_previews_writes_contact_sheet_and_gifs(tmp_path: Path):
    atlas = tmp_path / "spritesheet.webp"
    manifest = tmp_path / "motion_manifest.json"
    output = tmp_path / "preview"
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(atlas)
    write_manifest(manifest)

    generated = build_previews(atlas, manifest, output)

    assert output.joinpath("contact-sheet.png").exists()
    assert output.joinpath("gifs", "Default.gif").exists()
    assert output.joinpath("gifs", "TouchHead.gif").exists()
    assert "contact-sheet.png" in {path.name for path in generated}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_art_tools.py::test_build_previews_writes_contact_sheet_and_gifs -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'tools.art.build_companion_preview'`.

- [ ] **Step 3: 实现预览脚本**

Create `tools/art/build_companion_preview.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def build_previews(atlas_path: Path | str, manifest_path: Path | str, output_dir: Path | str) -> list[Path]:
    atlas = Path(atlas_path)
    manifest = Path(manifest_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    gif_dir = output / "gifs"
    gif_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    frame_width = int(payload["frame_width"])
    frame_height = int(payload["frame_height"])
    columns = int(payload["sheet_columns"])
    rows = int(payload["sheet_rows"])
    generated: list[Path] = []

    with Image.open(atlas) as source:
        sheet = source.convert("RGBA")

    contact = sheet.copy()
    draw = ImageDraw.Draw(contact)
    for x in range(0, columns * frame_width + 1, frame_width):
        draw.line((x, 0, x, rows * frame_height), fill=(255, 64, 64, 180), width=2)
    for y in range(0, rows * frame_height + 1, frame_height):
        draw.line((0, y, columns * frame_width, y), fill=(255, 64, 64, 180), width=2)
    contact_path = output / "contact-sheet.png"
    contact.save(contact_path)
    generated.append(contact_path)

    for name, motion in payload["motions"].items():
        row = int(motion["row"])
        frame_count = int(motion["frame_count"])
        fps = max(int(motion.get("fps", 6)), 1)
        frames = [
            sheet.crop((index * frame_width, row * frame_height, (index + 1) * frame_width, (row + 1) * frame_height))
            for index in range(frame_count)
        ]
        gif_path = gif_dir / f"{name}.gif"
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=max(int(1000 / fps), 16),
            loop=0,
            optimize=True,
        )
        generated.append(gif_path)

    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description="Build companion atlas preview files.")
    parser.add_argument("--atlas", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    generated = build_previews(args.atlas, args.manifest, args.output)
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_art_tools.py -v`

Expected: 3 passed.

- [ ] **Step 5: 为当前资源生成预览**

Run:

```powershell
python tools/art/build_companion_preview.py --atlas assets/companion/original_oc/spritesheet.png --manifest assets/companion/original_oc/motion_manifest.json --output assets/companion/original_oc/preview
```

Expected: prints `contact-sheet.png` and GIF paths under `assets/companion/original_oc/preview`.

- [ ] **Step 6: Commit**

```powershell
git add tools/art/build_companion_preview.py tests/test_art_tools.py assets/companion/original_oc/preview
git commit -m "feat: add companion atlas previews"
```

---

### Task 4: 让 MotionLayer 读取角色配置中的 spritesheet 文件名

**Files:**
- Modify: `src/guanghe_companion/character_pack.py`
- Modify: `src/guanghe_companion/motion.py`
- Modify: `tests/test_character_pack.py`
- Modify: `tests/test_motion.py`

- [ ] **Step 1: 写失败测试**

Modify `tests/test_character_pack.py`:

```python
def test_load_default_character_pack_reads_spritesheet_filename():
    pack = load_default_character_pack()

    assert pack.spritesheet == "spritesheet.png"
```

Modify `tests/test_motion.py`:

```python
def test_motion_catalog_uses_spritesheet_from_character_pack():
    catalog = load_default_motion_catalog()

    assert catalog.sheet_path.name == "spritesheet.png"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
pytest tests/test_character_pack.py::test_load_default_character_pack_reads_spritesheet_filename tests/test_motion.py::test_motion_catalog_uses_spritesheet_from_character_pack -v
```

Expected: first test fails with `AttributeError: 'CharacterPack' object has no attribute 'spritesheet'`.

- [ ] **Step 3: 修改 CharacterPack**

In `src/guanghe_companion/character_pack.py`, update dataclass:

```python
@dataclass(frozen=True, slots=True)
class CharacterPack:
    character_id: str
    name: str
    title: str
    description: str
    spritesheet: str
    default_mode: str
    modes: tuple[str, ...]
    mode_descriptions: dict[str, str]
    motion_labels: dict[str, str]
```

Update `load_character_pack` return:

```python
    return CharacterPack(
        character_id=payload["character_id"],
        name=payload["name"],
        title=payload["title"],
        description=payload["description"],
        spritesheet=payload["spritesheet"],
        default_mode=payload["default_mode"],
        modes=tuple(payload["modes"]),
        mode_descriptions=dict(payload["mode_descriptions"]),
        motion_labels=dict(payload["motion_labels"]),
    )
```

- [ ] **Step 4: 修改 MotionLayer**

In `src/guanghe_companion/motion.py`, change imports:

```python
from .character_pack import ASSETS_ROOT, DEFAULT_CHARACTER_ID, load_character_pack
```

In `load_motion_catalog`, use:

```python
    pack = load_character_pack(character_id)
    asset_dir = ASSETS_ROOT / character_id
    manifest_path = asset_dir / "motion_manifest.json"
```

And return:

```python
        sheet_path=asset_dir / pack.spritesheet,
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```powershell
pytest tests/test_character_pack.py tests/test_motion.py -v
```

Expected: all tests in both files pass.

- [ ] **Step 6: Commit**

```powershell
git add src/guanghe_companion/character_pack.py src/guanghe_companion/motion.py tests/test_character_pack.py tests/test_motion.py
git commit -m "feat: load spritesheet path from character pack"
```

---

### Task 5: 全量验证和交付检查

**Files:**
- No source changes expected.

- [ ] **Step 1: 运行完整测试**

Run: `pytest`

Expected: 27 tests pass after Tasks 1-4.

- [ ] **Step 2: 运行控制台 demo**

Run: `python run_demo.py`

Expected output includes:

```text
轻触 -> 我记录下来了。这不是指令，是你靠近我的方式。
共同学习 -> 获得 8 coins / 8 exp
商店购买 -> 热牛奶 入背包
背包使用 -> 投喂热牛奶
```

- [ ] **Step 3: 运行 PySide6 offscreen smoke**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
@'
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
ROOT = Path.cwd()
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from guanghe_companion.app import CompanionWindow
from guanghe_companion.controller import CompanionController

with TemporaryDirectory() as tmp:
    app = QApplication.instance() or QApplication([])
    controller = CompanionController(save_path=Path(tmp) / 'smoke-save.json', auto_load=False)
    window = CompanionWindow(controller=controller)
    window.show()
    QTimer.singleShot(100, app.quit)
    exit_code = app.exec()
    snapshot = controller.get_snapshot()
    print({
        'exit_code': exit_code,
        'window_title': window.windowTitle(),
        'actions': len(snapshot['actions']),
        'shop_items': len(snapshot['shop_items']),
        'inventory_items': len(snapshot['inventory_items']),
        'motion': snapshot['motion'],
    })
'@ | python -
```

Expected output includes:

```text
'exit_code': 0
'actions': 6
'shop_items': 8
'inventory_items': 8
```

- [ ] **Step 4: 检查 git 状态**

Run: `git status --short`

Expected: no output.

---

## 自检

- Spec 覆盖：本计划覆盖中文美术说明、prompt 模板、QA 脚本、预览脚本、MotionLayer 配置化读取 spritesheet 文件名。
- 范围控制：本计划不实际生成正式角色图，不替换当前运行资源，只先建立资源管线。
- 文档语言：新增面向项目的 `.md` 文档均为中文。
- 外部文档：Pillow API 已按 AGENTS.md 使用 `ctx7` 查询；计划中的 GIF 生成使用 `save_all=True`、`append_images`、`duration`、`loop=0`，图像合成使用 `paste/crop/save` 这类 Pillow 基础接口。
