import pytest

import guanghe_companion.controller as controller_module
import guanghe_companion.storage as storage_module


@pytest.fixture(autouse=True)
def isolate_default_save_path(tmp_path, monkeypatch):
    isolated_path = tmp_path / "companion_save.json"
    monkeypatch.setattr(controller_module, "DEFAULT_SAVE_PATH", isolated_path)
    monkeypatch.setattr(storage_module, "DEFAULT_SAVE_PATH", isolated_path)
