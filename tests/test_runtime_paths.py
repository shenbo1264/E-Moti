from pathlib import Path


def test_source_assets_root_points_to_repo_assets():
    from guanghe_companion.runtime_paths import assets_root, companion_assets_root

    root = assets_root()

    assert root.name == "assets"
    assert (root / "companion" / "original_oc" / "character.json").is_file()
    assert companion_assets_root() == root / "companion"


def test_frozen_assets_root_prefers_pyinstaller_meipass(monkeypatch, tmp_path):
    from guanghe_companion.runtime_paths import assets_root

    bundle_root = tmp_path / "_internal"
    expected = bundle_root / "assets"
    expected.mkdir(parents=True)
    exe_path = tmp_path / "E-Moti.exe"
    exe_path.write_text("", encoding="utf-8")

    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys._MEIPASS", str(bundle_root), raising=False)
    monkeypatch.setattr("sys.executable", str(exe_path))

    assert assets_root() == expected


def test_frozen_voice_services_root_prefers_pyinstaller_meipass(monkeypatch, tmp_path):
    from guanghe_companion.runtime_paths import voice_services_root

    bundle_root = tmp_path / "_internal"
    expected = bundle_root / "voice_services"
    expected.mkdir(parents=True)
    exe_path = tmp_path / "E-Moti.exe"
    exe_path.write_text("", encoding="utf-8")

    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys._MEIPASS", str(bundle_root), raising=False)
    monkeypatch.setattr("sys.executable", str(exe_path))

    assert voice_services_root() == expected


def test_frozen_save_paths_use_local_app_data(monkeypatch, tmp_path):
    from guanghe_companion.runtime_paths import default_save_path, demo_save_path, user_data_dir

    local_app_data = tmp_path / "LocalAppData"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setattr("sys.frozen", True, raising=False)

    assert user_data_dir() == local_app_data / "E-Moti"
    assert default_save_path() == local_app_data / "E-Moti" / "companion_save.json"
    assert demo_save_path() == local_app_data / "E-Moti" / "companion_demo_save.json"


def test_user_data_dir_can_be_overridden_for_smoke_runs(monkeypatch, tmp_path):
    from guanghe_companion.runtime_paths import default_save_path, dialogue_history_path, user_data_dir

    override = tmp_path / "runtime-data"
    monkeypatch.setenv("E_MOTI_USER_DATA_DIR", str(override))

    assert user_data_dir() == override
    assert default_save_path() == override / "companion_save.json"
    assert dialogue_history_path() == override / "dialogue_history.json"


def test_capability_paths_use_user_data_dir(monkeypatch, tmp_path):
    from guanghe_companion.runtime_paths import capability_settings_path, long_term_memory_path, tts_cache_dir

    override = tmp_path / "runtime-data"
    monkeypatch.setenv("E_MOTI_USER_DATA_DIR", str(override))

    assert capability_settings_path() == override / "capability_settings.json"
    assert long_term_memory_path() == override / "long_term_memory.json"
    assert tts_cache_dir() == override / "cache" / "tts"
