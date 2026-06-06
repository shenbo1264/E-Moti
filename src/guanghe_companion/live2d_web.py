from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView

from .presentation_renderer import PresentationFrame

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE2D_PAGE_PATH = "tools/live2d_spike/index.html"
CHARACTER_ASSET_ROUTE = "/character-assets/"
MISSING_ASSET = REPO_ROOT / "__missing_live2d_asset__"


@dataclass(slots=True)
class Live2DServerHandle:
    server: ThreadingHTTPServer
    base_url: str
    asset_dir: Path

    def shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def build_live2d_page_url(base_url: str, frame: PresentationFrame, asset_dir: Path | str) -> str:
    model_rel = _safe_model_relative_path(frame.model_path)
    root = Path(asset_dir)
    model_path = (root / model_rel).resolve()
    root_resolved = root.resolve()
    try:
        model_path.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Live2D model path must stay inside character asset directory") from exc
    if not model_path.is_file():
        raise FileNotFoundError(f"Live2D model not found: {model_path}")
    mapped_actions = json.dumps(list(frame.live2d_actions), ensure_ascii=False, separators=(",", ":"))
    model_url = CHARACTER_ASSET_ROUTE + quote(model_rel.as_posix(), safe="/")
    return (
        f"{base_url.rstrip('/')}/{LIVE2D_PAGE_PATH}"
        f"?model={quote(model_url, safe='/:')}"
        f"&mappedActions={quote(mapped_actions, safe='')}"
    )


def has_safe_live2d_model(asset_dir: Path | str, model_path: str) -> bool:
    try:
        model_rel = _safe_model_relative_path(model_path)
    except ValueError:
        return False
    return (Path(asset_dir) / model_rel).is_file()


def start_live2d_server(asset_dir: Path | str) -> Live2DServerHandle:
    port = _free_port()
    resolved_asset_dir = Path(asset_dir).resolve()

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def translate_path(self, path: str) -> str:
            request_path = unquote(urlparse(path).path)
            return str(resolve_live2d_static_path(request_path, resolved_asset_dir))

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return Live2DServerHandle(server=server, base_url=f"http://127.0.0.1:{port}", asset_dir=resolved_asset_dir)


def resolve_live2d_static_path(request_path: str, asset_dir: Path | str) -> Path:
    path = unquote(urlparse(request_path).path)
    asset_root = Path(asset_dir).resolve()
    if path.startswith(CHARACTER_ASSET_ROUTE):
        rel = Path(path.removeprefix(CHARACTER_ASSET_ROUTE))
        candidate = (asset_root / rel).resolve()
        try:
            candidate.relative_to(asset_root)
        except ValueError:
            return MISSING_ASSET
        return candidate
    rel_repo_path = Path(path.lstrip("/"))
    candidate = (REPO_ROOT / rel_repo_path).resolve()
    if _is_allowed_repo_static_path(candidate):
        return candidate
    return MISSING_ASSET


class Live2DWebSurface(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.loaded_frames: list[tuple[PresentationFrame, object]] = []
        self.last_url = ""
        self._server: Live2DServerHandle | None = None
        self._view: QWebEngineView | None = None
        self._status_label = QLabel("Live2D renderer")
        self._status_label.setObjectName("Live2DWebSurfaceStatus")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._status_label)
        self.setObjectName("Live2DWebSurface")

    def load_frame(self, frame: PresentationFrame, asset_dir: object) -> None:
        self.loaded_frames.append((frame, asset_dir))
        try:
            asset_path = Path(asset_dir)
            self._server = self._server or start_live2d_server(asset_path)
            url = build_live2d_page_url(self._server.base_url, frame, asset_path)
        except Exception as exc:
            self.last_url = ""
            self._status_label.setText(str(exc))
            self._status_label.show()
            return
        self.last_url = url
        self._status_label.hide()
        self._ensure_view().load(QUrl(url))

    def shutdown(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)

    def _ensure_view(self) -> QWebEngineView:
        if self._view is None:
            self._view = QWebEngineView(self)
            self.layout().addWidget(self._view)
        return self._view


def _safe_model_relative_path(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Live2D model path must be a non-empty string")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Live2D model path must stay inside character asset directory")
    if path.suffix != ".json" or not path.name.endswith(".model3.json"):
        raise ValueError("Live2D model path must point to a .model3.json file")
    return path


def _is_allowed_repo_static_path(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return False
    parts = rel.parts
    if len(parts) >= 2 and parts[0] == "tools" and parts[1] == "live2d_spike":
        return True
    if parts == ("tmp", "live2d_research", "live2dcubismcore.min.js"):
        return True
    return False


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
