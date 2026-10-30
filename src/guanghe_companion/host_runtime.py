import argparse
import ipaddress
import json
from pathlib import Path
import signal
import threading

from PySide6.QtCore import QCoreApplication, QLockFile, QTimer
import uvicorn

from .host_auth import DeviceCredentials
from .host_service import CompanionHost
from .host_transport import create_host_app
from .plugin_enabled_controller import PluginEnabledCompanionController


class HostServer:
    def __init__(self, host: CompanionHost, *, bind="127.0.0.1", port=8765, certfile=None, keyfile=None):
        if not ipaddress.ip_address(bind).is_loopback and not (certfile and keyfile):
            raise ValueError("external host binding requires a TLS certificate and key")
        self.server = uvicorn.Server(uvicorn.Config(create_host_app(host), host=bind, port=port,
            ssl_certfile=certfile, ssl_keyfile=keyfile, access_log=False, proxy_headers=False,
            limit_concurrency=32, timeout_graceful_shutdown=3))
        self.thread = threading.Thread(target=self.server.run, name="companion-http", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.should_exit = True


def main():
    parser = argparse.ArgumentParser(description="E-Moti explicit opt-in host")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--certfile")
    parser.add_argument("--keyfile")
    args = parser.parse_args()
    app = QCoreApplication.instance() or QCoreApplication([])
    args.data_root.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(args.data_root / "host.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise RuntimeError("another host owns this data directory")
    controller = PluginEnabledCompanionController(user_data_root=args.data_root)
    host = CompanionHost(controller, DeviceCredentials(args.data_root / "host-devices.sqlite3"))
    server = HostServer(host, bind=args.bind, port=args.port, certfile=args.certfile, keyfile=args.keyfile)
    print(json.dumps({"pairing_invitation": host.create_invitation(), "expires_in": 300}), flush=True)
    server.start()
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    timer = QTimer()
    timer.setInterval(250)
    timer.timeout.connect(lambda: app.quit() if not server.thread.is_alive() else None)
    timer.start()
    try:
        return app.exec()
    finally:
        server.stop()
        host.close()
        server.thread.join(timeout=4)
        controller.close()
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
