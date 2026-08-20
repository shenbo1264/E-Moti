from __future__ import annotations

from pathlib import Path

from guanghe_companion.plugin_manifest import discover_plugin_candidates
from guanghe_companion.plugin_runtime import PluginRuntime


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_bundled_capability_contracts_define_five_replaceable_services(tmp_path: Path) -> None:
    candidate = discover_plugin_candidates([REPO_ROOT / "plugins" / "capability_contracts"])[0]
    runtime = PluginRuntime(data_root=tmp_path / "data")

    runtime.load(candidate)

    service_ids = {item.service_id for item in runtime.list_service_definitions()}
    assert service_ids == {
        "emoti.llm.expression",
        "emoti.voice.tts",
        "emoti.voice.asr",
        "emoti.context.screen-summary",
        "emoti.context.web-search",
    }
    runtime.unload("emoti.core.capability-contracts")
    assert runtime.list_service_definitions() == ()
