from __future__ import annotations

import shutil
from pathlib import Path

from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.memory_album_controller import MemoryAlbumController
from guanghe_companion.memory_album_qt import create_memory_album_widget
from guanghe_companion.plugin_center_controller import PluginCenterController
from guanghe_companion.plugin_center_qt import create_plugin_center_widget
from guanghe_companion.plugin_subsystem import PluginSubsystem
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController
from guanghe_companion.focus_companion_qt import create_focus_companion_widget


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _album(tmp_path: Path, character_id: str, title: str) -> MemoryAlbumController:
    story = CompanionStoryRuntime.create(user_data_root=tmp_path, character_id=character_id)
    story.memory.remember(
        kind="共同日常",
        title=title,
        summary="一段可验证的共同经历。",
        source="test",
        now=10,
        user_confirmed=True,
    )
    return MemoryAlbumController(story)


def test_memory_album_widget_rebinds_after_character_switch(tmp_path: Path):
    _app()
    first = _album(tmp_path, "xingxi_pixel_pet", "星汐的回忆")
    second = _album(tmp_path, "ikaros_pixel_pet", "伊卡洛斯的回忆")

    class Host:
        memory_album_controller = first

    host = Host()
    widget = create_memory_album_widget(host)
    assert "星汐的回忆" in widget.memory_list.item(1).text()

    host.memory_album_controller = second
    widget.refresh_memory_album()

    assert "伊卡洛斯的回忆" in widget.memory_list.item(1).text()
    assert {button.text() for button in widget.memory_action_buttons} == {
        "固定",
        "纠正",
        "忘记",
        "查看来源",
    }


def test_plugin_center_widget_exposes_lifecycle_and_panel_controls(tmp_path: Path):
    _app()
    app_root = tmp_path / "app"
    app_root.mkdir()
    shutil.copytree(Path(__file__).resolve().parents[1] / "plugins", app_root / "plugins")
    subsystem = PluginSubsystem(application_root=app_root, user_data_root=tmp_path / "user")
    subsystem.start()
    center = PluginCenterController(subsystem)
    center.set_enabled("emoti.bundled.stargazing", True)

    try:
        widget = create_plugin_center_widget(center)
        labels = {button.text() for button in widget.plugin_action_buttons}
        assert {"卸载", "清除数据", "解除隔离"} <= labels
        assert "同进程 Python 插件属于可信代码" in widget.plugin_trust_notice.text()
        assert "星图角落" in widget.plugin_panels.toPlainText()
    finally:
        subsystem.shutdown()


def test_focus_widget_exposes_explicit_opt_in(tmp_path: Path):
    _app()
    controller = PluginEnabledCompanionController(
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    try:
        widget = create_focus_companion_widget(controller)
        assert widget.focus_enabled_check.text() == "启用低频探头判断"
        assert widget.focus_enabled_check.isChecked() is False
        widget.focus_enabled_check.setChecked(True)
        assert controller.story_runtime.focus.settings.enabled is True
    finally:
        controller.close()
