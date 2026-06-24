from __future__ import annotations

import json


def test_simulated_playthrough_report_without_live_services(tmp_path) -> None:
    from tools import simulate_companion_playthrough

    report = tmp_path / "playthrough.json"
    code = simulate_companion_playthrough.main(
        [
            "--report",
            str(report),
            "--skip-live-voice",
            "--user-data-root",
            str(tmp_path / "user-data"),
        ]
    )

    assert code == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert [item["character_id"] for item in payload["characters"]] == [
        "xingxi_pixel_pet",
        "ikaros_pixel_pet",
        "nairong_pixel_pet",
    ]
    assert all(item["voice_provider"] == "http_emoti_voice" for item in payload["characters"])
    assert payload["interaction_loop"]["ok"] is True
    assert payload["voice"]["skipped"] is True

