from __future__ import annotations

from pathlib import Path


def test_ikaros_gptsovits_start_script_documents_final_weights() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "tools" / "voice_services" / "start_ikaros_gptsovits_server.ps1"

    text = script.read_text(encoding="utf-8")

    assert "ikaros_curated160_v2-e4.ckpt" in text
    assert "ikaros_full642_v2_e3_s1926.pth" in text
    assert "9882" in text
    assert "EMOTI_GPTSOVITS_ROOT" in text
