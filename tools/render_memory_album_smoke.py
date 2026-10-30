"""Render only synthetic, disposable album data; never opens a user save."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.memory_album_controller import MemoryAlbumController
from guanghe_companion.memory_album_qt import create_memory_album_widget


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("memory_album_lifecycle_smoke.png"))
    args = parser.parse_args()
    app = QApplication([])
    if args.font:
        font_id = QFontDatabase.addApplicationFont(str(args.font))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            raise RuntimeError(f"Could not load preview font: {args.font}")
        app.setFont(QFont(families[0], 11))
    with TemporaryDirectory(prefix="emoti-album-smoke-") as root:
        story = CompanionStoryRuntime.create(user_data_root=Path(root), character_id="xingxi_pixel_pet")
        story.memory.remember(
            kind="玩家希望被记住", title="我的陪伴偏好",
            summary="我喜欢好奇、自然、偶尔吐槽的相处方式；忙碌时请保持安静。",
            source="explicit_user_request", now=10, user_confirmed=True,
        )
        story.memory.propose_explicit_user_memory("请记住：我周末喜欢练习电吉他。", now=20)
        widget = create_memory_album_widget(MemoryAlbumController(story))
        widget.resize(800, 620)
        widget.show()
        app.processEvents()
        if not widget.grab().save(str(args.output)):
            raise RuntimeError("Could not save album preview")
        print(args.output)
        widget.close()


if __name__ == "__main__":
    main()
