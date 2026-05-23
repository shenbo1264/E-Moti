from __future__ import annotations

import base64
import io

from PIL import Image

from guanghe_companion.capability_settings import ScreenObservationSettings


def make_image(width: int = 2000, height: int = 1000) -> Image.Image:
    return Image.new("RGB", (width, height), "#336699")


def test_screenshot_is_resized_to_data_url_without_disk_write(tmp_path):
    from guanghe_companion.screen_observation import PillowScreenCapture, screenshot_to_png_data_url

    capture = PillowScreenCapture(grab_func=lambda all_screens: make_image())

    image = capture.capture()
    data_url = screenshot_to_png_data_url(image, max_width=640)

    assert data_url.startswith("data:image/png;base64,")
    payload = base64.b64decode(data_url.split(",", 1)[1])
    decoded = Image.open(io.BytesIO(payload))
    assert decoded.width == 640
    assert decoded.height == 320
    assert list(tmp_path.iterdir()) == []


def test_observation_service_sends_image_to_vision_and_sanitizes_summary():
    from guanghe_companion.screen_observation import ScreenObservationService

    requests = []

    def fake_transport(payload, timeout):
        requests.append((payload, timeout))
        return {"choices": [{"message": {"content": "  看到 IDE 和测试输出。\n还有控制字符\t  "}}]}

    service = ScreenObservationService(
        capture=lambda: make_image(1200, 600),
        vision_transport=fake_transport,
    )

    result = service.observe(
        ScreenObservationSettings(
            enabled=True,
            vision_base_url="https://vision.example.test/v1",
            vision_api_key="secret",
            vision_model="vision-test",
            timeout_seconds=12,
        )
    )

    assert result.ok is True
    assert result.summary == "看到 IDE 和测试输出。 还有控制字符"
    assert requests[0][1] == 12
    content = requests[0][0]["messages"][0]["content"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_observation_disabled_or_missing_config_returns_reason():
    from guanghe_companion.screen_observation import ScreenObservationService

    service = ScreenObservationService(capture=lambda: make_image(), vision_transport=lambda payload, timeout: {})

    disabled = service.observe(ScreenObservationSettings(enabled=False))
    missing = service.observe(ScreenObservationSettings(enabled=True, vision_model="", vision_base_url=""))

    assert disabled.ok is False
    assert "未启用" in disabled.message
    assert missing.ok is False
    assert "视觉模型" in missing.message
