from __future__ import annotations

"""Open the real desktop window on a throwaway save seeded with synthetic memories.

For hand acceptance of the memory album. It never touches the user's save, and
no model is configured: replies are local fallbacks, not model behaviour.
"""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication

from guanghe_companion.app import CompanionWindow, MEMORY_ALBUM_PAGE_INDEX
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def seed(controller) -> None:
    memory = controller.story_runtime.memory
    controller.now = 200_000
    album = controller.memory_album_controller
    album.remember_explicit("我喜欢喝乌龙茶")
    album.remember_explicit("我住在杭州")
    memory.remember(kind="日常", title="周末计划", summary="周六一起看展", source="user_chat", now=200_000,
                    metadata={"plan_status": "planned"})
    memory.remember(kind="共同学习", title="一起练琴", summary="第一次一起练琴，弹错了三次", source="game_event", now=200_000)
    memory.remember(kind="任务", title="导出备份", summary="导出成功", source="trusted_executor", now=200_000,
                    scope="task_experience", metadata={"outcome": "succeeded"})
    secret = album.remember_explicit("测试用的秘密：橙色猫")
    target = next(row for row in memory.store.load_memories() if "橙色猫" in row.summary)
    album.forget(target.memory_id)
    del secret


def scripted(app, window, controller, out: Path) -> None:
    """Drive the real native window through Qt signals and save what it renders.

    This is program-driven evidence, not a person using a mouse.
    """
    out.mkdir(parents=True, exist_ok=True)
    window.resize(1100, 860)
    page = window.memory_album_page

    def shot(name: str) -> None:
        app.processEvents()
        window.grab().save(str(out / f"{name}.png"))

    shot("01-ledger")
    page.memory_ask_input.setText("我喜欢喝什么")
    page.memory_ask_button.click()
    shot("02-overview-sufficient")
    page.memory_claim_list.itemClicked.emit(page.memory_claim_list.item(0))
    shot("03-expanded-sources")
    page.memory_ask_input.setText("我的牙医叫什么名字")
    page.memory_ask_button.click()
    shot("04-unknown-calm")
    live = next(i for i in range(page.memory_list.count())
                if "我住在杭州" in page.memory_list.item(i).text())
    page.memory_list.setCurrentRow(live)
    page.memory_action_buttons[1].click()
    dialog = page.memory_edit_dialog
    dialog.summary_input.setPlainText("太长" * 200)
    dialog.save()
    app.processEvents()
    dialog.grab().save(str(out / "05-save-failed-draft-kept.png"))
    dialog.intents["change"].setChecked(True)
    dialog.summary_input.setPlainText("我搬到南京了")
    dialog.save()
    shot("06-reality-change-history")


def main() -> int:
    app = QApplication(sys.argv)
    args = [a for a in sys.argv[1:] if not a.startswith("--shots=")]
    shots = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--shots=")), "")
    root = Path(args[0]) if args else Path(tempfile.mkdtemp(prefix="emoti-acceptance-"))
    controller = PluginEnabledCompanionController(user_data_root=root)
    seed(controller)
    window = CompanionWindow(controller=controller)
    window.setWindowTitle("E-Moti 验收（测试存档）")
    window.show()
    window._select_navigation_button(MEMORY_ALBUM_PAGE_INDEX)
    window.memory_album_page.refresh_memory_album()
    if shots:
        scripted(app, window, controller, Path(shots))
        window.close()
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
