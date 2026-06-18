from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote

from PIL import Image
from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "tmp/live2d_research/CubismWebSamples/Samples/Resources/Haru/Haru.model3.json"
DEFAULT_CORE = "tmp/live2d_research/live2dcubismcore.min.js"


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test the local Live2D Web spike with QWebEngine.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Repo-relative .model3.json path.")
    parser.add_argument("--core", default=DEFAULT_CORE, help="Repo-relative live2dcubismcore.min.js path.")
    parser.add_argument("--expression", default="F01")
    parser.add_argument("--motion-group", default="TapBody")
    parser.add_argument(
        "--actions-json",
        default=json.dumps(
            [
                {"type": "expression", "id": "excited", "ttl_ms": 3000, "priority": 70, "source": "llm"},
                {"type": "motion", "id": "Play", "ttl_ms": 1800, "priority": 60, "source": "llm"},
            ],
            ensure_ascii=False,
        ),
        help="JSON array using E-Moti visual_actions shape.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--screenshot", default="artifacts/simulation/live2d_spike.png")
    return parser.parse_args(argv)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_server() -> tuple[ThreadingHTTPServer, str]:
    port = free_port()

    class Handler(QuietStaticHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def wait_for_loaded(view: QWebEngineView, timeout_seconds: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_state: dict[str, object] = {}
    while time.monotonic() < deadline:
        loop = QEventLoop()
        holder: dict[str, object] = {}

        def receive(value: object) -> None:
            holder["value"] = value
            loop.quit()

        view.page().runJavaScript("window.live2dSpike ? JSON.stringify(window.live2dSpike) : ''", receive)
        QTimer.singleShot(500, loop.quit)
        loop.exec()
        raw = holder.get("value")
        if isinstance(raw, str) and raw:
            last_state = json.loads(raw)
            if last_state.get("error"):
                raise RuntimeError(str(last_state["error"]))
            if last_state.get("loaded") and int(last_state.get("frameSamples") or 0) >= 5:
                return last_state
        QApplication.processEvents()
        time.sleep(0.1)
    raise TimeoutError(f"Live2D spike did not load within {timeout_seconds}s; last_state={last_state!r}")


def grab_nonblank(view: QWebEngineView, screenshot_path: Path) -> dict[str, object]:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = view.grab()
    if pixmap.isNull():
        raise RuntimeError("QWebEngine screenshot is null")
    pixmap.save(str(screenshot_path))
    image = Image.open(screenshot_path).convert("RGBA")
    colors = image.getcolors(maxcolors=1_000_000)
    unique_colors = len(colors or [])
    alpha_extrema = image.getchannel("A").getextrema()
    if unique_colors < 64:
        raise RuntimeError(f"Live2D screenshot appears blank: unique_colors={unique_colors}")
    return {
        "path": str(screenshot_path),
        "size": image.size,
        "unique_colors": unique_colors,
        "alpha_extrema": alpha_extrema,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    model_path = REPO_ROOT / args.model
    core_path = REPO_ROOT / args.core
    if not model_path.is_file():
        raise FileNotFoundError(f"missing Live2D model: {model_path}")
    if not core_path.is_file():
        raise FileNotFoundError(f"missing Cubism Core runtime: {core_path}")

    app = QApplication.instance() or QApplication([])
    server, base_url = start_server()
    try:
        view = QWebEngineView()
        view.resize(720, 900)
        encoded_model = quote(args.model.replace("\\", "/"), safe="/:")
        url = (
            f"{base_url}/tools/live2d_spike/index.html"
            f"?model=/{encoded_model}"
            f"&expression={quote(args.expression)}"
            f"&motionGroup={quote(args.motion_group)}"
            f"&actions={quote(args.actions_json)}"
        )
        view.load(QUrl(url))
        view.show()
        state = wait_for_loaded(view, args.timeout_seconds)
        applied_actions = state.get("appliedVisualActions")
        if args.actions_json and not applied_actions:
            raise RuntimeError(f"visual_actions were not applied: state={state!r}")
        shot = grab_nonblank(view, REPO_ROOT / args.screenshot)
        print(
            json.dumps(
                {
                    "ok": True,
                    "url": url,
                    "state": state,
                    "screenshot": shot,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        view.close()
        return 0
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
