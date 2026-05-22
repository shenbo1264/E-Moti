# 星汐功能对齐 Shinsekai 参考项目补齐计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不复制 Shinsekai 角色、美术和 IP 的前提下，补齐 E-Moti 作为“可养成 AI 桌面伴侣电子宠物”的核心功能链，让星汐具备设置中心、桌面演出窗口、文本对话、历史、配置、插件/工具接口和受控表达增强能力。

**Architecture:** 采用“本地养成状态机 + 受控表达层 + PySide 双窗口”的架构。Shinsekai 可作为代码参考库：优先复用或改写其消息解析、历史管理、配置表单、插件宿主、聊天窗口工具栏等成熟模块；但 E-Moti 的状态、背包、关系、动作、存档仍由现有 typed snapshot/events 和 controller/service 边界决定。

**Tech Stack:** Python 3.11、PySide6、pytest、PyInstaller、Inno Setup、JSON/YAML 配置文件、本地 `%LOCALAPPDATA%\E-Moti` 运行数据目录。

---

## 当前核对结论

本计划基于 2026-05-22 对当前仓库和参考项目的读取，不依赖未验证记忆。

当前 E-Moti 已具备：

- 原创 OC “星汐”角色包、spritesheet、动作 manifest、商店物品。
- 本地状态机：focus / charge / stability / mood / trust。
- typed snapshot/events：`CompanionSnapshot`、`CompanionEvent`、`EventValidator`、`DomainEventComposer`。
- 控制面板与独立桌宠窗口。
- 背包、商店、关系解锁、回忆、主动陪伴。
- `ShinsekaiAIExpressor` 雏形、OpenAI client、fallback 与字段边界测试。
- Windows 安装器、控制面板/桌宠快捷方式。

当前缺口：

- 没有真正的聊天输入窗口，桌宠窗口还不是“可对话演出窗口”。
- 没有保存/加载对话历史、回溯、清屏、复制历史。
- 没有用户可配置的 LLM/TTS/ASR 设置页。
- 没有 Shinsekai 式模板/规则生成页，但 E-Moti 不需要完整角色卡系统。
- 没有插件宿主和工具贡献接口。
- TTS/ASR 不应作为当前 P0，但需要预留适配接口。
- 屏幕感知目前只有手动隐私提示和只读摘要锚点，不能做自动后台观察。

参考项目可复用/改写的模块：

- `core/messaging/stream_parser.py`：流式 JSON 对象切分与解析思路。
- `core/messaging/dialog_tokens.py`：系统角色名 token 规范，适合改成 E-Moti typed events 的 token adapter。
- `core/sprite/chat_history.py`：历史保存、复制、回放、回溯的流程。
- `core/sprite/chat_ui_service.py`：窗口与会话、历史、插件贡献的桥接模式。
- `core/plugins/plugin_host.py`：插件 manifest、启用/禁用、贡献收集的宿主模式。
- `ui/chat_ui/desktop_toolbar.py`、`desktop_menu.py`、`busy_bar.py`、`rounded_chrome_button.py`：聊天/桌面窗口 chrome 与菜单组件思路。
- `ui/settings_ui/widgets/segmented_tab_nav.py`：按钮式分页导航。
- `ui/settings_ui/tabs/api_tab.py`、`plugin_tab.py`、`template_tab.py`：设置页结构和表单布局可参考，但不直接搬完整业务。

不可复用的内容：

- Shinsekai 的角色设定、示例角色、立绘、美术、语音素材、剧情模板文案。
- 完整 LLM/TTS/ASR/MCP 主体架构，除非对应阶段明确进入。
- 能让 LLM 修改状态、背包、关系、回忆、存档的路径。

---

## 目标功能对齐矩阵

| 功能域 | Shinsekai 参考能力 | E-Moti 对齐目标 | 优先级 |
|---|---|---|---|
| 设置中心 | API、人物、背景、模板、插件、工具 | 控制中心分为总览、AI 表达、角色包、背包/商店、插件/工具、隐私 | P0-P2 |
| 桌面演出窗口 | 立绘、对话框、输入栏、选项、工具栏 | 桌宠窗口升级为可输入、可反馈、可返回面板的演出窗口 | P0 |
| 消息解析 | LLM JSON 流式解析 | 接受 JSON speech event，转换为 typed event，非法则 fallback | P0 |
| 聊天历史 | 保存、清空、复制、回溯 | 保存星汐对话和动作事件，不污染养成状态 | P1 |
| LLM 配置 | provider/model/key/base_url | 用户可开关表达增强，默认无 key 可跑 | P1 |
| TTS/ASR | 多 provider | 只预留接口和关闭状态，真实 TTS/ASR 后置 | P3 |
| 插件 | manifest、贡献 UI/tools/providers | 先支持只读工具结果和 UI 贡献，不支持任意改状态 | P2 |
| 模板 | 角色模板与规则生成 | 固定“星汐表达规则”编辑/预览，不做通用角色卡平台 | P1 |

---

## 文件结构规划

### 新增文件

- `src/guanghe_companion/dialogue.py`
  - 星汐聊天输入请求、聊天输出消息、对话历史 row 的 typed 数据结构。

- `src/guanghe_companion/dialogue_history.py`
  - 保存/加载/清空/复制/回放对话历史，只处理表达历史，不改 `CompanionState`。

- `src/guanghe_companion/dialogue_parser.py`
  - 改写 Shinsekai `LlmResponseStreamParser` 思路，输出 E-Moti typed speech event。

- `src/guanghe_companion/settings.py`
  - 用户配置数据结构：表达增强开关、provider、model、base_url、timeout、TTS/ASR disabled 状态。

- `src/guanghe_companion/settings_storage.py`
  - 配置保存到 `%LOCALAPPDATA%\E-Moti\settings.json`，源码运行也不写仓库默认配置。

- `src/guanghe_companion/plugin_host.py`
  - 轻量插件 manifest 读取与贡献收集，第一版只支持安全 UI/tool 描述。

- `tests/test_dialogue.py`
  - 聊天请求、解析、history、状态不可变回归测试。

- `tests/test_settings.py`
  - 设置读写、旧配置迁移、坏 JSON fallback 测试。

- `tests/test_plugin_host.py`
  - 插件 manifest 解析、禁用、坏 entry 降级测试。

### 修改文件

- `src/guanghe_companion/app.py`
  - 桌宠窗口增加底部输入栏、反馈气泡、历史菜单入口、设置中心页面。

- `src/guanghe_companion/controller.py`
  - 新增 `submit_dialogue_request()`，只走表达层和 typed events，不改状态数值。

- `src/guanghe_companion/ai_expressor.py`
  - 复用现有 `ExpressionRequest`，增加配置驱动 client 构造，保留默认 disabled/fallback。

- `src/guanghe_companion/events.py`
  - 如需补充 dialogue event payload 字段，只通过 typed schema 扩展。

- `src/guanghe_companion/runtime_paths.py`
  - 增加 settings/history/plugin manifest 路径 helper。

- `tests/test_app.py`
  - 桌宠输入栏、菜单、设置页、history smoke。

- `tests/test_controller.py`
  - 对话输入不改变状态、不改背包、不绕过 events。

- `packaging/e-moti-installer.iss`
  - 如新增默认插件/配置样例，只安装到 app 目录，不写仓库 data。

---

## 阶段 0：功能边界锁定

**目标：** 先锁住“参考 Shinsekai 但不复制业务主体”的边界，避免后续把 LLM/TTS/ASR/插件混成大改。

**Files:**

- Modify: `docs/superpowers/plans/2026-05-22-shinsekai-function-parity-plan.md`

- [ ] **Step 1: 执行基线核对**

Run:

```powershell
git status --short --untracked-files=all
git log --oneline --decorate -5
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
```

Expected:

- 只允许 `data/companion_save.json` 之类运行存档差异存在。
- pytest 全量通过。
- JSON 校验通过。

- [ ] **Step 2: 只读核对参考模块**

Run:

```powershell
rg --files "D:\学工文档\光核\电子宠物\首选\_Shinsekai_latest\core\messaging" "D:\学工文档\光核\电子宠物\首选\_Shinsekai_latest\core\sprite" "D:\学工文档\光核\电子宠物\首选\_Shinsekai_latest\ui\chat_ui" "D:\学工文档\光核\电子宠物\首选\_Shinsekai_latest\core\plugins"
```

Expected:

- 只读参考，不改参考项目文件。
- 记录可复用模块和不可复用边界。

- [ ] **Step 3: Commit**

如果本阶段只更新计划文档：

```powershell
git add docs\superpowers\plans\2026-05-22-shinsekai-function-parity-plan.md
git commit -m "docs: plan shinsekai function parity"
```

---

## 阶段 1：桌宠演出窗口输入与对话事件

**目标：** 让桌宠模式不只是一个 sprite，而是能接收用户输入、显示星汐回复、显示选项/状态摘要的桌面演出窗口。第一版不接真实 LLM，默认使用本地 fallback 和现有 `ShinsekaiAIExpressor` mock。

**Files:**

- Create: `src/guanghe_companion/dialogue.py`
- Modify: `src/guanghe_companion/controller.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_dialogue.py`
- Test: `tests/test_app.py`
- Test: `tests/test_controller.py`

- [ ] **Step 1: 写失败测试：对话输入不改变养成状态**

Add to `tests/test_dialogue.py`:

```python
def test_dialogue_request_generates_speech_without_mutating_state(tmp_path):
    from guanghe_companion.controller import CompanionController
    from guanghe_companion.dialogue import DialogueRequest

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    before = controller.get_typed_snapshot()

    snapshot = controller.submit_dialogue_request(DialogueRequest(text="今天想陪你待一会儿。"))

    after = controller.get_typed_snapshot()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert snapshot["events"][0]["character_name"] == "星汐"
    assert "今天想陪你待一会儿" in snapshot["events"][0]["speech"]
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
python -m pytest tests\test_dialogue.py::test_dialogue_request_generates_speech_without_mutating_state -q
```

Expected:

- FAIL，原因是 `guanghe_companion.dialogue` 或 `submit_dialogue_request` 不存在。

- [ ] **Step 3: 新增最小 typed dialogue 模型**

Create `src/guanghe_companion/dialogue.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


MAX_DIALOGUE_INPUT_LENGTH = 240


@dataclass(frozen=True, slots=True)
class DialogueRequest:
    text: str
    source: str = "desktop_pet"

    def normalized_text(self) -> str:
        return self.text.strip()[:MAX_DIALOGUE_INPUT_LENGTH]
```

- [ ] **Step 4: 在 controller 中增加只表达不结算的入口**

Add to `src/guanghe_companion/controller.py`:

```python
    def submit_dialogue_request(self, request: DialogueRequest, *, include_ai_expression: bool = True) -> dict[str, object]:
        text = request.normalized_text()
        if not text:
            self.last_motion = "Default"
            self.last_feedback = "我在。你可以慢慢说。"
        else:
            self.last_motion = "Default"
            self.last_feedback = f"我听见了：{text}"
        self.last_delta_text = "对话输入不改变状态"
        self.last_allowed = True
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
        self.last_events = self._build_events(effect="ATTENTION", include_ai_expression=include_ai_expression)
        self._persist()
        return self.get_snapshot()
```

Also import:

```python
from .dialogue import DialogueRequest
```

- [ ] **Step 5: 运行测试转绿**

Run:

```powershell
python -m pytest tests\test_dialogue.py tests\test_controller.py -q
```

Expected:

- PASS。

- [ ] **Step 6: 写失败测试：桌宠窗口有输入栏和发送按钮**

Add to `tests/test_app.py`:

```python
def test_desktop_pet_has_dialogue_input_and_send_button(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication
    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    assert window.dialogue_input.placeholderText() == "和星汐说点什么"
    assert window.dialogue_send_button.text() == "发送"

    window.close()
    app.processEvents()
```

- [ ] **Step 7: 运行失败测试**

Run:

```powershell
python -m pytest tests\test_app.py::test_desktop_pet_has_dialogue_input_and_send_button -q
```

Expected:

- FAIL，原因是 `dialogue_input` 不存在。

- [ ] **Step 8: 最小实现输入栏**

Modify `src/guanghe_companion/app.py`：

- 为桌宠模式增加 `QLineEdit` 和 `QPushButton`。
- 发送后调用 `controller.submit_dialogue_request(DialogueRequest(text=...))`。
- 桌宠窗口仍默认透明、置顶、可右键返回。
- 不在此阶段接 TTS。

- [ ] **Step 9: 运行 UI 定向测试**

Run:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
```

Expected:

- PASS。

- [ ] **Step 10: Commit**

```powershell
git add src\guanghe_companion\dialogue.py src\guanghe_companion\controller.py src\guanghe_companion\app.py tests\test_dialogue.py tests\test_controller.py tests\test_app.py
git commit -m "feat: add desktop pet dialogue input"
```

---

## 阶段 2：Shinsekai 式 JSON 消息解析适配

**目标：** 合理沿用 Shinsekai `LlmResponseStreamParser` 的思路，改成 E-Moti 的 typed event parser。LLM 输出只能进入 `speech` 表达事件，不允许引入状态变更字段。

**Files:**

- Create: `src/guanghe_companion/dialogue_parser.py`
- Modify: `src/guanghe_companion/ai_expressor.py`
- Test: `tests/test_dialogue.py`
- Test: `tests/test_ai_expressor.py`

- [ ] **Step 1: 写失败测试：流式 JSON 可以解析为 speech event**

Add to `tests/test_dialogue.py`:

```python
def test_dialogue_stream_parser_yields_safe_speech_events():
    from guanghe_companion.dialogue_parser import DialogueStreamParser

    parser = DialogueStreamParser(character_name="星汐")

    first = list(parser.feed('[{"type":"speech",'))
    second = list(parser.feed('"speech":"我在这里。","effect":"ATTENTION"}]'))

    assert first == []
    assert len(second) == 1
    assert second[0]["character_name"] == "星汐"
    assert second[0]["speech"] == "我在这里。"
    assert second[0]["effect"] == "ATTENTION"
```

- [ ] **Step 2: 写失败测试：状态写入字段被拒绝**

Add:

```python
def test_dialogue_stream_parser_rejects_state_mutation_fields():
    from guanghe_companion.dialogue_parser import DialogueStreamParser

    parser = DialogueStreamParser(character_name="星汐")

    events = list(parser.feed('[{"type":"speech","speech":"给你加金币","coins":999}]'))

    assert events == []
    assert parser.last_error == "unsafe_fields"
```

- [ ] **Step 3: 运行失败测试**

Run:

```powershell
python -m pytest tests\test_dialogue.py -k "stream_parser" -q
```

Expected:

- FAIL，原因是 `DialogueStreamParser` 不存在。

- [ ] **Step 4: 实现 parser**

Create `src/guanghe_companion/dialogue_parser.py`:

```python
from __future__ import annotations

import json
from collections.abc import Iterator

ALLOWED_DIALOGUE_FIELDS = frozenset({"type", "speech", "effect", "motion_hint"})
ALLOWED_DIALOGUE_EFFECTS = frozenset({"ATTENTION", "DISAPPOINTED", "SWITCH", "OVERLOAD", "IDLE"})
MAX_DIALOGUE_SPEECH_LENGTH = 80


class DialogueStreamParser:
    def __init__(self, character_name: str) -> None:
        self.character_name = character_name
        self._buffer = ""
        self.accumulated_text = ""
        self.last_error: str | None = None

    def feed(self, chunk: str) -> Iterator[dict[str, str]]:
        if chunk:
            self._buffer += chunk
            self.accumulated_text += chunk
        yield from self._drain()

    def _drain(self) -> Iterator[dict[str, str]]:
        text = self._buffer.strip()
        if not text.endswith("]"):
            return
        self._buffer = ""
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            self.last_error = "invalid_json"
            return
        if not isinstance(payload, list):
            self.last_error = "invalid_payload"
            return
        for row in payload[:4]:
            event = self._normalize_row(row)
            if event is not None:
                yield event

    def _normalize_row(self, row: object) -> dict[str, str] | None:
        if not isinstance(row, dict):
            self.last_error = "invalid_row"
            return None
        if not set(row).issubset(ALLOWED_DIALOGUE_FIELDS):
            self.last_error = "unsafe_fields"
            return None
        if row.get("type") != "speech":
            self.last_error = "unsupported_type"
            return None
        speech = str(row.get("speech", "")).strip()[:MAX_DIALOGUE_SPEECH_LENGTH]
        if not speech:
            self.last_error = "empty_speech"
            return None
        effect = str(row.get("effect", "ATTENTION")).strip()
        if effect not in ALLOWED_DIALOGUE_EFFECTS:
            effect = "ATTENTION"
        event = {
            "character_name": self.character_name,
            "speech": speech,
            "sprite": "1",
            "effect": effect,
        }
        motion_hint = str(row.get("motion_hint", "")).strip()
        if motion_hint:
            event["motion_hint"] = motion_hint[:40]
        return event
```

- [ ] **Step 5: 运行测试转绿**

Run:

```powershell
python -m pytest tests\test_dialogue.py tests\test_ai_expressor.py -q
```

Expected:

- PASS。

- [ ] **Step 6: Commit**

```powershell
git add src\guanghe_companion\dialogue_parser.py src\guanghe_companion\ai_expressor.py tests\test_dialogue.py tests\test_ai_expressor.py
git commit -m "feat: add safe dialogue stream parser"
```

---

## 阶段 3：对话历史、清屏、复制、回溯

**目标：** 改写 Shinsekai `chat_history.py` 的流程，让星汐的对话/动作表达有历史，但不把历史当作状态机来源。

**Files:**

- Create: `src/guanghe_companion/dialogue_history.py`
- Modify: `src/guanghe_companion/runtime_paths.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_dialogue.py`
- Test: `tests/test_runtime_paths.py`

- [ ] **Step 1: 写失败测试：history 写入用户和星汐消息**

Add to `tests/test_dialogue.py`:

```python
def test_dialogue_history_saves_and_loads_rows(tmp_path):
    from guanghe_companion.dialogue_history import DialogueHistoryStore, DialogueHistoryRow

    store = DialogueHistoryStore(tmp_path / "history.json")
    store.append(DialogueHistoryRow(role="user", text="你好"))
    store.append(DialogueHistoryRow(role="xingxi", text="我在。"))

    loaded = store.load()

    assert [row.role for row in loaded] == ["user", "xingxi"]
    assert [row.text for row in loaded] == ["你好", "我在。"]
```

- [ ] **Step 2: 写失败测试：坏 history 文件降级为空**

Add:

```python
def test_dialogue_history_returns_empty_for_bad_json(tmp_path):
    from guanghe_companion.dialogue_history import DialogueHistoryStore

    path = tmp_path / "history.json"
    path.write_text("{bad", encoding="utf-8")

    assert DialogueHistoryStore(path).load() == []
```

- [ ] **Step 3: 运行失败测试**

Run:

```powershell
python -m pytest tests\test_dialogue.py -k "history" -q
```

Expected:

- FAIL，原因是 history 模块不存在。

- [ ] **Step 4: 实现 history store**

Create `src/guanghe_companion/dialogue_history.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DialogueHistoryRow:
    role: str
    text: str


class DialogueHistoryStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> list[DialogueHistoryRow]:
        if not self.path.is_file():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        rows: list[DialogueHistoryRow] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip()
            text = str(item.get("text", "")).strip()
            if role in {"user", "xingxi", "system"} and text:
                rows.append(DialogueHistoryRow(role=role, text=text))
        return rows[-100:]

    def append(self, row: DialogueHistoryRow) -> None:
        rows = self.load()
        rows.append(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(entry) for entry in rows[-100:]], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("[]", encoding="utf-8")
```

- [ ] **Step 5: runtime path 增加 history 路径**

Add to `src/guanghe_companion/runtime_paths.py`:

```python
def dialogue_history_path() -> Path:
    return user_data_dir() / "dialogue_history.json"
```

- [ ] **Step 6: UI 接入历史菜单**

Modify `src/guanghe_companion/app.py`：

- 右键菜单增加 `对话历史`、`清空对话`。
- 控制面板增加“历史”页或在“互动”页显示最近 10 条。
- `清空对话` 只清 history，不重置 `CompanionState`。

- [ ] **Step 7: 跑定向测试**

Run:

```powershell
python -m pytest tests\test_dialogue.py tests\test_runtime_paths.py tests\test_app.py -q
```

Expected:

- PASS。

- [ ] **Step 8: Commit**

```powershell
git add src\guanghe_companion\dialogue_history.py src\guanghe_companion\runtime_paths.py src\guanghe_companion\app.py tests\test_dialogue.py tests\test_runtime_paths.py tests\test_app.py
git commit -m "feat: add dialogue history"
```

---

## 阶段 4：设置中心与表达增强配置

**目标：** 对齐 Shinsekai 设置窗口的核心功能，但只保留 E-Moti 需要的最小设置：表达增强开关、provider、model、base_url、api_key、timeout、TTS/ASR 关闭状态。

**Files:**

- Create: `src/guanghe_companion/settings.py`
- Create: `src/guanghe_companion/settings_storage.py`
- Modify: `src/guanghe_companion/runtime_paths.py`
- Modify: `src/guanghe_companion/ai_expressor.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_settings.py`
- Test: `tests/test_ai_expressor.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: 写失败测试：默认设置禁用网络表达**

Add to `tests/test_settings.py`:

```python
def test_default_settings_disable_network_expression():
    from guanghe_companion.settings import CompanionSettings

    settings = CompanionSettings()

    assert settings.expression_enabled is False
    assert settings.llm_provider == "disabled"
    assert settings.tts_provider == "disabled"
    assert settings.asr_provider == "disabled"
```

- [ ] **Step 2: 写失败测试：配置保存到用户目录**

Add:

```python
def test_settings_store_round_trips_json(tmp_path):
    from guanghe_companion.settings import CompanionSettings
    from guanghe_companion.settings_storage import SettingsStore

    store = SettingsStore(tmp_path / "settings.json")
    store.save(CompanionSettings(expression_enabled=True, llm_provider="openai", model="gpt-5.5"))

    loaded = store.load()

    assert loaded.expression_enabled is True
    assert loaded.llm_provider == "openai"
    assert loaded.model == "gpt-5.5"
```

- [ ] **Step 3: 运行失败测试**

Run:

```powershell
python -m pytest tests\test_settings.py -q
```

Expected:

- FAIL，原因是 settings 模块不存在。

- [ ] **Step 4: 实现 settings 模型和 store**

Create `src/guanghe_companion/settings.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompanionSettings:
    expression_enabled: bool = False
    llm_provider: str = "disabled"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    timeout_seconds: float = 2.0
    tts_provider: str = "disabled"
    asr_provider: str = "disabled"
```

Create `src/guanghe_companion/settings_storage.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .settings import CompanionSettings


class SettingsStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> CompanionSettings:
        if not self.path.is_file():
            return CompanionSettings()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return CompanionSettings()
        if not isinstance(payload, dict):
            return CompanionSettings()
        allowed = {field: payload[field] for field in asdict(CompanionSettings()) if field in payload}
        return CompanionSettings(**allowed)

    def save(self, settings: CompanionSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 5: 设置中心 UI**

Modify `src/guanghe_companion/app.py`：

- 左侧导航增加 `AI 表达`。
- 页面包含 `启用表达增强`、provider、model、base_url、api_key、timeout。
- TTS/ASR 显示为 `暂未启用`，不要假装完成。
- 保存后写 `%LOCALAPPDATA%\E-Moti\settings.json`。

- [ ] **Step 6: ai_expressor 配置驱动**

Modify `src/guanghe_companion/ai_expressor.py`：

- 新增 `build_ai_expressor_from_settings(settings)`。
- `expression_enabled=False` 或 provider disabled 时返回 `ShinsekaiAIExpressor(enabled=False)`。
- `openai` provider 才构造 `OpenAIResponsesClient`。

- [ ] **Step 7: 跑测试**

Run:

```powershell
python -m pytest tests\test_settings.py tests\test_ai_expressor.py tests\test_app.py -q
```

Expected:

- PASS。

- [ ] **Step 8: Commit**

```powershell
git add src\guanghe_companion\settings.py src\guanghe_companion\settings_storage.py src\guanghe_companion\runtime_paths.py src\guanghe_companion\ai_expressor.py src\guanghe_companion\app.py tests\test_settings.py tests\test_ai_expressor.py tests\test_app.py
git commit -m "feat: add expression settings"
```

---

## 阶段 5：模板/规则预览页

**目标：** 对齐 Shinsekai 的“聊天模板”概念，但不做通用角色卡平台。E-Moti 第一版只提供“星汐表达规则预览”和“重置为默认规则”，用于解释 LLM 表达边界。

**Files:**

- Modify: `src/guanghe_companion/ai_expressor.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_ai_expressor.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: 写失败测试：prompt 包含不可改状态边界**

Add to `tests/test_ai_expressor.py`:

```python
def test_expression_prompt_preview_states_local_authority():
    from guanghe_companion.ai_expressor import build_expression_prompt_preview

    preview = build_expression_prompt_preview(character_name="星汐")

    assert "AI 只能生成表达事件" in preview
    assert "不能修改状态数值" in preview
    assert "背包" in preview
    assert "星汐" in preview
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
python -m pytest tests\test_ai_expressor.py::test_expression_prompt_preview_states_local_authority -q
```

Expected:

- FAIL，函数不存在。

- [ ] **Step 3: 实现 prompt preview**

Add to `src/guanghe_companion/ai_expressor.py`:

```python
def build_expression_prompt_preview(character_name: str = "星汐") -> str:
    return "\n".join(
        [
            f"角色：{character_name}",
            "AI 只能生成表达事件，不能修改状态数值、动作结果、目标、解锁、背包或存档。",
            "输出必须是 JSON 数组，每个对象只允许 type、speech、effect、motion_hint。",
            "STAT 和 CHOICE 由本地系统生成，AI 不得编造状态和选项。",
        ]
    )
```

- [ ] **Step 4: UI 增加规则预览页**

Modify `src/guanghe_companion/app.py`：

- 左侧导航增加 `表达规则`。
- 右侧只读显示 preview。
- 按钮 `复制规则` 可复制到剪贴板。

- [ ] **Step 5: 跑测试**

Run:

```powershell
python -m pytest tests\test_ai_expressor.py tests\test_app.py -q
```

Expected:

- PASS。

- [ ] **Step 6: Commit**

```powershell
git add src\guanghe_companion\ai_expressor.py src\guanghe_companion\app.py tests\test_ai_expressor.py tests\test_app.py
git commit -m "feat: add expression rule preview"
```

---

## 阶段 6：轻量插件与工具贡献宿主

**目标：** 借鉴 Shinsekai `plugin_host.py`，但第一版只支持安全、只读、可禁用的插件 manifest。插件不能直接写状态、背包、关系或存档。

**Files:**

- Create: `src/guanghe_companion/plugin_host.py`
- Modify: `src/guanghe_companion/runtime_paths.py`
- Modify: `src/guanghe_companion/expression_context.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_plugin_host.py`
- Test: `tests/test_expression_context.py`

- [ ] **Step 1: 写失败测试：manifest 解析 enabled 插件**

Add to `tests/test_plugin_host.py`:

```python
def test_plugin_manifest_reads_enabled_tool_contributions(tmp_path):
    from guanghe_companion.plugin_host import PluginManifestStore

    manifest = tmp_path / "plugins.json"
    manifest.write_text(
        '[{"id":"local_notes","enabled":true,"kind":"tool","title":"本地资料","summary":"只读资料摘要"}]',
        encoding="utf-8",
    )

    store = PluginManifestStore(manifest)

    assert store.enabled_tool_results() == [
        {"source": "plugin:local_notes", "title": "本地资料", "summary": "只读资料摘要"}
    ]
```

- [ ] **Step 2: 写失败测试：禁用插件不进入表达上下文**

Add:

```python
def test_plugin_manifest_ignores_disabled_entries(tmp_path):
    from guanghe_companion.plugin_host import PluginManifestStore

    manifest = tmp_path / "plugins.json"
    manifest.write_text(
        '[{"id":"x","enabled":false,"kind":"tool","title":"X","summary":"Y"}]',
        encoding="utf-8",
    )

    assert PluginManifestStore(manifest).enabled_tool_results() == []
```

- [ ] **Step 3: 运行失败测试**

Run:

```powershell
python -m pytest tests\test_plugin_host.py -q
```

Expected:

- FAIL，模块不存在。

- [ ] **Step 4: 实现轻量 plugin manifest**

Create `src/guanghe_companion/plugin_host.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


class PluginManifestStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> list[dict[str, object]]:
        if not self.path.is_file():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        return [dict(row) for row in payload if isinstance(row, dict)]

    def enabled_tool_results(self) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        for row in self.load():
            if row.get("enabled") is not True or row.get("kind") != "tool":
                continue
            plugin_id = str(row.get("id", "")).strip()
            title = str(row.get("title", "")).strip()
            summary = str(row.get("summary", "")).strip()
            if plugin_id and title and summary:
                results.append({"source": f"plugin:{plugin_id}", "title": title[:80], "summary": summary[:180]})
        return results[:3]
```

- [ ] **Step 5: 接入 expression_context**

Modify `src/guanghe_companion/expression_context.py`：

- 增加 `PluginToolResultsExpressionContextProvider`。
- 输出只放入 `tool_results`。
- 不允许插件返回状态变更。

- [ ] **Step 6: 设置中心增加插件页**

Modify `src/guanghe_companion/app.py`：

- 左侧导航增加 `插件`。
- 第一版只显示 manifest rows、启用状态和摘要。
- 不做在线发现、下载、依赖安装。

- [ ] **Step 7: 跑测试**

Run:

```powershell
python -m pytest tests\test_plugin_host.py tests\test_expression_context.py tests\test_app.py -q
```

Expected:

- PASS。

- [ ] **Step 8: Commit**

```powershell
git add src\guanghe_companion\plugin_host.py src\guanghe_companion\runtime_paths.py src\guanghe_companion\expression_context.py src\guanghe_companion\app.py tests\test_plugin_host.py tests\test_expression_context.py tests\test_app.py
git commit -m "feat: add safe plugin manifest host"
```

---

## 阶段 7：TTS/ASR 预留，不做主体

**目标：** 对齐参考项目的功能入口，但避免在交付前把真实 TTS/ASR 混进当前大改。第一版只显示配置状态和接口边界。

**Files:**

- Modify: `src/guanghe_companion/settings.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_settings.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: 写测试：默认 TTS/ASR disabled**

Add to `tests/test_settings.py`:

```python
def test_voice_settings_are_explicitly_disabled_by_default():
    from guanghe_companion.settings import CompanionSettings

    settings = CompanionSettings()

    assert settings.tts_provider == "disabled"
    assert settings.asr_provider == "disabled"
```

- [ ] **Step 2: UI 显示“暂未启用”而非假功能**

Add to `tests/test_app.py`:

```python
def test_voice_settings_page_marks_tts_as_not_enabled(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window.navigation_buttons_by_id["voice"].click()
    app.processEvents()

    assert "TTS 暂未启用" in window.voice_status_label.text()
    assert "ASR 暂未启用" in window.voice_status_label.text()

    window.close()
    app.processEvents()
```

- [ ] **Step 3: 实现 UI 状态页**

Modify `src/guanghe_companion/app.py`：

- 新增 `语音` 页。
- 只显示 TTS/ASR 当前禁用和后续说明。
- 不启动本地服务、不下载模型、不录音。

- [ ] **Step 4: 跑测试和提交**

Run:

```powershell
python -m pytest tests\test_settings.py tests\test_app.py -q
```

Commit:

```powershell
git add src\guanghe_companion\settings.py src\guanghe_companion\app.py tests\test_settings.py tests\test_app.py
git commit -m "feat: expose disabled voice settings"
```

---

## 阶段 8：打包与安装器回归

**目标：** 每完成一个用户可见功能阶段后重新打包，确保安装版也具备控制面板、桌宠模式、设置/历史路径和快捷方式。

**Files:**

- Modify as needed: `tools/build_windows_app.ps1`
- Modify as needed: `packaging/e-moti-installer.iss`
- Test: `tests/test_windows_packaging_scripts.py`
- Test: `tests/test_runtime_paths.py`

- [ ] **Step 1: 运行全量测试**

Run:

```powershell
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
```

Expected:

- pytest 全量通过。
- JSON 校验通过。

- [ ] **Step 2: 构建冻结应用**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
```

Expected:

- `dist\E-Moti\E-Moti.exe` 存在。

- [ ] **Step 3: 构建安装器**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
```

Expected:

- `dist\installer\E-Moti_Setup_0.1.0.exe` 存在。

- [ ] **Step 4: smoke 冻结版面板和桌宠**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$exe = (Resolve-Path 'dist\E-Moti\E-Moti.exe').Path
$p = Start-Process -FilePath $exe -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 3
if ($p.HasExited) { throw "control panel exited early" }
Stop-Process -Id $p.Id -Force
$p = Start-Process -FilePath $exe -ArgumentList '--pet-mode' -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 3
if ($p.HasExited) { throw "pet mode exited early" }
Stop-Process -Id $p.Id -Force
```

Expected:

- 两个进程均不在 3 秒内崩溃。

- [ ] **Step 5: Commit**

如果只重建产物但脚本未改，不提交 dist。若脚本或测试有变更：

```powershell
git add tools\build_windows_app.ps1 tools\build_windows_installer.ps1 packaging\e-moti-installer.iss tests\test_windows_packaging_scripts.py tests\test_runtime_paths.py
git commit -m "build: update installer for function parity"
```

---

## 阶段门禁

每个阶段结束必须满足：

- 先写失败测试，再实现。
- 不绕过 typed snapshot/events。
- 不让 LLM、插件、工具、TTS、ASR 修改本地养成状态。
- 不提交 `data/companion_save.json`。
- 不触碰 `AI不用看.md`。
- 涉及 UI 必须跑 `tests/test_app.py` 和 `tests/test_desktop_pet_smoke.py`。
- 涉及安装版必须实际构建并确认安装器文件存在。
- 任何真实联网、TTS、ASR、自动截图、插件下载都需要单独确认。

## 推荐执行顺序

1. 阶段 1：桌宠演出窗口输入与对话事件。
2. 阶段 2：Shinsekai 式 JSON 消息解析适配。
3. 阶段 3：对话历史、清屏、复制、回溯。
4. 阶段 4：设置中心与表达增强配置。
5. 阶段 5：模板/规则预览页。
6. 阶段 6：轻量插件与工具贡献宿主。
7. 阶段 7：TTS/ASR 预留，不做主体。
8. 阶段 8：打包与安装器回归。

## 交付口径

实现完阶段 1-4 后，E-Moti 可以对外说明：

- 星汐是原创 OC 桌面电子宠物与伴侣。
- 她有本地养成状态、动作动画、背包、商店、关系、回忆和主动陪伴。
- 控制中心负责配置与管理；桌宠窗口负责桌面陪伴和对话演出。
- AI 表达增强可配置、可关闭、可 fallback。
- LLM 不控制状态、不改背包、不写存档。

不能说明：

- 不能说已经完成真实 TTS/ASR，除非阶段 7 之后另开阶段并验证。
- 不能说有自动后台屏幕观察。
- 不能说复制或兼容 Shinsekai 角色包。
- 不能说 `轻触 / 共同学习 发色偏白` 已解决。
