from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import CompanionState

DEFAULT_SAVE_PATH = Path(__file__).resolve().parents[2] / "data" / "companion_save.json"


def save_state(state: CompanionState, path: Path | str = DEFAULT_SAVE_PATH) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(path: Path | str = DEFAULT_SAVE_PATH) -> CompanionState | None:
    target = Path(path)
    if not target.exists():
        return None
    payload = json.loads(target.read_text(encoding="utf-8"))
    return CompanionState(**payload)
