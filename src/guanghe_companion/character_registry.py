from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError

from .character_session import is_safe_character_id
from .runtime_paths import companion_assets_root, user_data_dir

EXPECTED_FRAME_WIDTH = 192
EXPECTED_FRAME_HEIGHT = 208
MAX_SHEET_COLUMNS = 32
MAX_SHEET_ROWS = 32
REQUIRED_FILES = (
    "character.json",
    "dialogue_style.json",
    "motion_manifest.json",
    "shop_items.json",
)
ALLOWED_ITEM_CATEGORIES = frozenset({"food", "gift", "tool"})
ALLOWED_ITEM_EFFECTS = frozenset({"charge", "mood", "stability", "trust", "study_bonus_exp"})
ALLOWED_RENDERER_BACKENDS = frozenset({"sprite", "live2d_web", "inochi2d", "portrait"})
ALLOWED_DISTRIBUTION_BOUNDARIES = frozenset(
    {"shareable_after_review", "local_ugc_only", "private_local_fanwork"}
)
DEFAULT_DISTRIBUTION_BOUNDARY = "shareable_after_review"
RENDERER_MAP_FIELDS = ("motion_map", "expression_map", "intent_map")
REQUIRED_LIVE2D_EXPRESSIONS = ("calm", "excited", "surprised", "sleepy", "sadness", "focused")
REQUIRED_LIVE2D_MOTIONS = ("Default", "Play", "Raised", "TouchHead", "Sleep")
REQUIRED_PORTRAIT_EXPRESSIONS = ("neutral", "smile", "thinking", "surprised", "sad", "sleepy")
MAX_PORTRAIT_WIDTH = 4096
MAX_PORTRAIT_HEIGHT = 4096
PROVENANCE_FILENAMES = ("provenance.md", "portrait_assets_provenance.md", "portrait_video_provenance.md")
LICENSE_FILENAMES = ("LICENSE", "LICENSE.md", "license.md")


@dataclass(frozen=True, slots=True)
class CharacterPackValidationReport:
    character_id: str
    path: Path
    source: str
    ok: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CharacterPackSummary:
    character_id: str
    name: str
    title: str
    description: str
    path: Path
    source: str
    distribution_boundary: str
    preview_path: Path
    provenance_paths: tuple[Path, ...]
    license_paths: tuple[Path, ...]


class CharacterRegistry:
    def __init__(
        self,
        *,
        builtin_root: Path | str | None = None,
        user_root: Path | str | None = None,
    ) -> None:
        self.builtin_root = Path(builtin_root) if builtin_root is not None else companion_assets_root()
        self.user_root = (
            Path(user_root)
            if user_root is not None
            else user_data_dir() / "character_packs"
        )

    def list_available_packs(self) -> tuple[CharacterPackSummary, ...]:
        summaries: list[CharacterPackSummary] = []
        seen: set[str] = set()
        for report in self.validate_all():
            if not report.ok or report.character_id in seen:
                continue
            summary = _summary_from_pack_dir(report.path, report.source)
            if summary is None:
                continue
            summaries.append(summary)
            seen.add(summary.character_id)
        return tuple(summaries)

    def get_available_pack(self, character_id: str) -> CharacterPackSummary:
        for pack in self.list_available_packs():
            if pack.character_id == character_id:
                return pack
        raise KeyError(character_id)

    def validate_all(self) -> tuple[CharacterPackValidationReport, ...]:
        reports: list[CharacterPackValidationReport] = []
        reports.extend(_validate_root(self.builtin_root, "builtin"))
        reports.extend(_validate_root(self.user_root, "user"))
        return tuple(reports)


def validate_character_pack_dir(
    pack_dir: Path | str,
    *,
    source: str = "builtin",
) -> CharacterPackValidationReport:
    root = Path(pack_dir)
    errors: list[str] = []
    character = _read_json_object(root / "character.json", errors, label="character.json")
    character_id = _character_id_from_payload(character, root)

    if not root.is_dir():
        errors.append(f"pack directory not found: {root}")
    if not is_safe_character_id(character_id):
        errors.append(f"unsafe character_id: {character_id!r}")
    if character_id != root.name:
        errors.append(f"character_id must match directory name: {root.name}")

    for filename in REQUIRED_FILES:
        if not (root / filename).is_file():
            errors.append(f"missing required file: {filename}")

    dialogue = _read_json_object(root / "dialogue_style.json", errors, label="dialogue_style.json")
    motion_manifest = _read_json_object(root / "motion_manifest.json", errors, label="motion_manifest.json")
    shop_items = _read_json_list(root / "shop_items.json", errors, label="shop_items.json")

    if isinstance(character, dict):
        _validate_character_payload(root, character, errors)
    if isinstance(dialogue, dict):
        _validate_dialogue_payload(dialogue, errors)
    if isinstance(motion_manifest, dict):
        _validate_motion_manifest(root, character, motion_manifest, errors)
    if isinstance(shop_items, list):
        _validate_shop_items(root, shop_items, errors)

    return CharacterPackValidationReport(
        character_id=character_id,
        path=root,
        source=source,
        ok=not errors,
        errors=tuple(errors),
    )


def summarize_character_pack_dir(
    pack_dir: Path | str,
    *,
    source: str = "builtin",
) -> CharacterPackSummary | None:
    return _summary_from_pack_dir(Path(pack_dir), source)


def _validate_root(root: Path, source: str) -> Iterable[CharacterPackValidationReport]:
    if not root.exists():
        return ()
    return tuple(
        validate_character_pack_dir(path, source=source)
        for path in sorted(root.iterdir(), key=lambda candidate: candidate.name)
        if path.is_dir()
    )


def _character_id_from_payload(payload: object, root: Path) -> str:
    if isinstance(payload, dict) and isinstance(payload.get("character_id"), str):
        return str(payload["character_id"])
    return root.name


def _read_json_object(path: Path, errors: list[str], *, label: str) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} json invalid: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label} must be an object")
        return None
    return payload


def _read_json_list(path: Path, errors: list[str], *, label: str) -> list[object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} json invalid: {exc}")
        return None
    if not isinstance(payload, list):
        errors.append(f"{label} must be a list")
        return None
    return payload


def _validate_character_payload(root: Path, payload: dict[str, object], errors: list[str]) -> None:
    for key in (
        "character_id",
        "name",
        "title",
        "description",
        "spritesheet",
        "motion_manifest",
        "default_mode",
    ):
        if not isinstance(payload.get(key), str) or not str(payload.get(key)).strip():
            errors.append(f"character.json.{key} must be a non-empty string")
    modes = payload.get("modes")
    if not isinstance(modes, list) or not all(isinstance(mode, str) and mode for mode in modes):
        errors.append("character.json.modes must be a non-empty string list")
    if not isinstance(payload.get("mode_descriptions"), dict):
        errors.append("character.json.mode_descriptions must be an object")
    if not isinstance(payload.get("motion_labels"), dict):
        errors.append("character.json.motion_labels must be an object")
    _validate_distribution_boundary(payload, errors)
    _validate_renderer_payload(root, payload.get("renderer"), errors)


def _validate_distribution_boundary(payload: dict[str, object], errors: list[str]) -> None:
    value = payload.get("distribution_boundary")
    if value is None:
        return
    if not isinstance(value, str) or value not in ALLOWED_DISTRIBUTION_BOUNDARIES:
        errors.append("character.json.distribution_boundary invalid")


def _distribution_boundary_from_payload(payload: dict[str, object]) -> str:
    value = payload.get("distribution_boundary")
    if isinstance(value, str) and value in ALLOWED_DISTRIBUTION_BOUNDARIES:
        return value
    return DEFAULT_DISTRIBUTION_BOUNDARY


def _validate_renderer_payload(root: Path, value: object, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append("character.json.renderer must be an object")
        return
    backend = value.get("backend", "sprite")
    if backend not in ALLOWED_RENDERER_BACKENDS:
        errors.append("character.json.renderer.backend invalid")
    if backend == "live2d_web":
        model = value.get("model")
        if not _safe_live2d_model_path(model):
            errors.append("character.json.renderer.model must be a safe relative model3 path")
        else:
            model_path = root / str(model)
            if not model_path.is_file():
                errors.append(f"character.json.renderer.model file not found: {model}")
        _validate_required_renderer_map(
            value.get("expression_map", {}),
            "expression_map",
            REQUIRED_LIVE2D_EXPRESSIONS,
            errors,
        )
        _validate_required_renderer_map(
            value.get("motion_map", {}),
            "motion_map",
            REQUIRED_LIVE2D_MOTIONS,
            errors,
        )
    if backend == "portrait":
        manifest = value.get("portrait_manifest")
        if not _safe_portrait_manifest_path(manifest):
            errors.append("character.json.renderer.portrait_manifest must be a safe relative json filename")
        else:
            manifest_path = root / str(manifest)
            if not manifest_path.is_file():
                errors.append(f"portrait manifest not found: {manifest}")
            else:
                payload = _read_json_object(manifest_path, errors, label="portrait_manifest.json")
                if isinstance(payload, dict):
                    _validate_portrait_manifest(root, payload, errors)
    for field in RENDERER_MAP_FIELDS:
        mapping = value.get(field, {})
        if not isinstance(mapping, dict):
            errors.append(f"character.json.renderer.{field} must be an object")
            continue
        for key, item in mapping.items():
            if not isinstance(key, str) or not key:
                errors.append(f"character.json.renderer.{field} keys must be non-empty strings")
                continue
            if not _safe_renderer_id(item):
                errors.append(f"character.json.renderer.{field}.{key} must be a safe renderer id")


def _validate_required_renderer_map(
    mapping: object,
    field: str,
    required_actions: tuple[str, ...],
    errors: list[str],
) -> None:
    if not isinstance(mapping, dict):
        return
    for action in required_actions:
        if action not in mapping:
            errors.append(f"character.json.renderer.{field} missing required Live2D action: {action}")


def _safe_renderer_id(value: object) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def _safe_live2d_model_path(value: object) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    return path.suffix == ".json" and path.name.endswith(".model3.json")


def _safe_portrait_manifest_path(value: object) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts and len(path.parts) == 1 and path.suffix == ".json"


def _validate_portrait_manifest(root: Path, payload: dict[str, object], errors: list[str]) -> None:
    expressions = payload.get("expressions")
    if not isinstance(expressions, dict):
        errors.append("portrait_manifest.expressions must be an object")
        return
    for expression in REQUIRED_PORTRAIT_EXPRESSIONS:
        if expression not in expressions:
            errors.append(f"portrait_manifest.expressions missing required portrait expression: {expression}")
    fallback = payload.get("fallback_expression")
    if not isinstance(fallback, str) or fallback not in expressions:
        errors.append("portrait_manifest.fallback_expression must reference an expression")
    for expression, image_path in expressions.items():
        if not isinstance(expression, str) or not expression:
            errors.append("portrait_manifest.expressions keys must be non-empty strings")
            continue
        for frame_name, frame_path in _portrait_frame_paths(image_path):
            label = expression if not frame_name else f"{expression}.{frame_name}"
            if not _safe_portrait_image_path(frame_path):
                errors.append(f"portrait_manifest.expressions.{label} path must stay inside portraits")
                continue
            _validate_portrait_image(root, label, str(frame_path), errors)
    _validate_portrait_motion_frames(root, payload.get("motion_frames"), errors)

    anchor = payload.get("anchor", "bottom_center")
    if anchor not in {"bottom_center", "center"}:
        errors.append("portrait_manifest.anchor invalid")
    default_scale = payload.get("default_scale", 1.0)
    if (
        isinstance(default_scale, bool)
        or not isinstance(default_scale, (int, float))
        or not 0.1 <= float(default_scale) <= 3.0
    ):
        errors.append("portrait_manifest.default_scale must be between 0.1 and 3.0")


def _safe_portrait_image_path(value: object) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    path = Path(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and len(path.parts) >= 2
        and path.parts[0] == "portraits"
        and path.suffix.lower() == ".png"
    )


def _validate_portrait_motion_frames(root: Path, value: object, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        errors.append("portrait_manifest.motion_frames must be an array")
        return
    for index, item in enumerate(value):
        label = f"motion_frames.{index}"
        if not _safe_portrait_motion_frame_path(item):
            errors.append(f"portrait_manifest.{label} path must stay inside motion_frames")
            continue
        _validate_portrait_motion_frame(root, label, str(item), errors)


def _safe_portrait_motion_frame_path(value: object) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    path = Path(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and len(path.parts) >= 2
        and path.parts[0] == "motion_frames"
        and path.suffix.lower() == ".png"
    )


def _validate_portrait_motion_frame(root: Path, label: str, relative_path: str, errors: list[str]) -> None:
    path = root / relative_path
    if not path.is_file():
        errors.append(f"portrait motion frame not found: {label}")
        return
    try:
        with Image.open(path) as image:
            width, height = image.size
            mode = image.mode
            image.verify()
    except (OSError, UnidentifiedImageError) as exc:
        errors.append(f"portrait motion frame invalid: {label}: {exc}")
        return
    if mode != "RGBA":
        errors.append(f"portrait motion frame mode must be RGBA: {label}")
    if width > MAX_PORTRAIT_WIDTH or height > MAX_PORTRAIT_HEIGHT:
        errors.append(f"portrait motion frame too large: {label}")


def _portrait_frame_paths(value: object) -> tuple[tuple[str, object], ...]:
    if isinstance(value, str):
        return (("", value),)
    if not isinstance(value, dict):
        return (("", value),)
    frames: list[tuple[str, object]] = []
    open_path = value.get("open")
    if not isinstance(open_path, str) or not open_path:
        frames.append(("open", ""))
    else:
        frames.append(("open", open_path))
    for key in ("blink_half", "blink_closed"):
        if key in value:
            frames.append((key, value.get(key)))
    for key in value:
        if key not in {"open", "blink_half", "blink_closed"}:
            frames.append((str(key), value.get(key)))
    return tuple(frames)


def _validate_portrait_image(root: Path, expression: str, image_path: str, errors: list[str]) -> None:
    resolved = (root / image_path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        errors.append(f"portrait_manifest.expressions.{expression} path must stay inside portraits")
        return
    if not resolved.is_file():
        errors.append(f"portrait image not found: {image_path}")
        return
    try:
        with Image.open(resolved) as image:
            size = image.size
            mode = image.mode
            image.verify()
    except (OSError, UnidentifiedImageError) as exc:
        errors.append(f"portrait image invalid: {image_path}: {exc}")
        return
    if mode != "RGBA":
        errors.append(f"portrait image mode must be RGBA: {image_path}")
    if size[0] > MAX_PORTRAIT_WIDTH or size[1] > MAX_PORTRAIT_HEIGHT:
        errors.append(f"portrait image too large: {image_path}")


def _validate_dialogue_payload(payload: dict[str, object], errors: list[str]) -> None:
    for key in ("tone", "fallback_style"):
        if not isinstance(payload.get(key), str) or not str(payload.get(key)).strip():
            errors.append(f"dialogue_style.json.{key} must be a non-empty string")
    keywords = payload.get("keywords")
    if not isinstance(keywords, list) or not all(isinstance(keyword, str) and keyword for keyword in keywords):
        errors.append("dialogue_style.json.keywords must be a non-empty string list")


def _validate_motion_manifest(
    root: Path,
    character: dict[str, object] | None,
    payload: dict[str, object],
    errors: list[str],
) -> None:
    sheet_columns = payload.get("sheet_columns")
    sheet_rows = payload.get("sheet_rows")
    frame_width = payload.get("frame_width")
    frame_height = payload.get("frame_height")
    if isinstance(sheet_columns, bool) or not isinstance(sheet_columns, int) or not 1 <= sheet_columns <= MAX_SHEET_COLUMNS:
        errors.append(f"motion_manifest.sheet_columns must be between 1 and {MAX_SHEET_COLUMNS}")
    valid_rows = isinstance(sheet_rows, int) and not isinstance(sheet_rows, bool) and 1 <= sheet_rows <= MAX_SHEET_ROWS
    if not valid_rows:
        errors.append(f"motion_manifest.sheet_rows must be between 1 and {MAX_SHEET_ROWS}")
    if frame_width != EXPECTED_FRAME_WIDTH:
        errors.append("motion_manifest.frame_width must be 192")
    if frame_height != EXPECTED_FRAME_HEIGHT:
        errors.append("motion_manifest.frame_height must be 208")
    motions = payload.get("motions")
    if not isinstance(motions, dict) or "Default" not in motions:
        errors.append("motion_manifest.motions must include Default")
    elif isinstance(motions, dict):
        for motion_name, motion in motions.items():
            if not isinstance(motion, dict):
                errors.append(f"motion_manifest.{motion_name} must be an object")
                continue
            row = motion.get("row")
            frame_count = motion.get("frame_count")
            fps = motion.get("fps")
            if isinstance(row, bool) or not isinstance(row, int) or not valid_rows or not 0 <= row < sheet_rows:
                errors.append(f"motion_manifest.{motion_name}.row out of range")
            if (
                isinstance(frame_count, bool)
                or not isinstance(frame_count, int)
                or not isinstance(sheet_columns, int)
                or isinstance(sheet_columns, bool)
                or not 1 <= frame_count <= sheet_columns
            ):
                errors.append(f"motion_manifest.{motion_name}.frame_count out of range")
            if isinstance(fps, bool) or not isinstance(fps, int) or fps <= 0:
                errors.append(f"motion_manifest.{motion_name}.fps must be positive")

    spritesheet = character.get("spritesheet") if isinstance(character, dict) else "spritesheet.png"
    if isinstance(spritesheet, str):
        _validate_atlas(root, spritesheet, payload, errors)


def _validate_atlas(
    root: Path,
    spritesheet: str,
    manifest: dict[str, object],
    errors: list[str],
) -> None:
    if not _safe_relative_path(spritesheet):
        errors.append("spritesheet path must be a safe relative filename")
        return
    path = root / spritesheet
    if not path.is_file():
        errors.append(f"spritesheet not found: {spritesheet}")
        return
    try:
        with Image.open(path) as image:
            size = image.size
            mode = image.mode
            image.verify()
    except (OSError, UnidentifiedImageError) as exc:
        errors.append(f"spritesheet image invalid: {exc}")
        return
    sheet_columns = manifest.get("sheet_columns")
    sheet_rows = manifest.get("sheet_rows")
    valid_rows = isinstance(sheet_rows, int) and not isinstance(sheet_rows, bool) and 1 <= sheet_rows <= MAX_SHEET_ROWS
    if isinstance(sheet_columns, int) and not isinstance(sheet_columns, bool) and valid_rows:
        expected_width = sheet_columns * EXPECTED_FRAME_WIDTH
        expected_height = sheet_rows * EXPECTED_FRAME_HEIGHT
        if size != (expected_width, expected_height):
            errors.append(f"spritesheet must be {expected_width}x{expected_height}, got {size[0]}x{size[1]}")
    if mode != "RGBA":
        errors.append(f"spritesheet mode must be RGBA, got {mode}")


def _validate_shop_items(root: Path, payload: list[object], errors: list[str]) -> None:
    if not payload:
        errors.append("shop_items.json must include at least one item")
        return
    seen: set[str] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            errors.append(f"shop_items[{index}] must be an object")
            continue
        item_id = item.get("item_id")
        icon = item.get("icon")
        category = item.get("category")
        effects = item.get("effects")
        if not isinstance(item_id, str) or not is_safe_character_id(item_id):
            errors.append(f"shop_items[{index}].item_id must be a safe id")
        elif item_id in seen:
            errors.append(f"shop_items[{index}].item_id duplicated: {item_id}")
        else:
            seen.add(item_id)
        if category not in ALLOWED_ITEM_CATEGORIES:
            errors.append(f"shop_items[{index}].category invalid")
        if not isinstance(item.get("name"), str) or not str(item.get("name")).strip():
            errors.append(f"shop_items[{index}].name must be non-empty")
        if isinstance(item.get("price"), bool) or not isinstance(item.get("price"), int) or item.get("price") < 0:
            errors.append(f"shop_items[{index}].price must be a non-negative integer")
        if not isinstance(effects, dict) or not effects:
            errors.append(f"shop_items[{index}].effects must be a non-empty object")
        elif any(key not in ALLOWED_ITEM_EFFECTS for key in effects):
            errors.append(f"shop_items[{index}].effects contains unsupported key")
        if not isinstance(icon, str):
            errors.append(f"shop_items[{index}].icon must be a string")
        else:
            _validate_icon_path(root, icon, errors)


def _validate_icon_path(root: Path, icon: str, errors: list[str]) -> None:
    icon_path = Path(icon)
    if icon_path.is_absolute() or ".." in icon_path.parts or len(icon_path.parts) != 2 or icon_path.parts[0] != "item_icons":
        errors.append(f"icon path must stay inside item_icons: {icon}")
        return
    resolved = (root / icon_path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        errors.append(f"icon path must stay inside item_icons: {icon}")
        return
    if not resolved.is_file():
        errors.append(f"icon not found: {icon}")


def _summary_from_pack_dir(root: Path, source: str) -> CharacterPackSummary | None:
    try:
        payload = json.loads((root / "character.json").read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    preview = root / "preview" / "contact-sheet.png"
    return CharacterPackSummary(
        character_id=str(payload["character_id"]),
        name=str(payload["name"]),
        title=str(payload["title"]),
        description=str(payload["description"]),
        path=root,
        source=source,
        distribution_boundary=_distribution_boundary_from_payload(payload),
        preview_path=preview,
        provenance_paths=_existing_pack_files(root, PROVENANCE_FILENAMES),
        license_paths=_existing_pack_files(root, LICENSE_FILENAMES),
    )


def _existing_pack_files(root: Path, filenames: Iterable[str]) -> tuple[Path, ...]:
    paths: list[Path] = []
    seen: set[str] = set()
    for filename in filenames:
        path = root / filename
        if not path.is_file():
            continue
        try:
            key = str(path.resolve()).casefold()
        except OSError:
            key = str(path.absolute()).casefold()
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return tuple(paths)


def _safe_relative_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and len(path.parts) == 1
