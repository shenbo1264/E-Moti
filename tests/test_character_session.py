from pathlib import Path

from guanghe_companion.character_session import CharacterSessionPaths, build_character_session_paths


def test_character_session_paths_are_isolated_by_character_id(tmp_path):
    first = build_character_session_paths("quiet_nebula", user_data_root=tmp_path)
    second = build_character_session_paths("solar_mender", user_data_root=tmp_path)

    assert first.character_dir == tmp_path / "characters" / "quiet_nebula"
    assert first.save_path == first.character_dir / "companion_save.json"
    assert first.dialogue_history_path == first.character_dir / "dialogue_history.json"
    assert first.long_term_memory_path == first.character_dir / "long_term_memory.json"
    assert first.expression_settings_path == first.character_dir / "expression_settings.json"
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
