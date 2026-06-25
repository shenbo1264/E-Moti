from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Mapping

MAX_LOCAL_COPY_KEYS = 40
MAX_LOCAL_COPY_LENGTH = 160
DEFAULT_LOCAL_COPY: dict[str, str] = {
    "initial": "我在这里。先轻轻碰一下试试。",
    "reset": "{character_name}重新站好了。回到初识，背包清空，手里还有 20 coins。",
    "switch": "现在是 {character_name} 在这里。",
    "dialogue_ack": "嗯，我听见了：{text}",
    "empty_dialogue": "我在这里。你可以慢慢说。",
    "purchase": "买好啦：{item_name}。我先放进背包里。",
    "feed": "投喂了 {item_name}。{character_name}看起来舒服了一点。",
    "gift": "把 {item_name} 交给了 {character_name}。这份心意被好好收下了。",
    "use": "{item_name} 用上了。",
    "tick": "{character_name}在桌面上待了一小会儿，状态悄悄变了。",
    "reject_proactive": "好，这次先暂停提醒。{character_name}会安静待着。",
}


@dataclass(frozen=True, slots=True)
class CharacterLocalCopy:
    templates: Mapping[str, str]

    def line(self, key: str, *, default: str = "", **values: object) -> str:
        template = self.templates.get(key) or DEFAULT_LOCAL_COPY.get(key) or default
        return _format_template(template, values) or default


def load_character_local_copy(asset_dir: Path | str) -> CharacterLocalCopy:
    payload = _read_dialogue_style(Path(asset_dir) / "dialogue_style.json")
    local_copy = payload.get("local_copy") if isinstance(payload, dict) else None
    templates = dict(DEFAULT_LOCAL_COPY)
    if isinstance(local_copy, dict):
        count = 0
        for key, value in local_copy.items():
            if count >= MAX_LOCAL_COPY_KEYS:
                break
            clean_key = _clean_key(key)
            clean_value = _clean_text(value)
            if clean_key and clean_value:
                templates[clean_key] = clean_value
                count += 1
    return CharacterLocalCopy(templates=templates)


def _read_dialogue_style(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _format_template(template: str, values: Mapping[str, object]) -> str:
    safe_values = {key: _clean_text(value) for key, value in values.items()}
    try:
        fields = {field_name for _, field_name, _, _ in Formatter().parse(template) if field_name}
    except ValueError:
        return ""
    for field_name in fields:
        safe_values.setdefault(field_name, "")
    try:
        return _clean_text(template.format_map(safe_values))
    except (KeyError, ValueError):
        return ""


def _clean_key(value: object) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = "".join(char for char in value.strip().lower() if char.isalnum() or char == "_")
    return cleaned[:40]


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value.strip())
    return " ".join(cleaned.split())[:MAX_LOCAL_COPY_LENGTH]
