from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx


def start(root, port):
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"), PYTHONUTF8="1")
    process = subprocess.Popen([sys.executable, "-m", "guanghe_companion.host_runtime",
        "--data-root", str(root), "--port", str(port)], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    with ThreadPoolExecutor(1) as worker:
        invitation = json.loads(worker.submit(process.stdout.readline).result(timeout=15))["pairing_invitation"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return process, invitation
        except OSError:
            if process.poll() is not None:
                raise RuntimeError("host stopped before listening")
            time.sleep(0.02)
    process.terminate()
    process.wait(timeout=5)
    raise TimeoutError("host startup")


def test_real_process_restart_retains_device_and_memory_but_rejects_old_session(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process, invitation = start(tmp_path, port)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            token = client.post("/v1/pair", json={"invitation": invitation, "device_name": "restart-client"}).json()["access_token"]
            client.headers["Authorization"] = "Bearer " + token
            session = client.get("/v1/session").json()
            body = {"session_id": session["session_id"], "expected_epoch": session["context_epoch"],
                    "expected_revision": session["revision"], "request_id": "remember-before-restart",
                    "operation": "remember", "text": "我喜欢桂花茶"}
            assert client.post("/v1/memory", json=body).status_code == 200
        process.terminate()
        process.wait(timeout=5)
        process, _ = start(tmp_path, port)
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False,
                          headers={"Authorization": "Bearer " + token}) as client:
            assert client.get("/v1/session").json()["session_id"] != session["session_id"]
            assert "桂花茶" in client.get("/v1/memory").text
            assert client.post("/v1/memory", json=body).json()["error"]["code"] == "session_changed"
    finally:
        process.terminate()
        process.wait(timeout=5)
