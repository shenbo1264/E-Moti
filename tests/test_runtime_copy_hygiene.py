import ast
import json
from collections.abc import Iterable
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_COPY_FILES = (
    "src/guanghe_companion/controller.py",
    "src/guanghe_companion/character_local_copy.py",
    "src/guanghe_companion/companion_moments.py",
    "src/guanghe_companion/relationship.py",
    "src/guanghe_companion/engine.py",
    "src/guanghe_companion/topic_scout.py",
)
ASSET_COPY_GLOBS = (
    "assets/companion/*/character.json",
    "assets/companion/*/dialogue_style.json",
    "assets/companion/*/shop_items.json",
)
AI_TEMPLATE_PHRASES = (
    "不是",
    "而是",
    "不只是",
    "作为一个",
    "我理解",
    "我可以帮",
    "首先",
    "其次",
    "总结",
    "综上",
)
OUT_OF_WORLD_PROFILE_PHRASES = (
    "课程提交",
    "展示包",
    "结构化事件",
    "hatch-pet",
    "序列帧包",
    "运行时",
)


def test_runtime_companion_copy_avoids_template_ai_phrasing():
    hits = _copy_phrase_hits(AI_TEMPLATE_PHRASES)

    assert hits == []


def test_bundled_character_profiles_use_in_world_descriptions():
    hits: list[str] = []
    for path in sorted((REPO_ROOT / "assets" / "companion").glob("*/character.json")):
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        for field in ("description", "title"):
            value = payload.get(field)
            if not isinstance(value, str):
                continue
            for phrase in OUT_OF_WORLD_PROFILE_PHRASES:
                if phrase in value:
                    hits.append(f"{path.relative_to(REPO_ROOT)}:{field}:{phrase}")

    assert hits == []


def _copy_phrase_hits(phrases: Iterable[str]) -> list[str]:
    hits: list[str] = []
    for path, label, text in _iter_runtime_copy():
        for phrase in phrases:
            if phrase in text:
                hits.append(f"{path.relative_to(REPO_ROOT)}:{label}:{phrase}:{text}")
    return hits


def _iter_runtime_copy() -> Iterable[tuple[Path, str, str]]:
    for relative_path in PYTHON_COPY_FILES:
        path = REPO_ROOT / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _contains_cjk(node.value):
                yield path, f"L{node.lineno}", node.value
    for pattern in ASSET_COPY_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            for label, text in _json_strings(payload):
                if _contains_cjk(text):
                    yield path, label, text


def _json_strings(value: object, prefix: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield prefix, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _json_strings(item, f"{prefix}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _json_strings(item, f"{prefix}.{key}")


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)
