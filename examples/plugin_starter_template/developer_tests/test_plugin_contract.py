from pathlib import Path
from guanghe_companion.plugin_manifest import load_plugin_manifest


def test_manifest_is_valid():
    root = Path(__file__).resolve().parents[1] / "plugin"
    manifest = load_plugin_manifest(root / "emoti-plugin.json")
    assert manifest.plugin_id == "emoti.community.my-first-plugin"
