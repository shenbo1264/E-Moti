from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DATA_DIR_NAME = "E-Moti"
USER_DATA_ENV = "E_MOTI_USER_DATA_DIR"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def assets_root() -> Path:
    for candidate in _asset_candidates():
        if candidate.exists():
            return candidate
    return _asset_candidates()[0]


def companion_assets_root() -> Path:
    return assets_root() / "companion"


def user_data_dir() -> Path:
    override = os.environ.get(USER_DATA_ENV)
    if override:
        return Path(override).expanduser()
    if is_frozen():
        return _local_app_data_root() / APP_DATA_DIR_NAME
    return repo_root() / "data"


def default_save_path() -> Path:
    return user_data_dir() / "companion_save.json"


def demo_save_path() -> Path:
    return user_data_dir() / "companion_demo_save.json"


def dialogue_history_path() -> Path:
    return user_data_dir() / "dialogue_history.json"


def expression_settings_path() -> Path:
    return user_data_dir() / "expression_settings.json"


def capability_settings_path() -> Path:
    return user_data_dir() / "capability_settings.json"


def long_term_memory_path() -> Path:
    return user_data_dir() / "long_term_memory.json"


def tts_cache_dir() -> Path:
    return user_data_dir() / "cache" / "tts"


def _asset_candidates() -> list[Path]:
    candidates: list[Path] = []
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets")
        candidates.append(Path(sys.executable).resolve().parent / "assets")
    candidates.append(repo_root() / "assets")
    return candidates


def _local_app_data_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data).expanduser()
    return Path.home() / "AppData" / "Local"
