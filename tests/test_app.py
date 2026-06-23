import time
import json

import pytest
from PIL import Image


def make_window(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    controller = make_controller(tmp_path)
    window = CompanionWindow(controller=controller)
    window.show()
    app.processEvents()
    return app, window


def make_controller(tmp_path, ai_expressor=None):
    from guanghe_companion.controller import CompanionController

    return CompanionController(save_path=tmp_path / "save.json", auto_load=False, ai_expressor=ai_expressor)


def write_ui_character_pack(
    root,
    character_id,
    *,
    name,
    title,
    distribution_boundary="shareable_after_review",
    tts_profile=None,
):
    pack_dir = root / character_id
    (pack_dir / "item_icons").mkdir(parents=True)
    (pack_dir / "preview").mkdir()
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    Image.new("RGBA", (32, 32), (40, 80, 120, 255)).save(pack_dir / "item_icons" / "snack.png")
    Image.new("RGBA", (64, 64), (40, 80, 120, 255)).save(pack_dir / "preview" / "contact-sheet.png")
    character_payload = {
        "character_id": character_id,
        "name": name,
        "title": title,
        "description": f"{name} 是一个原创桌面伴侣。",
        "distribution_boundary": distribution_boundary,
        "spritesheet": "spritesheet.png",
        "motion_manifest": "motion_manifest.json",
        "default_mode": "Calm",
        "modes": ["Calm"],
        "mode_descriptions": {"Calm": "安静回应。"},
        "motion_labels": {"Default": "安静待机", "Shop": "补给", "Eat": "收下点心"},
    }
    if tts_profile is not None:
        character_payload["tts_profile"] = tts_profile
    (pack_dir / "character.json").write_text(
        json.dumps(character_payload, ensure_ascii=False),
        encoding="utf-8",
    )
    (pack_dir / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 8,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
            }
        ),
        encoding="utf-8",
    )
    (pack_dir / "dialogue_style.json").write_text(
        json.dumps(
            {"tone": "安静、清晰", "keywords": ["桌面", "陪伴"], "fallback_style": "短句回应"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pack_dir / "shop_items.json").write_text(
        json.dumps(
            [
                {
                    "item_id": "snack",
                    "name": "小点心",
                    "category": "food",
                    "icon": "item_icons/snack.png",
                    "price": 1,
                    "effects": {"mood": 1},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return pack_dir


def add_ui_portrait_renderer(pack_dir):
    (pack_dir / "portraits").mkdir()
    expressions = {
        "neutral": "portraits/neutral.png",
        "smile": "portraits/smile.png",
        "thinking": "portraits/thinking.png",
        "surprised": "portraits/surprised.png",
        "sad": "portraits/sad.png",
        "sleepy": "portraits/sleepy.png",
    }
    for relative_path in expressions.values():
        Image.new("RGBA", (256, 384), (40, 80, 120, 255)).save(pack_dir / relative_path)
    (pack_dir / "portrait_manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "fallback_expression": "neutral",
                "anchor": "bottom_center",
                "default_scale": 1.0,
                "expressions": expressions,
            }
        ),
        encoding="utf-8",
    )
    character_path = pack_dir / "character.json"
    payload = json.loads(character_path.read_text(encoding="utf-8"))
    payload["renderer"] = {
        "backend": "portrait",
        "portrait_manifest": "portrait_manifest.json",
        "expression_map": {"focused": "thinking", "excited": "smile"},
    }
    character_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def patch_ui_character_assets(monkeypatch, root):
    import guanghe_companion.character_pack as character_pack_module
    import guanghe_companion.motion as motion_module
    import guanghe_companion.shop_items as shop_items_module

    monkeypatch.setattr(character_pack_module, "ASSETS_ROOT", root)
    monkeypatch.setattr(motion_module, "ASSETS_ROOT", root)
    monkeypatch.setattr(shop_items_module, "ASSETS_ROOT", root)


class FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in tuple(self._callbacks):
            callback(*args)


class FakeSystemTrayIcon:
    class ActivationReason:
        Trigger = object()
        DoubleClick = object()

    class MessageIcon:
        Information = object()

    available = True
    instances = []

    def __init__(self, icon=None, parent=None):
        self.icon = icon
        self.parent = parent
        self.context_menu = None
        self.tool_tip = ""
        self.visible = False
        self.messages = []
        self.activated = FakeSignal()
        self.__class__.instances.append(self)

    @classmethod
    def isSystemTrayAvailable(cls):
        return cls.available

    def setToolTip(self, text):
        self.tool_tip = text

    def setContextMenu(self, menu):
        self.context_menu = menu

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def showMessage(self, title, message, icon=None, msecs=0):
        self.messages.append((title, message, icon, msecs))


@pytest.fixture(autouse=True)
def disable_system_tray_by_default(monkeypatch):
    import guanghe_companion.app as app_module

    FakeSystemTrayIcon.instances = []
    FakeSystemTrayIcon.available = False
    monkeypatch.setattr(app_module, "QSystemTrayIcon", FakeSystemTrayIcon, raising=False)
    yield

    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for widget in list(QApplication.topLevelWidgets()):
        for timer_name in (
            "frame_timer",
            "tick_timer",
            "countdown_timer",
            "screen_observation_timer",
        ):
            timer = getattr(widget, timer_name, None)
            if timer is not None:
                timer.stop()
        tray_controller = getattr(widget, "tray_controller", None)
        if tray_controller is not None:
            tray_controller.force_exit = True
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def test_sprite_drag_uses_global_cursor_delta_when_window_moves(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import SpriteInteractionLabel

    app = QApplication.instance() or QApplication([])
    drag_deltas = []
    label = SpriteInteractionLabel(
        on_click=lambda: None,
        on_drag=lambda: None,
        on_drag_move=drag_deltas.append,
    )
    label.show()
    app.processEvents()

    label.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    label.mouseMoveEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(10, 10),
            QPointF(124, 100),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert drag_deltas == [QPoint(24, 0)]

    label.close()
    app.processEvents()


def test_companion_window_character_panel_omits_obsolete_placeholder_copy(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    text = window.character_label.text()

    assert "星汐" in text
    assert "程序化占位" not in text
    assert "后续可直接替换" not in text
    assert "正式角色包资产" not in text

    window.close()
    app.processEvents()


def test_companion_window_title_positions_xingxi_as_desktop_companion(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert window.windowTitle() == "星汐 E-Moti 桌面伴侣"

    window.close()
    app.processEvents()


def test_application_style_uses_fusion_and_chinese_font(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import configure_application_style

    app = QApplication.instance() or QApplication([])

    assert configure_application_style(app) is True
    assert app.font().family() in {"Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Arial"}
    assert "QGroupBox" in app.styleSheet()
    assert "font-family" in app.styleSheet()


def test_companion_font_loader_adds_available_cjk_font_files(tmp_path):
    from guanghe_companion import app as app_module

    font_file = tmp_path / "msyh.ttc"
    font_file.write_bytes(b"fake-font")

    class FakeFontDatabase:
        loaded_paths: list[str] = []

        @staticmethod
        def addApplicationFont(path: str) -> int:
            FakeFontDatabase.loaded_paths.append(path)
            return 7

        @staticmethod
        def applicationFontFamilies(font_id: int) -> list[str]:
            assert font_id == 7
            return ["Microsoft YaHei UI", "Microsoft YaHei"]

    families = app_module.load_companion_font_files(
        candidates=(tmp_path / "missing.ttc", font_file),
        font_database=FakeFontDatabase,
    )

    assert families == ("Microsoft YaHei UI", "Microsoft YaHei")
    assert FakeFontDatabase.loaded_paths == [str(font_file)]


def test_application_style_attempts_to_load_companion_fonts(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion import app as app_module

    calls: list[bool] = []
    monkeypatch.setattr(
        app_module,
        "ensure_companion_font_files_loaded",
        lambda: calls.append(True) or ("Microsoft YaHei UI",),
    )
    app = QApplication.instance() or QApplication([])

    assert app_module.configure_application_style(app) is True
    assert calls == [True]


def test_control_panel_presents_desktop_pet_as_primary_launch(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert window.launcher_title_label.text() == "星汐 E-Moti"
    assert "桌宠模式" in window.launcher_subtitle_label.text()
    assert window.enter_desktop_mode_button.text() == "进入桌宠模式"
    assert window.enter_desktop_mode_button.objectName() == "PrimaryLaunchButton"

    window.close()
    app.processEvents()


def test_control_panel_launches_separate_desktop_pet_window(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window.enter_desktop_mode_button.click()
    app.processEvents()

    pet_window = window.desktop_pet_window
    assert window.desktop_mode is False
    assert window.status_card.isVisibleTo(window)
    assert pet_window is not window
    assert pet_window.desktop_mode is True
    assert pet_window.presentation_renderer.backend == "sprite"
    assert pet_window.sprite_label.isVisibleTo(pet_window)
    assert not pet_window.spirit_surface.isVisibleTo(pet_window)
    assert not pet_window.tick_timer.isActive()

    pet_window.close()
    app.processEvents()

    assert window.desktop_pet_window is None

    window.close()
    app.processEvents()


def test_control_panel_uses_readable_chinese_status_labels(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert [label.text() for label in window.stat_name_labels] == ["专注", "能量", "稳定", "心情", "信任"]
    assert "金币" in window.resources_label.text()
    assert "coins" not in window.resources_label.text()
    assert "level" not in window.resources_label.text()

    window.close()
    app.processEvents()


def test_control_panel_surfaces_session_goal_and_recent_moment(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert "interact_twice" in window.session_goal_label.text()
    assert "touch" in window.session_goal_label.text()
    assert "recent_moment:none" in window.recent_moment_label.text()

    snapshot = window.controller.trigger_demo_proactive("return_idle", include_ai_expression=False)
    window._apply_snapshot(snapshot)

    assert "return_after_idle" in window.recent_moment_label.text()
    assert "deterministic_proactive" in window.recent_moment_label.text()

    window.close()
    app.processEvents()


def test_control_panel_has_settings_center_navigation(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert window.navigation_hint_label.text() == "控制中心"
    assert [button.text() for button in window.navigation_buttons] == [
        "总览",
        "互动",
        "背包",
        "角色库",
        "感知与搜索",
        "隐私",
        "LLM表达",
        "表达规则",
        "语音",
    ]

    window.close()
    app.processEvents()


def test_control_panel_navigation_switches_right_hand_pages(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert window.content_stack.currentIndex() == 0
    assert window.hero_card.isVisibleTo(window)

    window.navigation_buttons[2].click()
    app.processEvents()

    assert window.content_stack.currentIndex() == 2
    assert window.shop_card.isVisibleTo(window)
    assert window.inventory_card.isVisibleTo(window)
    assert not window.hero_card.isVisibleTo(window)

    window.navigation_buttons[3].click()
    app.processEvents()

    assert window.content_stack.currentIndex() == 3
    assert window.character_library_page.isVisibleTo(window)

    window.navigation_buttons[4].click()
    app.processEvents()

    assert window.content_stack.currentIndex() == 4
    assert window.perception_search_page.isVisibleTo(window)
    assert not window.shop_card.isVisibleTo(window)

    window.navigation_buttons[5].click()
    app.processEvents()

    assert window.content_stack.currentIndex() == 5
    assert window.perception_card.isVisibleTo(window)
    assert not window.shop_card.isVisibleTo(window)

    window.close()
    app.processEvents()


def test_character_library_lists_and_switches_character_packs(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    write_ui_character_pack(assets_root, "xingxi_pixel_pet", name="星汐", title="像素桌面同伴")
    write_ui_character_pack(assets_root, "custom_character", name="澄光", title="桌面回声同伴")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="xingxi_pixel_pet",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller)
    window.show()
    app.processEvents()

    window.navigation_buttons[3].click()
    app.processEvents()

    assert window.character_list.count() == 2
    assert [window.character_list.item(index).text() for index in range(window.character_list.count())] == [
        "澄光 | 桌面回声同伴",
        "星汐 | 像素桌面同伴",
    ]
    assert "课程提交角色" in window.character_list.item(0).toolTip()
    assert "默认提交角色" in window.character_list.item(1).toolTip()
    window.character_list.setCurrentRow(0)
    window.character_switch_button.click()
    app.processEvents()

    assert window.controller.state.character_id == "custom_character"
    assert "澄光" in window.character_label.text()
    assert window.dialogue_input.placeholderText() == "和澄光说点什么"
    assert not window.spritesheet.isNull()

    window.close()
    app.processEvents()


def test_character_library_shows_pack_distribution_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    pack_dir = write_ui_character_pack(assets_root, "xingxi_pixel_pet", name="Xingxi", title="Desktop companion")
    (pack_dir / "provenance.md").write_text("# Provenance\n\nOriginal local test pack.", encoding="utf-8")
    (pack_dir / "LICENSE").write_text("Test license.", encoding="utf-8")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="xingxi_pixel_pet",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller)
    window.show()
    app.processEvents()

    window.navigation_buttons[3].click()
    app.processEvents()

    details = window.character_detail_label.text()
    assert "角色定位: 默认提交角色" in details
    assert "来源: 内置角色库" in details
    assert "交付状态: 已纳入课程提交角色库" in details
    assert "来源记录: 已记录" in details
    assert "说明文件: 已记录" in details
    assert "视觉 QA: 未记录" in details
    assert "人工 QA: 未记录" in details
    assert "来源记录: provenance.md" in details
    assert "说明文件: LICENSE" in details
    assert "Warning:" not in details

    window.close()
    app.processEvents()


def test_character_library_detail_metadata_is_scrollable(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    pack_dir = write_ui_character_pack(assets_root, "original_oc", name="星汐", title="桌面频率同伴")
    (pack_dir / "provenance.md").write_text("Original generated pack.", encoding="utf-8")
    (pack_dir / "LICENSE.md").write_text("Test license.", encoding="utf-8")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="original_oc",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller)
    window.resize(720, 520)
    window.show()
    app.processEvents()

    window.navigation_buttons[3].click()
    app.processEvents()

    assert window.character_detail_scroll_area.widget() is window.character_detail_label
    assert window.character_detail_label.wordWrap()
    assert window.character_detail_label.alignment() & Qt.AlignmentFlag.AlignTop
    assert "交付状态: 已纳入课程提交角色库" in window.character_detail_label.text()
    assert "来源记录: provenance.md" in window.character_detail_label.text()
    assert "说明文件: LICENSE.md" in window.character_detail_label.text()

    window.close()
    app.processEvents()


def test_character_library_profile_preview_uses_large_character_card(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    pack_dir = write_ui_character_pack(assets_root, "xingxi_pixel_pet", name="Xingxi", title="Desktop companion")
    Image.new("RGB", (1024, 1536), (120, 160, 220)).save(pack_dir / "preview" / "profile.png")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="xingxi_pixel_pet",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller)
    window.resize(980, 720)
    window.show()
    app.processEvents()

    window.navigation_buttons[3].click()
    app.processEvents()

    assert window.character_preview_label.minimumHeight() >= 280
    assert window.character_preview_label.pixmap() is not None
    assert window.character_preview_label.pixmap().height() >= 260
    assert window.character_preview_label.pixmap().width() >= 170

    window.close()
    app.processEvents()


def test_character_library_profile_preview_fills_wide_stage_with_art_backdrop(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    pack_dir = write_ui_character_pack(assets_root, "xingxi_pixel_pet", name="Xingxi", title="Desktop companion")
    Image.new("RGB", (1024, 1536), (30, 78, 148)).save(pack_dir / "preview" / "profile.png")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="xingxi_pixel_pet",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller)
    window.resize(1100, 740)
    window.show()
    app.processEvents()

    window.navigation_buttons[3].click()
    app.processEvents()

    preview = window.character_preview_label.grab().toImage()
    assert preview.width() >= 420
    mid_y = preview.height() // 2
    edge_samples = (
        QColor(preview.pixel(24, mid_y)),
        QColor(preview.pixel(preview.width() - 24, mid_y)),
    )
    for sample in edge_samples:
        assert sample.blue() > sample.red() + 12
        assert sample.blue() > sample.green() + 4

    window.close()
    app.processEvents()


def test_character_library_switches_user_character_pack(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("E_MOTI_USER_DATA_DIR", str(tmp_path / "user-data"))
    assets_root = tmp_path / "assets"
    write_ui_character_pack(assets_root, "original_oc", name="星汐", title="桌面频率同伴")
    write_ui_character_pack(
        tmp_path / "user-data" / "character_packs",
        "custom_character",
        name="澄光",
        title="桌面回声同伴",
    )
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="original_oc",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller)
    window._show_message = lambda message: None
    window.show()
    app.processEvents()
    window.navigation_buttons[3].click()
    app.processEvents()

    for index in range(window.character_list.count()):
        item = window.character_list.item(index)
        if item.data(Qt.ItemDataRole.UserRole) == "custom_character":
            window.character_list.setCurrentItem(item)
            break
    window.character_switch_button.click()
    app.processEvents()

    assert window.controller.state.character_id == "custom_character"
    assert window.controller.resources.asset_dir == tmp_path / "user-data" / "character_packs" / "custom_character"
    assert "澄光" in window.character_label.text()

    window.close()
    app.processEvents()


def test_character_library_imports_complete_pack_from_selected_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    write_ui_character_pack(assets_root, "original_oc", name="星汐", title="桌面频率同伴")
    source_pack = write_ui_character_pack(
        tmp_path / "import-source",
        "imported_character",
        name="澄光",
        title="本地导入同伴",
    )
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    import guanghe_companion.app as app_module
    from guanghe_companion.controller import CompanionController

    monkeypatch.setattr(
        app_module.QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(source_pack),
    )
    monkeypatch.setattr(
        app_module.QMessageBox,
        "question",
        lambda *args, **kwargs: app_module.QMessageBox.StandardButton.Yes,
    )
    messages = []
    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="original_oc",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = app_module.CompanionWindow(controller=controller)
    window._show_message = messages.append
    window.show()
    app.processEvents()
    window.navigation_buttons[3].click()
    app.processEvents()

    assert window.character_import_button.isEnabled()
    window.character_import_button.click()
    app.processEvents()

    imported_dir = tmp_path / "user-data" / "character_packs" / "imported_character"
    assert imported_dir.is_dir()
    assert any("imported_character" in message for message in messages)
    for index in range(window.character_list.count()):
        item = window.character_list.item(index)
        if item.data(Qt.ItemDataRole.UserRole) == "imported_character":
            window.character_list.setCurrentItem(item)
            break
    window.character_switch_button.click()
    app.processEvents()

    assert window.controller.state.character_id == "imported_character"
    assert window.controller.resources.asset_dir == imported_dir

    window.close()
    app.processEvents()


def test_character_library_import_confirmation_shows_distribution_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    write_ui_character_pack(assets_root, "original_oc", name="Xingxi", title="Desktop companion")
    source_pack = write_ui_character_pack(
        tmp_path / "import-source",
        "imported_character",
        name="Echo",
        title="Local companion",
        distribution_boundary="local_ugc_only",
    )
    (source_pack / "provenance.md").write_text("Original generated pack.", encoding="utf-8")
    (source_pack / "LICENSE").write_text("Test license.", encoding="utf-8")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication
    import guanghe_companion.app as app_module
    from guanghe_companion.controller import CompanionController

    monkeypatch.setattr(
        app_module.QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(source_pack),
    )
    confirmations = []

    def capture_question(parent, title, text, buttons, default_button):
        confirmations.append((title, text, buttons, default_button))
        return app_module.QMessageBox.StandardButton.Yes

    monkeypatch.setattr(app_module.QMessageBox, "question", capture_question)
    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="original_oc",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = app_module.CompanionWindow(controller=controller)
    window._show_message = lambda message: None
    window.show()
    app.processEvents()
    window.navigation_buttons[3].click()
    app.processEvents()

    window.character_import_button.click()
    app.processEvents()

    assert (tmp_path / "user-data" / "character_packs" / "imported_character").is_dir()
    assert len(confirmations) == 1
    assert "imported_character" in confirmations[0][1]
    assert "来源: import_source" in confirmations[0][1]
    assert "交付状态: 用户导入角色包" in confirmations[0][1]
    assert "来源记录: provenance.md" in confirmations[0][1]
    assert "说明文件: LICENSE" in confirmations[0][1]

    window.close()
    app.processEvents()


def test_character_library_import_confirmation_marks_fanwork_ugc_with_source_note(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    write_ui_character_pack(assets_root, "xingxi_pixel_pet", name="Xingxi", title="Desktop companion")
    source_pack = write_ui_character_pack(
        tmp_path / "import-source",
        "private_fanwork_character",
        name="Fanwork",
        title="Private local pack",
        distribution_boundary="private_local_fanwork",
    )
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication
    import guanghe_companion.app as app_module
    from guanghe_companion.controller import CompanionController

    monkeypatch.setattr(
        app_module.QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(source_pack),
    )
    confirmations = []

    def capture_question(parent, title, text, buttons, default_button):
        confirmations.append(text)
        return app_module.QMessageBox.StandardButton.Yes

    monkeypatch.setattr(app_module.QMessageBox, "question", capture_question)
    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="xingxi_pixel_pet",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = app_module.CompanionWindow(controller=controller)
    window._show_message = lambda message: None
    window.show()
    app.processEvents()
    window.navigation_buttons[3].click()
    app.processEvents()

    window.character_import_button.click()
    app.processEvents()

    assert "扩展角色" in confirmations[0]
    assert "导入后会保留来源记录和 QA 说明" in confirmations[0]
    assert (tmp_path / "user-data" / "character_packs" / "private_fanwork_character").is_dir()

    window.close()
    app.processEvents()


def test_character_library_import_cancel_does_not_copy_pack(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    write_ui_character_pack(assets_root, "original_oc", name="Xingxi", title="Desktop companion")
    source_pack = write_ui_character_pack(
        tmp_path / "import-source",
        "imported_character",
        name="Echo",
        title="Local companion",
    )
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication
    import guanghe_companion.app as app_module
    from guanghe_companion.controller import CompanionController

    monkeypatch.setattr(
        app_module.QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(source_pack),
    )
    monkeypatch.setattr(
        app_module.QMessageBox,
        "question",
        lambda *args, **kwargs: app_module.QMessageBox.StandardButton.Cancel,
    )
    messages = []
    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="original_oc",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = app_module.CompanionWindow(controller=controller)
    window._show_message = messages.append
    window.show()
    app.processEvents()
    window.navigation_buttons[3].click()
    app.processEvents()

    window.character_import_button.click()
    app.processEvents()

    assert not (tmp_path / "user-data" / "character_packs" / "imported_character").exists()
    assert messages == ["Character pack import cancelled."]

    window.close()
    app.processEvents()


def test_character_library_rejects_draft_import_without_copying(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    write_ui_character_pack(assets_root, "original_oc", name="星汐", title="桌面频率同伴")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication
    import guanghe_companion.app as app_module
    from guanghe_companion.character_generation_workflow import CharacterGenerationWorkflow
    from guanghe_companion.controller import CompanionController

    draft = CharacterGenerationWorkflow(output_root=tmp_path / "generated").create_draft(
        {
            "character_id": "draft_echo",
            "name": "Draft Echo",
            "title": "Draft companion",
            "description": "Original draft companion for import validation.",
            "visual_keywords": ["teal"],
            "personality_keywords": ["gentle"],
            "boundaries": ["No third-party IP"],
        }
    )
    monkeypatch.setattr(
        app_module.QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(draft.pack_dir),
    )
    messages = []
    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="original_oc",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = app_module.CompanionWindow(controller=controller)
    window._show_message = messages.append
    window.show()
    app.processEvents()
    window.navigation_buttons[3].click()
    app.processEvents()

    window.character_import_button.click()
    app.processEvents()

    assert not (tmp_path / "user-data" / "character_packs" / "draft_echo").exists()
    assert any("spritesheet not found: spritesheet.png" in message for message in messages)
    assert window.controller.state.character_id == "original_oc"

    window.close()
    app.processEvents()


def test_window_started_with_custom_character_loads_matching_motion_assets(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    write_ui_character_pack(assets_root, "custom_character", name="澄光", title="桌面回声同伴")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="custom_character",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller)
    window.show()
    app.processEvents()

    assert window.motion_catalog.sheet_path == assets_root / "custom_character" / "spritesheet.png"
    assert "澄光" in window.character_label.text()

    window.close()
    app.processEvents()


def test_window_applies_visual_action_motion_without_mutating_controller_state(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    pack_dir = write_ui_character_pack(assets_root, "xingxi_pixel_pet", name="星汐", title="桌面频率同伴")
    motion_manifest_path = pack_dir / "motion_manifest.json"
    motion_manifest = json.loads(motion_manifest_path.read_text(encoding="utf-8"))
    motion_manifest["motions"]["Raised"] = {"row": 7, "frame_count": 1, "fps": 4}
    motion_manifest_path.write_text(json.dumps(motion_manifest), encoding="utf-8")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(
        controller=CompanionController(save_path=tmp_path / "save.json", auto_load=False),
    )
    window.show()
    app.processEvents()
    snapshot = window.controller.get_snapshot()
    assert snapshot["motion"] == "Default"
    assert window.presentation_renderer.backend == "sprite"

    snapshot["visual_actions"] = [
        {
            "type": "motion",
            "id": "Raised",
            "ttl_ms": 1800,
            "priority": 60,
            "source": "llm",
        }
    ]
    window._apply_snapshot(snapshot)
    app.processEvents()

    assert window.motion_animator.current_motion.name == "Raised"
    assert window.controller.get_snapshot()["motion"] == "Default"

    window.close()
    app.processEvents()


def test_desktop_mode_prefers_live2d_surface_for_live2d_renderer(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    pack_dir = write_ui_character_pack(
        assets_root,
        "live2d_character",
        name="Live2D",
        title="Live2D companion",
    )
    (pack_dir / "live2d").mkdir()
    (pack_dir / "live2d" / "Xingxi.model3.json").write_text("{}", encoding="utf-8")
    character_path = pack_dir / "character.json"
    payload = json.loads(character_path.read_text(encoding="utf-8"))
    payload["renderer"] = {
        "backend": "live2d_web",
        "model": "live2d/Xingxi.model3.json",
        "motion_map": {"Play": "TapBody"},
        "expression_map": {"excited": "F02"},
    }
    character_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication, QLabel
    import guanghe_companion.app as app_module
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    class FakeLive2DWebSurface(QLabel):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.loaded_frames = []

        def load_frame(self, frame, asset_dir):
            self.loaded_frames.append((frame, asset_dir))

    monkeypatch.setattr(app_module, "Live2DWebSurface", FakeLive2DWebSurface)

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="live2d_character",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()

    assert window.presentation_renderer.backend == "live2d_web"
    assert window.live2d_surface.isVisibleTo(window)
    assert not window.sprite_label.isVisibleTo(window)
    frame, asset_dir = window.live2d_surface.loaded_frames[-1]
    assert frame.backend == "live2d_web"
    assert frame.model_path == "live2d/Xingxi.model3.json"
    assert asset_dir == pack_dir

    window.close()
    app.processEvents()


def test_live2d_renderer_frame_timer_does_not_restore_sprite_surface(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    pack_dir = write_ui_character_pack(
        assets_root,
        "live2d_character",
        name="Live2D",
        title="Live2D companion",
    )
    (pack_dir / "live2d").mkdir()
    (pack_dir / "live2d" / "Xingxi.model3.json").write_text("{}", encoding="utf-8")
    character_path = pack_dir / "character.json"
    payload = json.loads(character_path.read_text(encoding="utf-8"))
    payload["renderer"] = {
        "backend": "live2d_web",
        "model": "live2d/Xingxi.model3.json",
        "motion_map": {"Play": "TapBody"},
        "expression_map": {"excited": "F02"},
    }
    character_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication, QLabel
    import guanghe_companion.app as app_module
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    class FakeLive2DWebSurface(QLabel):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.loaded_frames = []

        def load_frame(self, frame, asset_dir):
            self.loaded_frames.append((frame, asset_dir))

    monkeypatch.setattr(app_module, "Live2DWebSurface", FakeLive2DWebSurface)

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="live2d_character",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()

    window._advance_frame()
    app.processEvents()

    assert window.live2d_surface.isVisibleTo(window)
    assert not window.sprite_label.isVisibleTo(window)

    window.close()
    app.processEvents()


def test_desktop_mode_prefers_spirit_surface_for_portrait_renderer(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    pack_dir = write_ui_character_pack(
        assets_root,
        "portrait_character",
        name="Portrait",
        title="Portrait companion",
    )
    add_ui_portrait_renderer(pack_dir)
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication, QLabel
    import guanghe_companion.app as app_module
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    class FakeSpiritStageSurface(QLabel):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.loaded_frames = []

        def load_frame(self, frame, asset_dir):
            self.loaded_frames.append((frame, asset_dir))

    monkeypatch.setattr(app_module, "SpiritStageSurface", FakeSpiritStageSurface, raising=False)

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="portrait_character",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()

    assert window.presentation_renderer.backend == "portrait"
    assert window.spirit_surface.isVisibleTo(window)
    assert not window.sprite_label.isVisibleTo(window)
    assert not window.live2d_surface.isVisibleTo(window)
    frame, asset_dir = window.spirit_surface.loaded_frames[-1]
    assert frame.backend == "portrait"
    assert frame.portrait_manifest == "portrait_manifest.json"
    assert frame.portrait_id == "neutral"
    assert asset_dir == pack_dir

    window.close()
    app.processEvents()


def test_portrait_renderer_frame_timer_does_not_restore_sprite_surface(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    pack_dir = write_ui_character_pack(
        assets_root,
        "portrait_character",
        name="Portrait",
        title="Portrait companion",
    )
    add_ui_portrait_renderer(pack_dir)
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication, QLabel
    import guanghe_companion.app as app_module
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    class FakeSpiritStageSurface(QLabel):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.loaded_frames = []

        def load_frame(self, frame, asset_dir):
            self.loaded_frames.append((frame, asset_dir))

    monkeypatch.setattr(app_module, "SpiritStageSurface", FakeSpiritStageSurface, raising=False)

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="portrait_character",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()

    window._advance_frame()
    app.processEvents()

    assert window.presentation_renderer.backend == "portrait"
    assert window.spirit_surface.isVisibleTo(window)
    assert not window.sprite_label.isVisibleTo(window)

    window.close()
    app.processEvents()


def test_desktop_mode_falls_back_to_sprite_when_live2d_model_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    pack_dir = write_ui_character_pack(
        assets_root,
        "live2d_character",
        name="Live2D",
        title="Live2D companion",
    )
    character_path = pack_dir / "character.json"
    payload = json.loads(character_path.read_text(encoding="utf-8"))
    payload["renderer"] = {
        "backend": "live2d_web",
        "model": "live2d/missing.model3.json",
        "motion_map": {"Play": "TapBody"},
        "expression_map": {"excited": "F02"},
    }
    character_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="live2d_character",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()

    assert window.presentation_renderer.backend == "sprite"
    assert window.sprite_label.isVisibleTo(window)
    assert not window.live2d_surface.isVisibleTo(window)

    window.close()
    app.processEvents()


def test_character_switch_updates_open_desktop_pet_window(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    write_ui_character_pack(assets_root, "original_oc", name="星汐", title="桌面频率同伴")
    write_ui_character_pack(assets_root, "custom_character", name="澄光", title="桌面回声同伴")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="original_oc",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller)
    window.show()
    app.processEvents()
    window.enter_desktop_mode_button.click()
    app.processEvents()
    pet_window = window.desktop_pet_window

    window.navigation_buttons[3].click()
    window.character_list.setCurrentRow(0)
    window.character_switch_button.click()
    app.processEvents()

    assert pet_window is not None
    assert pet_window.controller.state.character_id == "custom_character"
    assert pet_window.motion_catalog.sheet_path == assets_root / "custom_character" / "spritesheet.png"
    assert "澄光" in pet_window.character_label.text()

    pet_window.close()
    window.close()
    app.processEvents()


def test_character_switch_preserves_manual_perception_expression_context(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    write_ui_character_pack(assets_root, "original_oc", name="鏄熸睈", title="妗岄潰棰戠巼鍚屼即")
    write_ui_character_pack(assets_root, "custom_character", name="婢勫厜", title="妗岄潰鍥炲０鍚屼即")
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox
    from guanghe_companion.app import CompanionWindow, MANUAL_PERCEPTION_NO_SCREEN_SUMMARY
    from guanghe_companion.controller import CompanionController

    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, message: None)
    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="original_oc",
        user_data_root=tmp_path / "user-data",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller)
    window.show()
    app.processEvents()

    window.navigation_buttons[3].click()
    for index in range(window.character_list.count()):
        item = window.character_list.item(index)
        if item.data(Qt.ItemDataRole.UserRole) == "custom_character":
            window.character_list.setCurrentItem(item)
            break
    window.character_switch_button.click()
    app.processEvents()

    window.observe_screen_button.click()
    app.processEvents()
    context = window.controller.expression_context_provider()

    assert context["perception_summary"] == MANUAL_PERCEPTION_NO_SCREEN_SUMMARY

    window.close()
    app.processEvents()


def test_window_event_panel_uses_presentational_summary_not_raw_json(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window._handle_action("touch")
    app.processEvents()
    text = window.events_label.text()

    assert "{" not in text
    assert "}" not in text
    assert "星汐" in text
    assert "状态" in text
    assert "可选动作" in text

    window.close()
    app.processEvents()


def test_desktop_mode_uses_pet_window_chrome_and_hides_control_panels(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)

    flags = window.windowFlags()

    assert bool(flags & Qt.WindowType.FramelessWindowHint)
    assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)
    assert bool(flags & Qt.WindowType.NoDropShadowWindowHint)
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.hero_card.isVisibleTo(window)
    assert window.status_card.isHidden()
    assert window.feedback_card.isHidden()
    assert window.actions_card.isHidden()
    assert window.shop_card.isHidden()
    assert window.inventory_card.isHidden()
    assert window.screen_observation_settings_card.isHidden()
    assert window.web_search_settings_card.isHidden()
    assert window.expression_settings_card.isHidden()
    assert window.expression_rule_card.isHidden()
    assert window.voice_settings_card.isHidden()

    window.close()
    app.processEvents()


def test_desktop_mode_shows_primary_surface_with_dialogue_controls_after_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    assert window.width() <= 360
    assert window.height() <= 430
    assert window.hero_card.title() == ""
    assert window.root_widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.hero_card.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.sprite_label.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.spirit_surface.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert "border: none" in window.hero_card.styleSheet()
    assert "background: transparent" in window.sprite_label.styleSheet()
    assert window.presentation_renderer.backend == "sprite"
    assert window.sprite_label.isVisibleTo(window)
    assert not window.spirit_surface.isVisibleTo(window)
    assert window.mask().isEmpty()
    assert not window.character_label.isVisibleTo(window)
    assert not window.desktop_feedback_label.isVisibleTo(window)
    assert window.dialogue_input.isVisibleTo(window)
    assert window.dialogue_send_button.isVisibleTo(window)

    window.close()
    app.processEvents()


def test_desktop_mode_uses_native_pixel_pet_surface_size(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import (
        CompanionWindow,
        DESKTOP_SPRITE_HEIGHT,
        DESKTOP_SPRITE_WIDTH,
        DESKTOP_WINDOW_HEIGHT,
        DESKTOP_WINDOW_WIDTH,
    )

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    assert (DESKTOP_SPRITE_WIDTH, DESKTOP_SPRITE_HEIGHT) == (192, 208)
    assert (DESKTOP_WINDOW_WIDTH, DESKTOP_WINDOW_HEIGHT) == (260, 312)
    assert (window.sprite_label.width(), window.sprite_label.height()) == (192, 208)
    assert (window.width(), window.height()) == (260, 312)

    window.close()
    app.processEvents()


def test_desktop_sprite_backend_renders_without_upscaling_pixel_frame(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow, DESKTOP_SPRITE_HEIGHT, DESKTOP_SPRITE_WIDTH
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        save_path=tmp_path / "save.json",
        character_id="xingxi_pixel_pet",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()

    assert window.presentation_renderer.backend == "sprite"
    pixmap = window.sprite_label.pixmap()
    assert pixmap is not None
    assert not pixmap.isNull()
    assert pixmap.width() <= DESKTOP_SPRITE_WIDTH
    assert pixmap.height() <= DESKTOP_SPRITE_HEIGHT

    window.close()
    app.processEvents()


def test_desktop_pet_has_dialogue_input_and_send_button(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    assert window.dialogue_input.placeholderText() == "和星汐说点什么"
    assert window.dialogue_send_button.text() == "发送"
    assert window.dialogue_input.isVisibleTo(window)
    assert window.dialogue_send_button.isVisibleTo(window)

    window.close()
    app.processEvents()


def test_desktop_pet_dialogue_send_shows_xingxi_response_without_growth_settlement(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    window.dialogue_input.setText("今天陪我一会儿")
    window.dialogue_send_button.click()
    app.processEvents()

    after = window.controller.get_typed_snapshot()
    assert window.dialogue_input.text() == ""
    assert window.desktop_feedback_label.isVisibleTo(window)
    assert "今天陪我一会儿" in window.desktop_feedback_label.text()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_dialogue_submit_uses_enabled_llm_expression_without_growth_mutation(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.expression_settings import normalize_expression_settings

    class FakeExpressor:
        def __init__(self):
            self.last_fallback_reason = None
            self.requests = []

        def express(self, snapshot, effect=None):
            self.requests.append((snapshot, effect))
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "我会陪你慢慢说。",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    app = QApplication.instance() or QApplication([])
    fake_expressor = FakeExpressor()
    controller = make_controller(tmp_path, ai_expressor=fake_expressor)
    controller.update_expression_settings(
        normalize_expression_settings(
            {
                "enabled": True,
                "provider": "custom",
                "model": "local-model",
                "base_url": "http://127.0.0.1:1234/v1",
                "api_key": "",
            }
        )
    )
    controller.ai_expressor = fake_expressor
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    window.dialogue_input.setText("今天有点累")
    window.dialogue_send_button.click()
    app.processEvents()

    after = window.controller.get_typed_snapshot()
    assert fake_expressor.requests
    assert fake_expressor.requests[-1][1] == "ATTENTION"
    assert "我会陪你慢慢说。" in window.desktop_feedback_label.text()
    assert "我会陪你慢慢说。" in window.events_label.text()
    assert window.dialogue_input.text() == ""
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_desktop_mode_context_menu_status_panel_shows_feedback(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication, QMessageBox

    from guanghe_companion.app import CompanionWindow

    captured = {}

    def fake_information(parent, title, message):
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(QMessageBox, "information", fake_information)
    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    menu = window._build_desktop_context_menu()
    menu.actions()[0].trigger()
    app.processEvents()

    assert captured["title"] == "状态面板"
    assert "模式" in captured["message"]
    assert "能量 65" in captured["message"]
    assert "心情 58" in captured["message"]
    assert "信任 5" in captured["message"]
    assert "{" not in captured["message"]
    assert "STAT" not in captured["message"]
    assert "CHOICE" not in captured["message"]

    window.close()
    app.processEvents()


def test_desktop_mode_feedback_overlay_updates_after_sprite_touch(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    QTest.mouseClick(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(24, 24))
    app.processEvents()
    text = window.snapshot_renderer.format_desktop_status_panel(window.controller.get_snapshot())

    assert "模式：Calm" in text
    assert "招手回应" in text
    assert "靠近我的方式" in text
    assert window.controller.get_snapshot()["motion"] == "TouchHead"

    window.close()
    app.processEvents()


def test_desktop_mode_context_menu_returns_to_control_panel(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    menu = window._build_desktop_context_menu()
    labels = [action.text() for action in menu.actions() if not action.isSeparator()]

    assert labels == ["状态面板", "对话历史", "清屏", "复制对话", "回放上一句", "回溯上一轮", "返回控制面板", "退出"]

    labels_to_actions = {action.text(): action for action in menu.actions() if not action.isSeparator()}
    labels_to_actions["返回控制面板"].trigger()
    app.processEvents()
    flags = window.windowFlags()

    assert window.desktop_mode is False
    assert not bool(flags & Qt.WindowType.FramelessWindowHint)
    assert not bool(flags & Qt.WindowType.WindowStaysOnTopHint)
    assert not window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.launcher_card.isVisibleTo(window)
    assert window.sidebar_card.isVisibleTo(window)
    assert window.content_stack.currentIndex() == 0
    assert window.status_card.isVisibleTo(window)
    assert window.feedback_card.isVisibleTo(window)
    assert not window.actions_card.isVisibleTo(window)
    assert not window.demo_card.isVisibleTo(window)
    assert not window.perception_card.isVisibleTo(window)
    assert not window.shop_card.isVisibleTo(window)
    assert not window.inventory_card.isVisibleTo(window)
    assert not window.expression_settings_card.isVisibleTo(window)
    assert not window.expression_rule_card.isVisibleTo(window)
    assert not window.voice_settings_card.isVisibleTo(window)
    assert window.character_label.isVisibleTo(window)
    assert window.desktop_feedback_label.isHidden()
    assert window.mask().isEmpty()
    assert window.controller.get_snapshot()["motion"] == "Default"

    window.close()
    app.processEvents()


def test_desktop_mode_sprite_right_click_opens_context_menu(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    captured = {}

    def fake_show_desktop_context_menu(global_pos):
        captured["global_pos"] = global_pos

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window._show_desktop_context_menu = fake_show_desktop_context_menu
    window.show()
    app.processEvents()

    window.sprite_label.customContextMenuRequested.emit(QPoint(18, 18))
    app.processEvents()

    assert isinstance(captured["global_pos"], QPoint)

    window.close()
    app.processEvents()


def test_desktop_mode_context_menu_exit_closes_window_and_controller(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    class CloseAwareController(CompanionController):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.close_calls = 0

        def close(self):
            if self.close_calls:
                return
            self.close_calls += 1
            super().close()

    app = QApplication.instance() or QApplication([])
    controller = CloseAwareController(save_path=tmp_path / "save.json", auto_load=False)
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()

    menu = window._build_desktop_context_menu()
    labels_to_actions = {action.text(): action for action in menu.actions() if not action.isSeparator()}
    labels_to_actions["退出"].trigger()
    app.processEvents()

    assert not window.isVisible()
    assert controller.close_calls == 1


def test_desktop_pet_history_menu_shows_copies_replays_reverts_and_clears_dialogue(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication, QMessageBox

    from guanghe_companion.app import CompanionWindow

    captured_messages = []

    def fake_information(parent, title, message):
        captured_messages.append((title, message))

    monkeypatch.setattr(QMessageBox, "information", fake_information)
    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.show()
    app.processEvents()

    window.dialogue_input.setText("第一句")
    window.dialogue_send_button.click()
    window.dialogue_input.setText("第二句")
    window.dialogue_send_button.click()
    app.processEvents()

    menu = window._build_desktop_context_menu()
    labels_to_actions = {action.text(): action for action in menu.actions() if not action.isSeparator()}

    labels_to_actions["对话历史"].trigger()
    app.processEvents()
    assert captured_messages[-1][0] == "对话历史"
    assert "你：第一句" in captured_messages[-1][1]
    assert "星汐：" in captured_messages[-1][1]
    assert "{" not in captured_messages[-1][1]

    labels_to_actions["复制对话"].trigger()
    app.processEvents()
    assert "你：第二句" in QApplication.clipboard().text()

    labels_to_actions["回放上一句"].trigger()
    app.processEvents()
    assert "第二句" in window.desktop_feedback_label.text()

    labels_to_actions["回溯上一轮"].trigger()
    app.processEvents()
    assert "第一句" in window.desktop_feedback_label.text()

    labels_to_actions["清屏"].trigger()
    app.processEvents()
    assert window.controller.get_snapshot()["dialogue_history"] == []
    assert "清屏" in window.controller.get_snapshot()["feedback"]

    window.close()
    app.processEvents()


def test_should_use_desktop_mode_accepts_pet_mode_alias():
    from guanghe_companion.app import should_use_desktop_mode

    assert should_use_desktop_mode(["demo", "--desktop-mode"]) is True
    assert should_use_desktop_mode(["demo", "--pet-mode"]) is True
    assert should_use_desktop_mode(["demo"]) is False


def test_clicking_sprite_area_performs_touch_action(monkeypatch, tmp_path):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    app, window = make_window(monkeypatch, tmp_path)

    QTest.mouseClick(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(24, 24))
    app.processEvents()
    snapshot = window.controller.get_snapshot()

    assert snapshot["motion"] == "TouchHead"
    assert snapshot["mood"] == 62
    assert "靠近" in snapshot["feedback"]

    window.close()
    app.processEvents()


def test_window_action_handler_does_not_wait_for_slow_llm_expression(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    class SlowExpressor:
        def __init__(self):
            self.calls = 0

        def express(self, snapshot, effect=None):
            self.calls += 1
            time.sleep(0.25)
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "late LLM speech",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    app = QApplication.instance() or QApplication([])
    slow_expressor = SlowExpressor()
    window = CompanionWindow(controller=make_controller(tmp_path, ai_expressor=slow_expressor))
    window.show()
    app.processEvents()
    slow_expressor.calls = 0

    started_at = time.monotonic()
    window._handle_action("touch")
    elapsed = time.monotonic() - started_at
    app.processEvents()

    snapshot = window.controller.get_snapshot()
    assert elapsed < 0.1
    assert slow_expressor.calls == 0
    assert snapshot["motion"] == "TouchHead"
    assert snapshot["mood"] == 62
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert snapshot["events"][0]["speech"] != "late LLM speech"

    window.close()
    app.processEvents()


def test_window_action_button_signal_does_not_wait_for_slow_llm_expression(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    class SlowExpressor:
        def __init__(self):
            self.calls = 0

        def express(self, snapshot, effect=None):
            self.calls += 1
            time.sleep(0.25)
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "late button LLM speech",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    app = QApplication.instance() or QApplication([])
    slow_expressor = SlowExpressor()
    window = CompanionWindow(controller=make_controller(tmp_path, ai_expressor=slow_expressor))
    window.show()
    app.processEvents()
    slow_expressor.calls = 0

    started_at = time.monotonic()
    window.action_buttons["touch"].click()
    elapsed = time.monotonic() - started_at
    app.processEvents()

    snapshot = window.controller.get_snapshot()
    assert elapsed < 0.1
    assert slow_expressor.calls == 0
    assert snapshot["motion"] == "TouchHead"
    assert snapshot["mood"] == 62
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert snapshot["events"][0]["speech"] != "late button LLM speech"

    window.close()
    app.processEvents()


def test_window_secondary_controls_do_not_wait_for_slow_llm_expression(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    class SlowExpressor:
        def __init__(self):
            self.calls = 0

        def express(self, snapshot, effect=None):
            self.calls += 1
            time.sleep(0.25)
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "late secondary LLM speech",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    app = QApplication.instance() or QApplication([])
    slow_expressor = SlowExpressor()
    controller = make_controller(tmp_path, ai_expressor=slow_expressor)
    controller.state.coins = 120
    window = CompanionWindow(controller=controller)
    window.show()
    app.processEvents()
    slow_expressor.calls = 0

    window.shop_list.setCurrentRow(0)
    started_at = time.monotonic()
    window._handle_buy()
    buy_elapsed = time.monotonic() - started_at
    app.processEvents()

    window.inventory_list.setCurrentRow(0)
    started_at = time.monotonic()
    window._handle_inventory_usage("feed")
    feed_elapsed = time.monotonic() - started_at
    app.processEvents()

    started_at = time.monotonic()
    window._handle_tick()
    tick_elapsed = time.monotonic() - started_at
    app.processEvents()

    started_at = time.monotonic()
    window._handle_demo_reset()
    reset_elapsed = time.monotonic() - started_at
    app.processEvents()

    started_at = time.monotonic()
    window._handle_demo_proactive("low_charge")
    proactive_elapsed = time.monotonic() - started_at
    app.processEvents()

    snapshot = window.controller.get_snapshot()
    assert max(buy_elapsed, feed_elapsed, tick_elapsed, reset_elapsed, proactive_elapsed) < 0.1
    assert slow_expressor.calls == 0
    assert snapshot["proactive_feedback"]["kind"] == "low_charge"
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]
    assert snapshot["events"][0]["speech"] != "late secondary LLM speech"

    window.close()
    app.processEvents()


def test_dragging_sprite_area_performs_raised_action(monkeypatch, tmp_path):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    app, window = make_window(monkeypatch, tmp_path)

    QTest.mousePress(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(24, 24))
    QTest.mouseMove(window.sprite_label, pos=QPoint(72, 72))
    QTest.mouseRelease(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(72, 72))
    app.processEvents()
    snapshot = window.controller.get_snapshot()

    assert snapshot["motion"] == "Raised"
    assert "提起" in snapshot["feedback"]

    window.close()
    app.processEvents()


def test_dragging_sprite_area_moves_desktop_pet_window(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.move(100, 100)
    window.show()
    app.processEvents()
    original_pos = window.pos()

    QTest.mousePress(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(24, 24))
    QTest.mouseMove(window.sprite_label, pos=QPoint(84, 54))
    QTest.mouseRelease(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(84, 54))
    app.processEvents()

    moved_pos = window.pos()
    snapshot = window.controller.get_snapshot()

    assert moved_pos.x() > original_pos.x()
    assert moved_pos.y() > original_pos.y()
    assert snapshot["motion"] == "Raised"

    window.close()
    app.processEvents()


def test_dragging_desktop_pet_window_stays_inside_available_screen(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.resize(120, 100)
    window.desktop_shell.available_geometry_provider = lambda: QRect(0, 0, 300, 260)
    window.move(150, 140)
    window.show()
    app.processEvents()

    QTest.mousePress(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(24, 24))
    QTest.mouseMove(window.sprite_label, pos=QPoint(320, 320))
    QTest.mouseRelease(window.sprite_label, Qt.MouseButton.LeftButton, pos=QPoint(320, 320))
    app.processEvents()

    moved_pos = window.pos()
    snapshot = window.controller.get_snapshot()

    assert moved_pos.x() <= 180
    assert moved_pos.y() <= 160
    assert moved_pos.x() >= 0
    assert moved_pos.y() >= 0
    assert snapshot["motion"] == "Raised"

    window.close()
    app.processEvents()


def test_desktop_pet_drag_release_docks_to_near_left_edge(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.desktop_shell.available_geometry_provider = lambda: QRect(0, 0, 1000, 800)
    window.show()
    app.processEvents()
    window.move(24, 140)
    app.processEvents()

    window._handle_action("drag")
    app.processEvents()
    snapshot = window.controller.get_snapshot()

    assert window.pos().x() == 0
    assert window.pos().y() == 140
    assert snapshot["motion"] == "Raised"

    window.close()
    app.processEvents()


def test_desktop_pet_drag_release_docks_to_near_right_edge(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path), desktop_mode=True)
    window.desktop_shell.available_geometry_provider = lambda: QRect(0, 0, 1000, 800)
    window.show()
    app.processEvents()
    docked_x = window.desktop_shell.clamp_position(QPoint(10_000, 140)).x()
    window.move(docked_x - 24, 140)
    app.processEvents()

    window._handle_action("drag")
    app.processEvents()
    snapshot = window.controller.get_snapshot()

    assert window.pos().x() == docked_x
    assert window.pos().y() == 140
    assert snapshot["motion"] == "Raised"

    window.close()
    app.processEvents()


def test_shop_and_inventory_lists_show_item_icons(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    shop_item = window.shop_list.item(0)

    assert shop_item is not None
    assert not shop_item.icon().isNull()

    window.shop_list.setCurrentRow(0)
    window._handle_buy()
    app.processEvents()
    inventory_item = window.inventory_list.item(0)

    assert inventory_item is not None
    assert not inventory_item.icon().isNull()

    window.close()
    app.processEvents()


def test_feeding_item_shows_temporary_icon_feedback(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window.shop_list.setCurrentRow(0)
    window._handle_buy()
    app.processEvents()
    window.inventory_list.setCurrentRow(0)
    window._handle_inventory_usage("feed")
    app.processEvents()

    assert window.item_feedback_label.isVisible()
    assert window.item_feedback_label.pixmap() is not None
    assert not window.item_feedback_label.pixmap().isNull()

    window.close()
    app.processEvents()


def test_window_shows_relationship_memory_log(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert "暂无回忆" in window.memory_label.text()

    window._handle_action("touch")
    app.processEvents()

    assert "轻触" in window.memory_label.text()
    assert "互动" in window.memory_label.text()

    window.close()
    app.processEvents()


def test_window_shows_relationship_stage_and_next_unlock(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    text = window.relationship_label.text()

    assert "当前关系：初识" in text
    assert "信任达到 20" in text
    assert "学习 KPI" not in text

    window.close()
    app.processEvents()


def test_window_shows_local_alias_relationship_presentation_and_badges(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window.player_alias_input.setText("小沈")
    window.player_alias_save_button.click()
    window.controller.state.trust = 20
    window.controller.state.unlocks = ["unlock_first_nickname"]
    window._apply_snapshot(window.controller.get_snapshot())
    app.processEvents()

    text = window.relationship_label.text()
    assert "小沈" in text
    assert "熟悉陪伴" in text
    assert "靠近一点" in text
    assert "星形发夹" in text
    assert window.controller.state.player_alias == "小沈"

    window.close()
    app.processEvents()


def test_llm_expression_reads_relationship_presentation_without_alias_write_surface(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.ai_expressor import ExpressionRequest
    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.expression_settings import normalize_expression_settings

    class CapturingExpressor:
        def __init__(self):
            self.requests = []

        def express(self, snapshot, effect=None):
            self.requests.append(snapshot)
            return []

    app = QApplication.instance() or QApplication([])
    expressor = CapturingExpressor()
    controller = make_controller(tmp_path, ai_expressor=expressor)
    controller.set_player_alias("小沈")
    controller.state.trust = 20
    controller.state.unlocks = ["unlock_first_nickname"]
    controller.update_expression_settings(
        normalize_expression_settings(
            {
                "enabled": True,
                "provider": "custom",
                "model": "local-model",
                "base_url": "http://127.0.0.1:1234/v1",
                "api_key": "",
            }
        )
    )
    controller.ai_expressor = expressor
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()

    window.dialogue_input.setText("今天陪我一会儿")
    window.dialogue_send_button.click()
    app.processEvents()

    request = expressor.requests[-1]
    relationship_context = [
        entry for entry in request.tool_results if entry["source"] == "local_relationship_presentation"
    ]
    assert isinstance(request, ExpressionRequest)
    assert relationship_context
    assert "小沈" in relationship_context[0]["summary"]
    assert "熟悉陪伴" in relationship_context[0]["summary"]
    assert "靠近一点" in relationship_context[0]["summary"]
    assert not hasattr(request, "player_alias")
    assert not hasattr(request, "unlocks")

    window.close()
    app.processEvents()


def test_llm_expression_cannot_write_player_alias_or_relationship_unlocks(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.expression_settings import normalize_expression_settings

    class OverreachingExpressor:
        def express(self, snapshot, effect=None):
            return [
                {
                    "type": "speech",
                    "speech": "我来改称呼。",
                    "effect": "ATTENTION",
                    "player_alias": "被 LLM 改写",
                    "unlocks": ["unlock_shared_ritual"],
                }
            ]

    app = QApplication.instance() or QApplication([])
    controller = make_controller(tmp_path, ai_expressor=OverreachingExpressor())
    controller.set_player_alias("小沈")
    controller.update_expression_settings(
        normalize_expression_settings(
            {
                "enabled": True,
                "provider": "custom",
                "model": "local-model",
                "base_url": "http://127.0.0.1:1234/v1",
                "api_key": "",
            }
        )
    )
    controller.ai_expressor = OverreachingExpressor()
    window = CompanionWindow(controller=controller, desktop_mode=True)
    window.show()
    app.processEvents()
    before_unlocks = list(window.controller.state.unlocks)

    window.dialogue_input.setText("今天陪我一会儿")
    window.dialogue_send_button.click()
    app.processEvents()

    assert window.controller.state.player_alias == "小沈"
    assert window.controller.state.unlocks == before_unlocks
    assert "我来改称呼" not in window.desktop_feedback_label.text()

    window.close()
    app.processEvents()


def test_window_shows_screen_perception_disabled_by_default(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window.navigation_buttons[5].click()
    app.processEvents()

    assert window.perception_card.isVisibleTo(window)
    assert window.observe_screen_button.isEnabled()
    assert "屏幕感知：关闭" in window.perception_status_label.text()
    assert "默认不会读取屏幕" in window.perception_privacy_label.text()
    assert "不会自动截图" in window.perception_privacy_label.text()

    window.close()
    app.processEvents()


def test_capability_pages_have_safe_defaults(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    nav_labels = [button.text() for button in window.navigation_buttons]

    assert "感知与搜索" in nav_labels
    assert "语音" in nav_labels
    assert window.screen_observation_enabled_check.isChecked() is False
    assert window.screen_observation_auto_check.isChecked() is False
    assert window.web_search_enabled_check.isChecked() is False
    assert window.tts_enabled_check.isChecked() is False
    assert window.asr_enabled_check.isChecked() is False
    assert window.proactive_companion_enabled_check.isChecked() is False
    assert window.proactive_interval_input.value() == 900
    assert window.proactive_global_cooldown_input.value() == 1800
    assert window.proactive_daily_limit_input.value() == 8
    assert window.proactive_quiet_hours_check.isChecked() is False
    assert window.proactive_allow_context_topic_check.isChecked() is True
    assert "不会自动点击" in window.perception_privacy_label.text()

    window.close()
    app.processEvents()


def test_capability_ui_save_round_trips_to_controller(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)
    before = window.controller.get_typed_snapshot()

    window.screen_observation_enabled_check.setChecked(True)
    window.web_search_enabled_check.setChecked(True)
    window.tts_enabled_check.setChecked(True)
    window.asr_enabled_check.setChecked(True)
    window.proactive_companion_enabled_check.setChecked(True)
    window.proactive_interval_input.setValue(1200)
    window.proactive_global_cooldown_input.setValue(2400)
    window.proactive_daily_limit_input.setValue(6)
    window.proactive_quiet_hours_check.setChecked(True)
    window.proactive_quiet_start_input.setText("22:30")
    window.proactive_quiet_end_input.setText("07:30")
    window.proactive_allow_context_topic_check.setChecked(False)
    window.capability_save_button.click()
    app.processEvents()

    settings = window.controller.get_capability_settings()
    after = window.controller.get_typed_snapshot()
    assert settings.screen_observation.enabled is True
    assert settings.web_search.enabled is True
    assert settings.tts.enabled is True
    assert settings.asr.enabled is True
    assert settings.proactive_companion.enabled is True
    assert settings.proactive_companion.interval_seconds == 1200
    assert settings.proactive_companion.global_cooldown_seconds == 2400
    assert settings.proactive_companion.daily_limit == 6
    assert settings.proactive_companion.quiet_hours_enabled is True
    assert settings.proactive_companion.quiet_start == "22:30"
    assert settings.proactive_companion.quiet_end == "07:30"
    assert settings.proactive_companion.allow_context_topic is False
    assert "已保存" in window.capability_feedback_label.text()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_screen_observation_button_updates_readonly_context_without_growth_mutation(monkeypatch, tmp_path):
    from guanghe_companion.screen_observation import ScreenObservationResult

    app, window = make_window(monkeypatch, tmp_path)
    before = window.controller.get_typed_snapshot()

    class FakeObservationService:
        def __init__(self):
            self.settings = []

        def observe(self, settings):
            self.settings.append(settings)
            return ScreenObservationResult(True, "屏幕观察完成", "看到 IDE 和测试结果")

    fake_service = FakeObservationService()
    window.screen_observation_service = fake_service
    window.screen_observation_enabled_check.setChecked(True)
    window.screen_observation_model_input.setText("vision-test")
    window.screen_observation_base_url_input.setText("https://vision.example.test/v1")
    window.screen_observation_api_key_input.setText("secret")

    window.screen_observation_run_button.click()
    app.processEvents()

    context = window.controller._expression_context()
    after = window.controller.get_typed_snapshot()
    assert fake_service.settings[0].enabled is True
    assert context["perception_summary"] == "看到 IDE 和测试结果"
    assert "屏幕观察完成" in window.screen_observation_status_label.text()
    assert "看到 IDE 和测试结果" in window.screen_observation_status_label.text()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_screen_observation_auto_timer_tracks_saved_settings(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window.screen_observation_enabled_check.setChecked(True)
    window.screen_observation_auto_check.setChecked(True)
    window.screen_observation_interval_input.setValue(10)
    window.capability_save_button.click()
    app.processEvents()

    assert window.screen_observation_timer.isActive()
    assert window.screen_observation_timer.interval() == 10_000

    window.screen_observation_auto_check.setChecked(False)
    window.capability_save_button.click()
    app.processEvents()

    assert not window.screen_observation_timer.isActive()

    window.close()
    app.processEvents()


def test_web_search_button_updates_tool_results_without_growth_mutation(monkeypatch, tmp_path):
    from guanghe_companion.web_search import WebSearchResult

    app, window = make_window(monkeypatch, tmp_path)
    before = window.controller.get_typed_snapshot()

    class FakeSearchService:
        def __init__(self):
            self.calls = []

        def search(self, query, settings):
            self.calls.append((query, settings))
            return WebSearchResult(
                ok=True,
                message="搜索完成",
                tool_results=[{"source": "web_search", "title": query, "summary": "摘要"}],
            )

    fake_service = FakeSearchService()
    window.web_search_service = fake_service
    window.web_search_enabled_check.setChecked(True)
    window.web_search_query_input.setText("星汐")

    window.web_search_run_button.click()
    app.processEvents()

    context = window.controller._expression_context()
    after = window.controller.get_typed_snapshot()
    assert fake_service.calls[0][0] == "星汐"
    assert fake_service.calls[0][1].enabled is True
    assert context["tool_results"][0]["title"] == "星汐"
    assert "搜索完成" in window.web_search_results_label.text()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_search_shortcut_updates_tool_results_without_dialogue_submit(monkeypatch, tmp_path):
    from guanghe_companion.web_search import WebSearchResult

    app, window = make_window(monkeypatch, tmp_path)
    before_history = window.controller.dialogue_history

    class FakeSearchService:
        def search(self, query, settings):
            return WebSearchResult(
                ok=True,
                message="搜索完成",
                tool_results=[{"source": "web_search", "title": query, "summary": "摘要"}],
            )

    window.web_search_service = FakeSearchService()
    window.web_search_enabled_check.setChecked(True)
    window.capability_save_button.click()
    window.dialogue_input.setText("/search 星汐")

    window._handle_dialogue_submit()
    app.processEvents()

    assert window.dialogue_input.text() == ""
    assert window.controller.dialogue_history == before_history
    assert window.controller._expression_context()["tool_results"][0]["title"] == "星汐"
    assert "搜索完成" in window.web_search_results_label.text()

    window.close()
    app.processEvents()


def test_expression_settings_page_shows_required_fields_and_saves_local_config(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication, QLineEdit

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    window.show()
    app.processEvents()

    window.navigation_buttons[6].click()
    app.processEvents()

    assert window.expression_settings_card.isVisibleTo(window)
    assert window.expression_settings_card.title() == "LLM 表达接入"
    assert window.expression_enabled_checkbox.text() == "启用 LLM 表达增强"
    assert window.expression_provider_label.text() == "服务商"
    assert window.expression_model_label.text() == "模型 ID"
    assert window.expression_base_url_label.text() == "Base URL"
    assert window.expression_api_key_label.text() == "API Key"
    assert window.expression_timeout_label.text() == "超时（秒）"
    assert window.expression_provider_combo.currentText() == "openai"
    assert window.expression_model_input.text()
    assert window.expression_model_input.placeholderText() == "例如 gpt-5.5"
    assert window.expression_base_url_input.text().startswith("https://")
    assert window.expression_base_url_input.placeholderText() == "OpenAI-compatible Base URL 或完整 endpoint"
    assert window.expression_api_key_input.echoMode() == QLineEdit.EchoMode.Password
    assert window.expression_api_key_input.placeholderText() == "粘贴 API Key"
    assert window.expression_timeout_input.value() == 2.0
    assert window.expression_timeout_input.maximum() == 60.0
    assert window.expression_test_button.text() == "测试 LLM 回应"
    assert window.expression_settings_status_label.text() == "LLM 表达：关闭"

    window.expression_enabled_checkbox.setChecked(True)
    window.expression_model_input.setText("demo-model")
    window.expression_base_url_input.setText("https://example.test/v1/responses")
    window.expression_api_key_input.setText("test-key")
    window.expression_timeout_input.setValue(0.5)
    window.expression_save_button.click()
    app.processEvents()

    settings = window.controller.get_expression_settings()
    assert settings["enabled"] is True
    assert settings["provider"] == "openai"
    assert settings["model"] == "demo-model"
    assert settings["base_url"] == "https://example.test/v1/responses"
    assert settings["api_key_set"] is True
    assert settings["timeout_seconds"] == 0.5
    assert window.expression_settings_status_label.text() == "LLM 表达设置已保存"

    window.close()
    app.processEvents()


def test_expression_settings_test_button_saves_and_tests_llm_without_mutating_state(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    import guanghe_companion.controller as controller_module
    from guanghe_companion.app import CompanionWindow

    class FakeExpressor:
        def __init__(self):
            self.last_fallback_reason = None
            self.requests = []

        def close(self):
            pass

        def express(self, snapshot, effect=None):
            self.requests.append((snapshot, effect))
            return [
                {
                    "character_name": snapshot.character_name,
                    "speech": "LLM 连接成功",
                    "sprite": "1",
                    "effect": "ATTENTION",
                }
            ]

    created = []

    def fake_build_default_ai_expressor(*, settings=None):
        fake = FakeExpressor()
        created.append((settings, fake))
        return fake

    monkeypatch.setattr(controller_module, "build_default_ai_expressor", fake_build_default_ai_expressor)

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    window.show()
    app.processEvents()

    window.navigation_buttons[6].click()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    window.expression_enabled_checkbox.setChecked(True)
    window.expression_model_input.setText("demo-model")
    window.expression_base_url_input.setText("https://example.test/v1/responses")
    window.expression_api_key_input.setText("test-key")
    window.expression_timeout_input.setValue(0.5)
    window.expression_test_button.click()
    app.processEvents()

    after = window.controller.get_typed_snapshot()
    settings, fake = created[-1]
    assert settings.enabled is True
    assert settings.model == "demo-model"
    assert settings.base_url == "https://example.test/v1/responses"
    assert settings.api_key == "test-key"
    assert fake.requests
    assert "LLM 测试通过" in window.expression_settings_status_label.text()
    assert "LLM 连接成功" in window.expression_settings_status_label.text()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.unlocks == before.unlocks
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_expression_settings_test_button_shows_diagnostic_stage_and_reason(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    window.show()
    app.processEvents()

    window.navigation_buttons[6].click()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    def fake_test_expression_provider():
        return {
            "ok": False,
            "stage": "provider_call",
            "reason": "timeout",
            "fallback_reason": "timeout",
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "timeout_seconds": 0.5,
            "speech": "",
            "effect": "",
        }

    window.controller.test_expression_provider = fake_test_expression_provider
    window.expression_provider_combo.setCurrentText("deepseek")
    window.expression_enabled_checkbox.setChecked(True)
    window.expression_api_key_input.setText("test-key")
    window.expression_timeout_input.setValue(0.5)
    window.expression_test_button.click()
    app.processEvents()

    after = window.controller.get_typed_snapshot()
    status = window.expression_settings_status_label.text()
    assert "LLM 测试失败" in status
    assert "调用服务" in status
    assert "请求超时" in status
    assert "deepseek-v4-flash" in status
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_expression_settings_test_button_shows_auth_action_without_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    window.show()
    app.processEvents()

    window.navigation_buttons[6].click()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    def fake_test_expression_provider():
        return {
            "ok": False,
            "stage": "provider_call",
            "reason": "http_401",
            "fallback_reason": "http_401",
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "timeout_seconds": 0.5,
            "speech": "",
            "effect": "",
        }

    window.controller.test_expression_provider = fake_test_expression_provider
    window.expression_provider_combo.setCurrentText("deepseek")
    window.expression_enabled_checkbox.setChecked(True)
    window.expression_api_key_input.setText("sk-secret")
    window.expression_test_button.click()
    app.processEvents()

    after = window.controller.get_typed_snapshot()
    status = window.expression_settings_status_label.text()
    assert "Provider 认证失败" in status
    assert "Action: replace API key" in status
    assert "Ollama" in status
    assert "LM Studio" in status
    assert "sk-secret" not in status
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_expression_settings_fetches_provider_model_list_without_saving_or_mutating_state(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    captured = {}
    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))

    def fake_fetch_expression_models(settings):
        captured.update(settings)
        return ("deepseek-v4-flash", "deepseek-v4-pro")

    window.controller.fetch_expression_models = fake_fetch_expression_models
    window.show()
    app.processEvents()

    window.navigation_buttons[6].click()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    provider_items = [window.expression_provider_combo.itemText(index) for index in range(window.expression_provider_combo.count())]
    assert provider_items == ["openai", "deepseek", "openrouter", "ollama", "lmstudio", "custom"]
    assert not window.expression_model_list_combo.isVisibleTo(window)

    window.expression_provider_combo.setCurrentText("deepseek")
    app.processEvents()

    assert window.expression_model_input.text() == "deepseek-v4-flash"
    assert window.expression_base_url_input.text() == "https://api.deepseek.com"

    window.expression_api_key_input.setText("test-key")
    window.expression_model_fetch_button.click()
    app.processEvents()

    after = window.controller.get_typed_snapshot()
    assert captured["provider"] == "deepseek"
    assert captured["base_url"] == "https://api.deepseek.com"
    assert captured["api_key"] == "test-key"
    assert window.expression_model_list_combo.isVisibleTo(window)
    assert window.expression_model_list_combo.count() == 2
    assert window.expression_model_list_combo.itemText(1) == "deepseek-v4-pro"
    assert window.expression_model_input.text() == "deepseek-v4-flash"

    window.expression_model_list_combo.setCurrentIndex(1)
    app.processEvents()

    assert window.expression_model_input.text() == "deepseek-v4-pro"
    assert "获取到 2 个模型" in window.expression_settings_status_label.text()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_expression_rule_preview_page_is_readonly_and_copyable(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    window.show()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    window.navigation_buttons[7].click()
    app.processEvents()

    preview = window.expression_rule_preview_text.toPlainText()
    assert window.expression_rule_card.isVisibleTo(window)
    assert window.expression_rule_preview_text.isReadOnly()
    assert "AI 只能生成表达事件" in preview
    assert "不能修改状态数值" in preview
    assert "背包" in preview
    assert "星汐" in preview

    window.expression_rule_copy_button.click()
    app.processEvents()

    assert QApplication.clipboard().text() == preview
    assert "已复制" in window.expression_rule_status_label.text()
    assert window.controller.get_typed_snapshot().stats == before.stats
    assert window.controller.get_typed_snapshot().inventory == before.inventory
    assert window.controller.get_typed_snapshot().memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_voice_settings_page_marks_tts_and_asr_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    window.show()
    app.processEvents()
    before = window.controller.get_typed_snapshot()

    window.navigation_buttons[8].click()
    app.processEvents()

    assert window.voice_settings_card.isVisibleTo(window)
    assert "TTS 暂未启用" in window.voice_status_label.text()
    assert "ASR 暂未启用" in window.voice_status_label.text()
    assert window.voice_tts_provider_label.text() == "tts_provider: disabled"
    assert window.voice_asr_provider_label.text() == "asr_provider: disabled"
    assert window.tts_model_variant_combo.currentText() == "qwen3tts_0.6b_customvoice"
    assert not window.voice_tts_enable_button.isEnabled()
    assert not window.voice_asr_enable_button.isEnabled()
    assert window.controller.get_typed_snapshot().stats == before.stats
    assert window.controller.get_typed_snapshot().inventory == before.inventory
    assert window.controller.get_typed_snapshot().memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_auto_tts_consumes_snapshot_speech_after_validation(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    class CapturingExpressor:
        def express(self, snapshot, effect=None):
            return [
                {
                    "character_name": "星汐",
                    "speech": "LLM 连接成功",
                    "sprite": "1",
                    "effect": "ATTENTION",
                },
                {
                    "character_name": "STAT",
                    "speech": "专注 50 / 能量 50",
                    "sprite": "-1",
                    "effect": "",
                },
            ]

    class FakeTTSManager:
        def __init__(self):
            self.calls = []

        def speak(self, text, settings):
            from guanghe_companion.voice_tts import TTSResult

            self.calls.append((text, settings))
            return TTSResult(True, "朗读完成")

        def stop(self, settings=None):
            from guanghe_companion.voice_tts import TTSResult

            return TTSResult(True, "已停止朗读")

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path, ai_expressor=CapturingExpressor()))
    fake_tts = FakeTTSManager()
    window.tts_manager = fake_tts
    window.tts_enabled_check.setChecked(True)
    window.tts_auto_speak_check.setChecked(True)
    window.tts_model_variant_combo.setCurrentText("qwen3tts_1.7b_customvoice")
    window.capability_save_button.click()

    snapshot = window.controller.perform_action("touch", include_ai_expression=True)
    before_tts = window.controller.get_typed_snapshot()
    window._apply_snapshot(snapshot)
    app.processEvents()
    after = window.controller.get_typed_snapshot()

    assert len(fake_tts.calls) == 1
    assert fake_tts.calls[0][0] == "LLM 连接成功"
    assert fake_tts.calls[0][1].profile_id == "xingxi_pixel_pet_qwen_vivian_v1"
    assert fake_tts.calls[0][1].model_variant == "qwen3tts_0.6b_customvoice"
    assert fake_tts.calls[0][1].voice == "Vivian"
    assert fake_tts.calls[0][1].rate == 1
    assert fake_tts.calls[0][1].volume == 0.92
    assert "Xingxi" in fake_tts.calls[0][1].instruct
    assert "STAT" not in fake_tts.calls[0][0]
    assert "web_search" not in fake_tts.calls[0][0]
    assert after.stats == before_tts.stats
    assert after.inventory == before_tts.inventory
    assert after.memory_log == before_tts.memory_log

    window.close()
    app.processEvents()


def test_character_tts_profile_is_applied_to_voice_test(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    write_ui_character_pack(
        assets_root,
        "xingxi_pixel_pet",
        name="Xingxi",
        title="Desktop companion",
        tts_profile={
            "profile_id": "xingxi_qwen_vivian_v1",
            "provider": "http-qwen3tts",
            "api_url": "http://127.0.0.1:9880/",
            "language": "zh",
            "voice": "Vivian",
            "model_variant": "0.6B",
            "rate": 2,
            "volume": 0.8,
            "instruct": "gentle companion tone",
            "voice_source_type": "original_design",
            "training_status": "designed",
            "distribution_policy": "public_ok",
        },
    )
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    class FakeTTSManager:
        def __init__(self):
            self.calls = []

        def speak(self, text, settings):
            from guanghe_companion.voice_tts import TTSResult

            self.calls.append((text, settings))
            return TTSResult(True, "started")

        def stop(self, settings=None):
            from guanghe_companion.voice_tts import TTSResult

            return TTSResult(True, "stopped")

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="xingxi_pixel_pet",
        save_path=tmp_path / "save.json",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller)
    fake_tts = FakeTTSManager()
    window.tts_manager = fake_tts
    window.tts_enabled_check.setChecked(True)

    window._handle_tts_test()

    assert fake_tts.calls
    assert fake_tts.calls[0][1].profile_id == "xingxi_qwen_vivian_v1"
    assert fake_tts.calls[0][1].provider == "http_qwen3tts"
    assert fake_tts.calls[0][1].voice == "Vivian"
    assert fake_tts.calls[0][1].model_variant == "qwen3tts_0.6b_customvoice"
    assert fake_tts.calls[0][1].rate == 2
    assert fake_tts.calls[0][1].volume == 0.8
    assert fake_tts.calls[0][1].instruct == "gentle companion tone"

    window.close()
    app.processEvents()


def test_character_switch_updates_voice_profile_summary(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assets_root = tmp_path / "assets"
    write_ui_character_pack(
        assets_root,
        "xingxi_pixel_pet",
        name="Xingxi",
        title="Desktop companion",
        tts_profile={
            "profile_id": "xingxi_voice_v1",
            "display_name": "Xingxi designed voice",
            "provider": "http_qwen3tts",
            "voice": "Vivian",
            "model_variant": "0.6B",
            "voice_source_type": "original_design",
            "training_status": "designed",
            "distribution_policy": "public_ok",
        },
    )
    write_ui_character_pack(
        assets_root,
        "custom_character",
        name="Custom",
        title="Voice companion",
        tts_profile={
            "profile_id": "custom_voice_v1",
            "display_name": "Custom role voice",
            "provider": "http_qwen3tts",
            "voice": "Dylan",
            "model_variant": "0.6B",
            "voice_source_type": "local_generated",
            "training_status": "candidate",
            "distribution_policy": "public_ok",
        },
    )
    patch_ui_character_assets(monkeypatch, assets_root)

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    app = QApplication.instance() or QApplication([])
    controller = CompanionController(
        character_id="xingxi_pixel_pet",
        save_path=tmp_path / "save.json",
        auto_load=False,
    )
    window = CompanionWindow(controller=controller)
    app.processEvents()

    assert "Xingxi designed voice" in window.voice_character_profile_label.text()
    assert "Vivian" in window.voice_character_profile_label.text()

    for index in range(window.character_list.count()):
        item = window.character_list.item(index)
        if item.data(Qt.ItemDataRole.UserRole) == "custom_character":
            window.character_list.setCurrentItem(item)
            break
    window.character_switch_button.click()
    app.processEvents()

    assert window.controller.state.character_id == "custom_character"
    assert "Custom role voice" in window.voice_character_profile_label.text()
    assert "Dylan" in window.voice_character_profile_label.text()

    window.close()
    app.processEvents()


def test_asr_stop_button_fills_dialogue_input(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    class FakeASRService:
        def __init__(self):
            self.started = []
            self.stopped = []

        def start_recording(self, settings):
            from guanghe_companion.voice_asr import ASRResult

            self.started.append(settings)
            return ASRResult(True, "录音中")

        def stop_and_transcribe(self, settings):
            from guanghe_companion.voice_asr import ASRResult

            self.stopped.append(settings)
            return ASRResult(True, "识别完成", "你好星汐")

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    fake_asr = FakeASRService()
    window.asr_service = fake_asr
    window.asr_enabled_check.setChecked(True)
    window.capability_save_button.click()

    window.asr_start_button.click()
    window.asr_stop_button.click()
    app.processEvents()

    assert fake_asr.started[0].enabled is True
    assert fake_asr.stopped[0].enabled is True
    assert window.dialogue_input.text() == "你好星汐"
    assert "识别完成" in window.voice_status_label.text()
    assert window.controller.dialogue_history == ()

    window.close()
    app.processEvents()


def test_asr_auto_send_uses_dialogue_request_without_growth_mutation(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    class FakeASRService:
        def start_recording(self, settings):
            from guanghe_companion.voice_asr import ASRResult

            return ASRResult(True, "录音中")

        def stop_and_transcribe(self, settings):
            from guanghe_companion.voice_asr import ASRResult

            return ASRResult(True, "识别完成", "你好星汐")

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    window.asr_service = FakeASRService()
    window.asr_enabled_check.setChecked(True)
    window.asr_auto_send_check.setChecked(True)
    window.capability_save_button.click()
    before = window.controller.get_typed_snapshot()

    window.asr_start_button.click()
    window.asr_stop_button.click()
    app.processEvents()
    after = window.controller.get_typed_snapshot()
    user_entries = [entry for entry in window.controller.dialogue_history if entry.role == "user"]

    assert window.dialogue_input.text() == ""
    assert user_entries[-1].source == "asr"
    assert user_entries[-1].text == "你好星汐"
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_asr_hotkey_toggles_recording_and_uses_dialogue_request(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtGui import QKeySequence
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow

    class FakeASRService:
        def __init__(self):
            self.started = []
            self.stopped = []

        def start_recording(self, settings):
            from guanghe_companion.voice_asr import ASRResult

            self.started.append(settings)
            return ASRResult(True, "录音中")

        def stop_and_transcribe(self, settings):
            from guanghe_companion.voice_asr import ASRResult

            self.stopped.append(settings)
            return ASRResult(True, "识别完成", "快捷键和星汐说话")

    app = QApplication.instance() or QApplication([])
    window = CompanionWindow(controller=make_controller(tmp_path))
    fake_asr = FakeASRService()
    window.asr_service = fake_asr
    window.asr_enabled_check.setChecked(True)
    window.asr_auto_send_check.setChecked(True)
    window.asr_hotkey_enabled_check.setChecked(True)
    window.asr_hotkey_input.setText("Ctrl+Alt+Space")
    window.capability_save_button.click()
    before = window.controller.get_typed_snapshot()

    assert window.asr_hotkey_shortcut.isEnabled() is True
    assert (
        window.asr_hotkey_shortcut.key().toString(QKeySequence.SequenceFormat.PortableText)
        == "Ctrl+Alt+Space"
    )

    window.asr_hotkey_shortcut.activated.emit()
    window.asr_hotkey_shortcut.activated.emit()
    app.processEvents()
    after = window.controller.get_typed_snapshot()
    user_entries = [entry for entry in window.controller.dialogue_history if entry.role == "user"]

    assert [settings.hotkey_sequence for settings in fake_asr.started] == ["Ctrl+Alt+Space"]
    assert [settings.hotkey_sequence for settings in fake_asr.stopped] == ["Ctrl+Alt+Space"]
    assert user_entries[-1].source == "asr"
    assert user_entries[-1].text == "快捷键和星汐说话"
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.memory_log == before.memory_log

    window.close()
    app.processEvents()


def test_window_manual_screen_perception_trigger_shows_privacy_prompt_and_status(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    captured = {}

    def fake_information(parent, title, message):
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(QMessageBox, "information", fake_information)
    app, window = make_window(monkeypatch, tmp_path)

    window.observe_screen_button.click()
    app.processEvents()

    assert captured["title"] == "屏幕感知隐私提示"
    assert "只在手动触发时运行" in captured["message"]
    assert "本轮不会自动截图" in captured["message"]
    assert "屏幕感知：已手动触发" in window.perception_status_label.text()
    assert "未读取屏幕内容" in window.perception_status_label.text()

    window.close()
    app.processEvents()


def test_window_manual_screen_perception_updates_readonly_expression_context(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, message: None)
    app, window = make_window(monkeypatch, tmp_path)

    before_context = window.controller.expression_context_provider()
    window.observe_screen_button.click()
    app.processEvents()
    after_context = window.controller.expression_context_provider()

    assert "perception_summary" not in before_context
    assert after_context["perception_summary"] == "manual screen perception requested; no screen content was read"
    assert "tool_results" in after_context
    assert "screenshot" not in after_context["perception_summary"]
    assert "ocr" not in after_context["perception_summary"].lower()

    window.close()
    app.processEvents()


def test_window_close_clears_manual_screen_perception_context(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, message: None)
    app, window = make_window(monkeypatch, tmp_path)

    window.observe_screen_button.click()
    app.processEvents()
    assert window.controller.expression_context_provider()["perception_summary"]

    controller = window.controller
    window.close()
    app.processEvents()

    context_after_close = controller.expression_context_provider()
    assert "perception_summary" not in context_after_close


def test_window_manual_screen_perception_reaches_typed_expression_request(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication, QMessageBox

    from guanghe_companion.ai_expressor import ExpressionRequest
    from guanghe_companion.app import (
        MANUAL_PERCEPTION_NO_SCREEN_SUMMARY,
        CompanionWindow,
    )

    class CapturingExpressor:
        def __init__(self):
            self.requests = []

        def express(self, snapshot, effect=None):
            self.requests.append(snapshot)
            return []

    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, message: None)
    app = QApplication.instance() or QApplication([])
    expressor = CapturingExpressor()
    window = CompanionWindow(controller=make_controller(tmp_path, ai_expressor=expressor))
    window.show()
    app.processEvents()

    window.observe_screen_button.click()
    app.processEvents()
    snapshot = window.controller.perform_action("touch", include_ai_expression=True)

    request = expressor.requests[-1]
    assert isinstance(request, ExpressionRequest)
    assert request.perception_summary == MANUAL_PERCEPTION_NO_SCREEN_SUMMARY
    assert "no screen content was read" in request.perception_summary
    assert "window title:" not in request.perception_summary.lower()
    assert "screenshot" not in request.perception_summary.lower()
    assert "ocr" not in request.perception_summary.lower()
    assert snapshot["mood"] == 62
    assert snapshot["events"][0]["speech"] == snapshot["feedback"]

    window.close()
    app.processEvents()


def test_window_shows_proactive_companionship_feedback(monkeypatch, tmp_path):
    from guanghe_companion.capability_settings import CapabilitySettings, ProactiveCompanionSettings

    app, window = make_window(monkeypatch, tmp_path)
    window.controller.update_capability_settings(
        CapabilitySettings(proactive_companion=ProactiveCompanionSettings(enabled=True))
    )
    window.controller.state.charge = 25
    window.controller.state.mood = 60
    window.controller.state.focus = 70
    window.controller.state.stability = 70

    window._handle_tick()
    app.processEvents()

    assert "能量有点低" in window.feedback_label.text()
    assert "主动陪伴" in window.memory_label.text()

    window.close()
    app.processEvents()


def test_window_close_closes_controller(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    class CloseAwareController(CompanionController):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.close_calls = 0

        def close(self):
            if self.close_calls:
                return
            self.close_calls += 1
            super().close()

    app = QApplication.instance() or QApplication([])
    controller = CloseAwareController(save_path=tmp_path / "save.json", auto_load=False)
    window = CompanionWindow(controller=controller)
    window.show()
    app.processEvents()

    window.close()
    app.processEvents()

    assert controller.close_calls == 1


def test_window_close_stops_runtime_timers(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert window.frame_timer.isActive()
    assert window.countdown_timer.isActive()

    window.close()
    app.processEvents()

    assert not window.frame_timer.isActive()
    assert not window.tick_timer.isActive()
    assert not window.countdown_timer.isActive()
    assert not window.screen_observation_timer.isActive()


def test_control_panel_close_hides_to_tray_without_closing_controller(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    import guanghe_companion.app as app_module
    from guanghe_companion.controller import CompanionController

    class CloseAwareController(CompanionController):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.close_calls = 0

        def close(self):
            self.close_calls += 1
            super().close()

    FakeSystemTrayIcon.instances = []
    FakeSystemTrayIcon.available = True
    monkeypatch.setattr(app_module, "QSystemTrayIcon", FakeSystemTrayIcon, raising=False)
    app = QApplication.instance() or QApplication([])
    controller = CloseAwareController(save_path=tmp_path / "save.json", auto_load=False)
    window = app_module.CompanionWindow(controller=controller)
    window.show()
    app.processEvents()

    window.close()
    app.processEvents()

    assert not window.isVisible()
    assert controller.close_calls == 0
    assert FakeSystemTrayIcon.instances[-1].visible is True
    assert FakeSystemTrayIcon.instances[-1].messages

    labels_to_actions = {
        action.text(): action
        for action in FakeSystemTrayIcon.instances[-1].context_menu.actions()
        if not action.isSeparator()
    }
    labels_to_actions["退出"].trigger()
    app.processEvents()

    assert controller.close_calls == 1
    assert FakeSystemTrayIcon.instances[-1].visible is False


def test_control_panel_minimize_hides_to_tray_without_closing_controller(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    import guanghe_companion.app as app_module
    from guanghe_companion.controller import CompanionController

    class CloseAwareController(CompanionController):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.close_calls = 0

        def close(self):
            self.close_calls += 1
            super().close()

    FakeSystemTrayIcon.instances = []
    FakeSystemTrayIcon.available = True
    monkeypatch.setattr(app_module, "QSystemTrayIcon", FakeSystemTrayIcon, raising=False)
    app = QApplication.instance() or QApplication([])
    controller = CloseAwareController(save_path=tmp_path / "save.json", auto_load=False)
    window = app_module.CompanionWindow(controller=controller)
    window.show()
    app.processEvents()

    window.showMinimized()
    app.processEvents()
    app.processEvents()

    assert not window.isVisible()
    assert controller.close_calls == 0
    assert FakeSystemTrayIcon.instances[-1].visible is True

    labels_to_actions = {
        action.text(): action
        for action in FakeSystemTrayIcon.instances[-1].context_menu.actions()
        if not action.isSeparator()
    }
    labels_to_actions["退出"].trigger()
    app.processEvents()


def test_desktop_pet_child_window_does_not_create_tray_icon(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    import guanghe_companion.app as app_module

    FakeSystemTrayIcon.instances = []
    FakeSystemTrayIcon.available = True
    monkeypatch.setattr(app_module, "QSystemTrayIcon", FakeSystemTrayIcon, raising=False)
    app = QApplication.instance() or QApplication([])
    window = app_module.CompanionWindow(
        controller=make_controller(tmp_path),
        desktop_mode=True,
        owns_controller=False,
    )
    window.show()
    app.processEvents()

    assert FakeSystemTrayIcon.instances == []

    window.close()
    app.processEvents()


def test_tray_show_control_panel_restores_hidden_window(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    import guanghe_companion.app as app_module

    FakeSystemTrayIcon.instances = []
    FakeSystemTrayIcon.available = True
    monkeypatch.setattr(app_module, "QSystemTrayIcon", FakeSystemTrayIcon, raising=False)
    app = QApplication.instance() or QApplication([])
    window = app_module.CompanionWindow(controller=make_controller(tmp_path))
    window.show()
    app.processEvents()

    window.close()
    app.processEvents()
    assert not window.isVisible()

    labels_to_actions = {
        action.text(): action
        for action in FakeSystemTrayIcon.instances[-1].context_menu.actions()
        if not action.isSeparator()
    }
    labels_to_actions["显示控制面板"].trigger()
    app.processEvents()

    assert window.isVisible()

    labels_to_actions["退出"].trigger()
    app.processEvents()


def test_window_close_falls_back_when_system_tray_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    import guanghe_companion.app as app_module
    from guanghe_companion.controller import CompanionController

    class CloseAwareController(CompanionController):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.close_calls = 0

        def close(self):
            self.close_calls += 1
            super().close()

    FakeSystemTrayIcon.instances = []
    FakeSystemTrayIcon.available = False
    monkeypatch.setattr(app_module, "QSystemTrayIcon", FakeSystemTrayIcon, raising=False)
    app = QApplication.instance() or QApplication([])
    controller = CloseAwareController(save_path=tmp_path / "save.json", auto_load=False)
    window = app_module.CompanionWindow(controller=controller)
    window.show()
    app.processEvents()

    window.close()
    app.processEvents()

    assert not window.isVisible()
    assert controller.close_calls == 1
    assert FakeSystemTrayIcon.instances == []


def test_window_close_ignores_controller_close_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication

    from guanghe_companion.app import CompanionWindow
    from guanghe_companion.controller import CompanionController

    class BrokenCloseController(CompanionController):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.close_calls = 0

        def close(self):
            self.close_calls += 1
            raise RuntimeError("controller close failed")

    app = QApplication.instance() or QApplication([])
    controller = BrokenCloseController(save_path=tmp_path / "save.json", auto_load=False)
    original_provider = controller.expression_context_provider
    window = CompanionWindow(controller=controller)
    window._manual_perception_summary = "manual context"

    window.closeEvent(QCloseEvent())
    app.processEvents()

    assert controller.close_calls == 1
    assert window._manual_perception_summary == ""
    assert controller.expression_context_provider is original_provider


def test_window_demo_buttons_trigger_proactive_companionship(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert "模拟低能量" in window.demo_low_charge_button.text()
    assert "模拟久未互动" in window.demo_quiet_mood_button.text()

    window.demo_low_charge_button.click()
    app.processEvents()

    assert "能量有点低" in window.feedback_label.text()
    assert "主动陪伴" in window.memory_label.text()

    window.close()
    app.processEvents()


def test_window_reset_demo_button_restores_clean_demo_state(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)
    window._handle_action("study")
    window.shop_list.setCurrentRow(0)
    window._handle_buy()
    window._handle_action("rest")
    app.processEvents()
    assert window.controller.get_snapshot()["memory_log"]

    window.demo_reset_button.click()
    app.processEvents()
    snapshot = window.controller.get_snapshot()

    assert "\u91cd\u7f6e\u6f14\u793a\u72b6\u6001" in window.demo_reset_button.text()
    assert snapshot["coins"] == 20
    assert snapshot["trust"] == 5
    assert snapshot["memory_log"] == []
    assert snapshot["resting"] is False

    window.close()
    app.processEvents()


def test_demo_save_cli_flags_select_isolated_demo_save():
    from guanghe_companion.app import should_reset_demo_save, should_use_demo_save

    assert should_use_demo_save(["demo", "--demo-save"]) is True
    assert should_use_demo_save(["demo", "--reset-demo-save"]) is True
    assert should_use_demo_save(["demo"]) is False
    assert should_reset_demo_save(["demo", "--reset-demo-save"]) is True
    assert should_reset_demo_save(["demo", "--demo-save"]) is False


def test_launch_reset_demo_save_uses_local_first_reset(monkeypatch):
    import guanghe_companion.app as app_module

    captured = {}

    class FakeApplication:
        def __init__(self, args):
            captured["app_args"] = args

        @staticmethod
        def instance():
            return None

        def exec(self):
            return 17

    class FakeController:
        def __init__(self, save_path=None):
            captured["save_path"] = save_path

        def reset_demo_state(self, **kwargs):
            captured["reset_kwargs"] = kwargs

    class FakeWindow:
        def __init__(self, controller, desktop_mode=False):
            captured["window_controller"] = controller
            captured["desktop_mode"] = desktop_mode

        def show(self):
            captured["shown"] = True

    monkeypatch.setattr(app_module, "QApplication", FakeApplication)
    monkeypatch.setattr(app_module, "CompanionController", FakeController)
    monkeypatch.setattr(app_module, "CompanionWindow", FakeWindow)
    monkeypatch.setattr(app_module, "configure_application_style", lambda app: True)

    result = app_module.launch(["demo", "--reset-demo-save"])

    assert result == 17
    assert captured["reset_kwargs"] == {"include_ai_expression": False}
    assert captured["shown"] is True


def test_launch_with_user_data_override_enables_user_character_packs(monkeypatch, tmp_path):
    import guanghe_companion.app as app_module

    captured = {}
    user_data_root = tmp_path / "preview-data"
    monkeypatch.setenv("E_MOTI_USER_DATA_DIR", str(user_data_root))

    class FakeApplication:
        def __init__(self, args):
            captured["app_args"] = args

        @staticmethod
        def instance():
            return None

        def exec(self):
            return 17

    class FakeController:
        def __init__(self, save_path=None, user_data_root=None):
            captured["save_path"] = save_path
            captured["user_data_root"] = user_data_root

    class FakeWindow:
        def __init__(self, controller, desktop_mode=False):
            captured["window_controller"] = controller
            captured["desktop_mode"] = desktop_mode

        def show(self):
            captured["shown"] = True

    monkeypatch.setattr(app_module, "QApplication", FakeApplication)
    monkeypatch.setattr(app_module, "CompanionController", FakeController)
    monkeypatch.setattr(app_module, "CompanionWindow", FakeWindow)
    monkeypatch.setattr(app_module, "configure_application_style", lambda app: True)

    result = app_module.launch(["demo", "--demo-save"])

    assert result == 17
    assert captured["user_data_root"] == user_data_root
    assert captured["save_path"] == user_data_root / "companion_demo_save.json"
    assert captured["shown"] is True
