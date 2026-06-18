from guanghe_companion.snapshot_renderer import SnapshotRenderer


def test_snapshot_renderer_extracts_first_valid_character_speech_for_tts():
    renderer = SnapshotRenderer()
    snapshot = {
        "character_name": "星汐",
        "events": [
            {"character_name": "STAT", "speech": "状态摘要", "sprite": "-1", "effect": ""},
            {"character_name": "星汐", "speech": "  先读这一句  ", "sprite": "1", "effect": "ATTENTION"},
            {"character_name": "星汐", "speech": "第二句不读", "sprite": "1", "effect": "ATTENTION"},
        ],
    }

    assert renderer.snapshot_tts_speech(snapshot) == "先读这一句"


def test_snapshot_renderer_formats_relationship_and_desktop_status_panel():
    renderer = SnapshotRenderer()
    snapshot = {
        "relationship_stage": "默契",
        "next_relationship_unlock": "信任达到 80",
        "relationship_presentation": {
            "address_line": "星汐会叫你阿澈",
            "tone_label": "温柔",
            "micro_motion": "轻轻晃动",
            "unlocked_decorations": [{"label": "星砂发夹"}, {"label": "蓝色丝带"}],
        },
        "mode": "Calm",
        "charge": 72.8,
        "mood": 66.2,
        "trust": 41.9,
        "motion_caption": "靠近回应",
        "feedback": "靠近我的方式，星汐记住了。",
    }

    assert renderer.format_relationship_presentation(snapshot) == (
        "当前关系：默契\n"
        "星汐会叫你阿澈\n"
        "语气：温柔 / 小动作：轻轻晃动\n"
        "装饰：星砂发夹 / 蓝色丝带\n"
        "下个解锁：信任达到 80"
    )
    assert renderer.format_desktop_status_panel(snapshot) == (
        "模式：Calm\n"
        "能量 72 / 心情 66 / 信任 41\n"
        "动作：靠近回应\n"
        "靠近我的方式，星汐记住了。"
    )


def test_snapshot_renderer_formats_memory_log_and_event_summary():
    renderer = SnapshotRenderer()

    assert renderer.format_memory_log([]) == "回忆日志：暂无回忆"
    assert renderer.format_memory_log(
        [
            {"kind": "touch", "summary": "靠近回应"},
            {"kind": "gift", "summary": "收下热牛奶"},
        ]
    ) == "回忆日志：\n- touch：靠近回应\n- gift：收下热牛奶"
    assert renderer.format_event_summary(
        [
            {"character_name": "星汐", "speech": "我在。"},
            {"character_name": "STAT", "speech": "mood +2"},
            {"character_name": "CHOICE", "speech": "轻触 / 休息"},
            {"character_name": "星汐", "speech": "第四条不会显示"},
        ]
    ) == "星汐：我在。\n状态：mood +2\n可选动作：轻触 / 休息"
