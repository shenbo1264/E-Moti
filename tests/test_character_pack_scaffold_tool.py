from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_scaffold_character_pack_writes_private_local_fanwork_pack(tmp_path: Path) -> None:
    target = tmp_path / "packs"

    result = subprocess.run(
        [
            sys.executable,
            "tools/scaffold_character_pack.py",
            "--character-id",
            "test_pet",
            "--name",
            "Test Pet",
            "--title",
            "Local test pack",
            "--distribution-boundary",
            "private_local_fanwork",
            "--output-root",
            str(target),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0
    pack_dir = target / "test_pet"
    character = json.loads((pack_dir / "character.json").read_text(encoding="utf-8"))
    assert character["character_id"] == "test_pet"
    assert character["distribution_boundary"] == "private_local_fanwork"
    assert (pack_dir / "provenance.md").read_text(encoding="utf-8").startswith("# Provenance")
    assert (pack_dir / "preview").is_dir()


def test_scaffold_character_pack_rejects_unsafe_character_id(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "tools/scaffold_character_pack.py",
            "--character-id",
            "..\\bad",
            "--name",
            "Bad",
            "--title",
            "Bad",
            "--output-root",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 2
    assert "unsafe character id" in result.stderr
