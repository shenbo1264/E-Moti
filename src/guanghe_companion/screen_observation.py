from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageGrab

from .capability_settings import ScreenObservationSettings
from .expression_context import _sanitize_perception_summary


@dataclass(frozen=True, slots=True)
class ScreenObservationResult:
    ok: bool
    message: str
    summary: str = ""


class PillowScreenCapture:
    def __init__(self, grab_func: Callable[..., Image.Image] | None = None) -> None:
        self._grab_func = grab_func or ImageGrab.grab

    def capture(self) -> Image.Image:
        return self._grab_func(all_screens=True)


def screenshot_to_png_data_url(image: Image.Image, *, max_width: int) -> str:
    resized = image
    if resized.width > max_width:
        ratio = max_width / resized.width
        resized = resized.resize((max_width, max(1, int(resized.height * ratio))))
    output = io.BytesIO()
    resized.convert("RGB").save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def openai_vision_transport(payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    base_url = str(payload.get("_base_url", "")).rstrip("/")
    api_key = str(payload.get("_api_key", ""))
    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    request_payload = {key: value for key, value in payload.items() if not key.startswith("_")}
    data = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
    auth_header = _vision_auth_headers(base_url, api_key)
    request = urllib.request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            **auth_header,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _vision_auth_headers(base_url: str, api_key: str) -> dict[str, str]:
    if "xiaomimimo.com" in base_url.lower():
        return {"api-key": api_key}
    return {"Authorization": f"Bearer {api_key}"}


class ScreenObservationService:
    def __init__(
        self,
        *,
        capture: Callable[[], Image.Image] | None = None,
        vision_transport: Callable[[dict[str, Any], int], dict[str, Any]] | None = None,
    ) -> None:
        self._capture = capture or PillowScreenCapture().capture
        self._vision_transport = vision_transport or openai_vision_transport

    def observe(self, settings: ScreenObservationSettings) -> ScreenObservationResult:
        if not settings.enabled:
            return ScreenObservationResult(False, "屏幕观察未启用")
        if not settings.vision_model or not settings.vision_base_url or not settings.vision_api_key:
            return ScreenObservationResult(False, "缺少视觉模型、Base URL 或 API Key")
        try:
            image = self._capture()
            data_url = screenshot_to_png_data_url(image, max_width=settings.max_screenshot_width)
            payload = _build_vision_payload(settings, data_url)
            response = self._vision_transport(payload, settings.timeout_seconds)
            summary = _extract_summary(response)
            if not summary:
                return ScreenObservationResult(False, "视觉模型未返回摘要")
            return ScreenObservationResult(True, "屏幕观察完成", summary)
        except (OSError, ValueError, KeyError, urllib.error.URLError, TimeoutError) as exc:
            return ScreenObservationResult(False, f"屏幕观察失败：{exc}")


def _build_vision_payload(settings: ScreenObservationSettings, data_url: str) -> dict[str, Any]:
    payload = {
        "_base_url": settings.vision_base_url,
        "_api_key": settings.vision_api_key,
        "model": settings.vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "请用不超过 80 个中文字符描述这张桌面截图里与用户当前任务相关的可见信息。"
                            "不要推断隐私内容，不要输出操作指令。"
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0.2,
        "max_tokens": 120,
    }
    if _is_mimo_base_url(settings.vision_base_url):
        payload.pop("max_tokens", None)
        payload["max_completion_tokens"] = 180
        payload["thinking"] = {"type": "disabled"}
    return payload


def _extract_summary(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    return _sanitize_perception_summary(message.get("content"))


def _is_mimo_base_url(base_url: str) -> bool:
    return "xiaomimimo.com" in str(base_url).lower()
