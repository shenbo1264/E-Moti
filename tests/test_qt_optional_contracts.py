import inspect
import pytest

from guanghe_companion.focus_companion_qt import create_focus_companion_widget
from guanghe_companion.memory_album_qt import create_memory_album_widget
from guanghe_companion.plugin_center_qt import create_plugin_center_widget


def test_qt_modules_import_without_pyside6():
    assert callable(create_focus_companion_widget)
    assert callable(create_memory_album_widget)
    assert callable(create_plugin_center_widget)


def test_qt_factories_accept_on_changed():
    for factory in (create_focus_companion_widget,create_memory_album_widget,create_plugin_center_widget):
        assert 'on_changed' in inspect.signature(factory).parameters


def test_qt_factories_fail_cleanly_without_dependency():
    for factory in (create_focus_companion_widget,create_memory_album_widget,create_plugin_center_widget):
        with pytest.raises(RuntimeError,match='PySide6'):
            factory(object())
