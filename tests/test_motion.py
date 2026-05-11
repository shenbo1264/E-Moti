from guanghe_companion.motion import MotionAnimator, load_default_motion_catalog


def test_load_default_motion_catalog_reads_core_rows():
    catalog = load_default_motion_catalog()

    idle = catalog.resolve("Default")
    touch = catalog.resolve("TouchHead")

    assert catalog.sheet_columns == 8
    assert catalog.frame_width == 192
    assert catalog.frame_height == 208
    assert idle.row == 0
    assert idle.frame_count == 6
    assert touch.row == 3
    assert touch.frame_count == 4


def test_motion_catalog_uses_spritesheet_from_character_pack():
    catalog = load_default_motion_catalog()

    assert catalog.sheet_path.name == "spritesheet.png"


def test_motion_animator_cycles_frames_for_selected_motion():
    catalog = load_default_motion_catalog()
    animator = MotionAnimator(catalog)

    animator.set_motion("TouchHead")
    first = animator.current_frame_rect()
    second = animator.advance()
    third = animator.advance()

    assert first.x() == 0
    assert second.x() == 192
    assert third.x() == 384
    assert first.y() == second.y() == third.y() == 208 * 3


def test_motion_animator_falls_back_to_default_when_motion_missing():
    catalog = load_default_motion_catalog()
    animator = MotionAnimator(catalog)

    animator.set_motion("UnknownMotion")
    rect = animator.current_frame_rect()

    assert rect.y() == 0
    assert rect.width() == 192
