from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .character_session import is_safe_character_id


@dataclass(frozen=True, slots=True)
class CharacterDraft:
    character_id: str
    pack_dir: Path
    import_ready: bool
    manual_qa_required: bool


class CharacterGenerationWorkflow:
    def __init__(self, *, output_root: Path | str) -> None:
        self.output_root = Path(output_root)

    def create_draft(
        self,
        brief: Mapping[str, object],
        *,
        source_notes: Iterable[Mapping[str, str]] = (),
        force: bool = False,
    ) -> CharacterDraft:
        normalized = _normalize_brief(brief)
        character_id = str(normalized["character_id"])
        pack_dir = self.output_root / character_id
        if pack_dir.exists():
            if not force:
                raise FileExistsError(pack_dir)
            shutil.rmtree(pack_dir)
        pack_dir.mkdir(parents=True, exist_ok=False)
        (pack_dir / "item_icons").mkdir()
        (pack_dir / "preview").mkdir()

        _write_json(pack_dir / "character.json", _character_json(normalized))
        _write_json(pack_dir / "dialogue_style.json", _dialogue_style_json(normalized))
        _write_json(pack_dir / "shop_items.json", _shop_items_json(normalized))
        _write_json(pack_dir / "motion_manifest.json", _motion_manifest_json())
        _write_json(pack_dir / "art_prompts.json", _art_prompts(normalized))
        (pack_dir / "character_card.md").write_text(
            _character_card_markdown(normalized),
            encoding="utf-8",
        )
        (pack_dir / "provenance.md").write_text(
            _provenance_markdown(normalized, source_notes),
            encoding="utf-8",
        )
        (pack_dir / "qa_checklist.md").write_text(_qa_checklist(normalized), encoding="utf-8")
        return CharacterDraft(
            character_id=character_id,
            pack_dir=pack_dir,
            import_ready=False,
            manual_qa_required=True,
        )


def _normalize_brief(brief: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(brief, Mapping):
        raise ValueError("invalid character brief")
    character_id = _required_text(brief.get("character_id"), 64)
    name = _required_text(brief.get("name"), 32)
    title = _required_text(brief.get("title"), 40)
    description = _required_text(brief.get("description"), 180)
    if not is_safe_character_id(character_id) or not name or not title or not description:
        raise ValueError("invalid character brief")
    return {
        "character_id": character_id,
        "name": name,
        "title": title,
        "description": description,
        "visual_keywords": _text_list(brief.get("visual_keywords"), 8, 40),
        "personality_keywords": _text_list(brief.get("personality_keywords"), 8, 40),
        "boundaries": _text_list(brief.get("boundaries"), 8, 80),
        "policy": _policy(brief.get("policy")),
        "source_character": _required_text(brief.get("source_character"), 80),
    }


def _character_json(brief: Mapping[str, object]) -> dict[str, object]:
    return {
        "character_id": brief["character_id"],
        "name": brief["name"],
        "title": brief["title"],
        "description": brief["description"],
        "spritesheet": "spritesheet.png",
        "motion_manifest": "motion_manifest.json",
        "default_mode": "Calm",
        "modes": ["Glow", "Calm", "Frayed", "Overload"],
        "mode_descriptions": {
            "Glow": "情绪稳定且主动亲近。",
            "Calm": "频率平稳，适合日常互动。",
            "Frayed": "开始疲惫或分心，需要轻一点的陪伴。",
            "Overload": "进入保护状态，只接受安抚和休息。",
        },
        "motion_labels": {
            "Default": "待机呼吸",
            "TouchHead": "靠近回应",
            "Comfort": "情绪安抚",
            "Sleep": "进入休息",
            "Study": "共同行动",
            "Play": "共同娱乐",
            "Raised": "被轻轻提起",
            "Eat": "接受投喂",
            "Gift": "收到礼物",
            "Shop": "资源补给",
            "Tick": "时间流逝",
            "SwitchDown": "低状态反馈",
        },
        "relationship_decorations": [
            {
                "unlock_id": "unlock_first_nickname",
                "item_id": "keepsake_badge",
                "label": "纪念徽章",
                "icon": "item_icons/keepsake_badge.png",
            }
        ],
    }


def _dialogue_style_json(brief: Mapping[str, object]) -> dict[str, object]:
    keywords = list(brief["personality_keywords"] or [])[:5]
    return {
        "tone": "、".join(keywords) or "克制、亲近、清晰",
        "keywords": keywords or ["陪伴", "记录", "靠近"],
        "fallback_style": "短句、明确反馈、避免长篇解释",
    }


def _shop_items_json(brief: Mapping[str, object]) -> list[dict[str, object]]:
    return [
        {
            "item_id": "snack",
            "name": "小点心",
            "category": "food",
            "icon": "item_icons/snack.png",
            "price": 12,
            "effects": {"mood": 3, "charge": 6},
        },
        {
            "item_id": "keepsake_badge",
            "name": "纪念徽章",
            "category": "gift",
            "icon": "item_icons/keepsake_badge.png",
            "price": 24,
            "effects": {"mood": 6, "trust": 3},
        },
    ]


def _motion_manifest_json() -> dict[str, object]:
    return {
        "sheet_columns": 8,
        "sheet_rows": 9,
        "frame_width": 192,
        "frame_height": 208,
        "background": "transparent",
        "motions": {
            "Default": {"row": 0, "frame_count": 6, "fps": 4},
            "MoveRight": {"row": 1, "frame_count": 8, "fps": 8},
            "MoveLeft": {"row": 2, "frame_count": 8, "fps": 8},
            "TouchHead": {"row": 3, "frame_count": 4, "fps": 6},
            "Play": {"row": 4, "frame_count": 5, "fps": 7},
            "SwitchDown": {"row": 5, "frame_count": 8, "fps": 5},
            "Sleep": {"row": 6, "frame_count": 6, "fps": 4},
            "Raised": {"row": 7, "frame_count": 6, "fps": 7},
            "Study": {"row": 8, "frame_count": 6, "fps": 5},
            "Comfort": {"row": 6, "frame_count": 6, "fps": 4},
            "Eat": {"row": 3, "frame_count": 4, "fps": 6},
            "Gift": {"row": 3, "frame_count": 4, "fps": 6},
            "Shop": {"row": 4, "frame_count": 5, "fps": 5},
            "Tick": {"row": 0, "frame_count": 6, "fps": 4},
        },
    }


def _art_prompts(brief: Mapping[str, object]) -> dict[str, object]:
    visual = ", ".join(brief["visual_keywords"] or ["original desktop companion"])
    boundaries = "; ".join(brief["boundaries"] or ["No copyrighted characters"])
    if brief.get("policy") == "local_fanwork":
        source = str(brief.get("source_character") or brief["name"])
        common = (
            "private local fanwork only. Do not bundle or distribute. "
            "Do not use official art, screenshots, logos, copied lines, or exact asset reproduction. "
            f"User-provided source character for private reference: {source}. "
            "transparent background, consistent outfit, readable at 192x208. "
            f"Visual keywords: {visual}. Boundaries: {boundaries}."
        )
    else:
        common = (
            "No copyrighted characters, no fan art, no existing franchise style copying, "
            "transparent background, consistent outfit, readable at 192x208. "
            f"Visual keywords: {visual}. Boundaries: {boundaries}."
        )
    return {
        "reference_sheet": f"Create an original desktop companion character design sheet. {common}",
        "sprite_rows": {
            motion: f"Generate {motion} animation frames for the same original character. {common}"
            for motion in (
                "Default",
                "MoveRight",
                "MoveLeft",
                "TouchHead",
                "Play",
                "SwitchDown",
                "Sleep",
                "Raised",
                "Study",
            )
        },
        "item_icons": {
            "snack": f"Create a small original food icon. {common}",
            "keepsake_badge": f"Create a small original keepsake badge icon. {common}",
        },
    }


def _provenance_markdown(
    brief: Mapping[str, object],
    source_notes: Iterable[Mapping[str, str]],
) -> str:
    policy = str(brief.get("policy") or "original_inspiration")
    source_character = str(brief.get("source_character") or "")
    if policy == "local_fanwork":
        origin_line = "Local fanwork: user-authorized private draft only; do not commit, bundle, or distribute."
    else:
        origin_line = "Originality: generated from an abstract brief; no copyrighted character assets are included."
    lines = [
        f"# {brief['name']} Provenance",
        "",
        "Status: draft, not import-ready.",
        f"Policy: {policy}.",
        origin_line,
    ]
    if source_character:
        lines.extend(["", f"Source character: {source_character}"])
    lines.extend(
        [
            "",
            "## Source Notes",
        ]
    )
    for note in source_notes:
        title = _required_text(note.get("title"), 80) or "source"
        summary = _required_text(note.get("summary"), 180) or "summary unavailable"
        url = _required_text(note.get("url"), 240)
        suffix = f" - {url}" if url else ""
        lines.append(f"- {title}: {summary}{suffix}")
    if len(lines) == 6:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _qa_checklist(brief: Mapping[str, object]) -> str:
    lines = [
        "# Character Draft QA",
        "",
        "- [ ] JSON files pass `python -m json.tool`.",
        "- [ ] `spritesheet.png` is generated as 1536x1872 RGBA.",
        "- [ ] Item icons exist under `item_icons/`.",
        "- [ ] `tools/art/validate_companion_atlas.py` passes.",
        "- [ ] Contact sheet and GIF previews are manually inspected.",
    ]
    if brief.get("policy") == "local_fanwork":
        lines.extend(
            [
                "- [ ] Do not commit local fanwork packs into the open-source repository.",
                "- [ ] Do not bundle or distribute official art, logos, copied lines, or exact assets.",
            ]
        )
    else:
        lines.append("- [ ] No third-party IP names, logos, protected outfits, or copied lines remain.")
    return "\n".join(lines) + "\n"


def _character_card_markdown(brief: Mapping[str, object]) -> str:
    policy = str(brief.get("policy") or "original_inspiration")
    source_character = str(brief.get("source_character") or "")
    lines = [
        f"# {brief['name']}",
        "",
        f"Policy: {policy}",
    ]
    if source_character:
        lines.append(f"Source character: {source_character}")
    lines.extend(
        [
            f"Character ID: {brief['character_id']}",
            f"Title: {brief['title']}",
            "",
            "## Description",
            str(brief["description"]),
            "",
            "## Visual Keywords",
        ]
    )
    visual_keywords = list(brief["visual_keywords"])
    lines.extend(f"- {item}" for item in visual_keywords)
    lines.extend(["", "## Personality Keywords"])
    personality_keywords = list(brief["personality_keywords"])
    lines.extend(f"- {item}" for item in personality_keywords)
    lines.extend(["", "## Boundaries"])
    boundaries = list(brief["boundaries"])
    if not boundaries and policy == "local_fanwork":
        boundaries = ["Private local fanwork only", "Do not bundle or distribute"]
    lines.extend(f"- {item}" for item in boundaries)
    lines.extend(
        [
            "",
            "## Asset Status",
            "- Draft metadata exists.",
            "- Spritesheet and item icons still require manual generation and QA.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _required_text(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value).strip()[:max_length]


def _text_list(value: object, limit: int, max_length: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for entry in value:
        text = _required_text(entry, max_length)
        if text and text not in items:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _policy(value: object) -> str:
    if value == "local_fanwork":
        return "local_fanwork"
    return "original_inspiration"
