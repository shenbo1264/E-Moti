from pathlib import Path

from guanghe_companion.character_session import (
    CharacterSessionPaths,
    build_character_session_paths,
    write_character_session_pack_metadata,
)


def test_character_session_paths_are_isolated_by_character_id(tmp_path):
    first = build_character_session_paths("quiet_nebula", user_data_root=tmp_path)
    second = build_character_session_paths("solar_mender", user_data_root=tmp_path)

    assert first.character_dir == tmp_path / "characters" / "quiet_nebula"
    assert first.save_path == first.character_dir / "companion_save.json"
    assert first.dialogue_history_path == first.character_dir / "dialogue_history.json"
    assert first.long_term_memory_path == first.character_dir / "long_term_memory.json"
    assert first.expression_settings_path == first.character_dir / "expression_settings.json"
    assert first.pack_metadata_path == first.character_dir / "pack_metadata.json"
    assert first != second


def test_character_session_paths_reject_unsafe_character_ids(tmp_path):
    for character_id in ("../bad", "BadName", "bad-name", "", "星汐"):
        try:
            build_character_session_paths(character_id, user_data_root=tmp_path)
        except ValueError as exc:
            assert "unsafe character_id" in str(exc)
        else:
            raise AssertionError(f"{character_id!r} should be rejected")


def test_character_session_paths_accept_path_like_user_data_root(tmp_path):
    paths = build_character_session_paths("quiet_nebula", user_data_root=Path(tmp_path))

    assert isinstance(paths, CharacterSessionPaths)
    assert paths.character_dir.parent == tmp_path / "characters"


def test_character_session_pack_metadata_paths_are_isolated(tmp_path):
    first = build_character_session_paths("quiet_nebula", user_data_root=tmp_path)
    second = build_character_session_paths("solar_mender", user_data_root=tmp_path)

    assert first.pack_metadata_path.parent == first.character_dir
    assert second.pack_metadata_path.parent == second.character_dir
    assert first.pack_metadata_path != second.pack_metadata_path


def test_write_character_session_pack_metadata_records_pack_boundary(tmp_path):
    paths = build_character_session_paths("quiet_nebula", user_data_root=tmp_path)

    payload = write_character_session_pack_metadata(
        paths,
        pack_name="Quiet Nebula",
        asset_dir=tmp_path / "assets" / "quiet_nebula",
        renderer_backend="sprite",
        spritesheet="spritesheet.png",
    )

    assert paths.pack_metadata_path.exists()
    assert payload["schema_version"] == 1
    assert payload["character_id"] == "quiet_nebula"
    assert payload["pack_name"] == "Quiet Nebula"
    assert payload["asset_dir"] == str(tmp_path / "assets" / "quiet_nebula")
    assert payload["renderer_backend"] == "sprite"
    assert payload["spritesheet"] == "spritesheet.png"
