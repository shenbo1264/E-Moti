from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request

import pytest
from PySide6.QtWidgets import QApplication
from guanghe_companion.expression_clients import OpenAICompatibleChatClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("persona_behavior_eval_under_test", ROOT / "tools/persona_behavior_eval.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_persona_cli_uses_explicit_application_settings():
    result = subprocess.run([sys.executable, str(ROOT / "tools/persona_behavior_eval.py"), "--help"],
                            capture_output=True, text=True, encoding="utf-8", check=True)
    assert "--app-settings" in result.stdout
    assert "--api-key-env" not in result.stdout


def test_failed_real_http_is_counted_and_retained_before_budget_stops_next_call(tmp_path):
    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(422)
            self.end_headers()
            self.wfile.write(b'{"error":{"message":"contract request rejected"}}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    body = {"model": "contract-only", "messages": [{"role": "user", "content": "JSON evidence request"}]}
    request = Request(f"http://127.0.0.1:{server.server_port}/chat/completions",
                      data=json.dumps(body).encode(), headers={"Authorization": "Bearer protocol-secret"})
    journal = tmp_path / "provider-calls.json"
    meter = module.FlashMeter(1, journal_path=journal, secret="protocol-secret")
    try:
        with pytest.raises(HTTPError):
            meter(request, 2)
        assert meter.calls == 1
        assert len(meter.records) == 1
        record = meter.records[0]
        assert record["wire_payload"] == body
        assert record["error_type"] == "HTTPError"
        assert record["http_status"] == 422
        assert record["raw_response_text"] == '{"error":{"message":"contract request rejected"}}'
        assert record["transport_latency_ms"] >= 0
        assert "protocol-secret" not in json.dumps(record)
        assert json.loads(journal.read_text(encoding="utf-8"))["calls"] == [record]
        with pytest.raises(module.BudgetExceeded):
            meter(request, 2)
        assert len(received) == 1
        assert meter.calls == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_local_quiet_scenario_closes_actual_service_without_model_calls(tmp_path):
    app = QApplication.instance() or QApplication([])
    meter = module.FlashMeter(1)

    def reject_network(*args):
        raise AssertionError("local quiet command must not invoke a model")

    def new_client():
        return OpenAICompatibleChatClient(api_key="", require_api_key=False, transport=reject_network)

    result = module.run_scenario(app, {"id": "local_quiet", "dimensions": ["quiet"],
        "seed": [], "turns": ["先别说话了"]}, new_client, meter, tmp_path / "archives")
    assert result["model_status"] == "not_run"
    assert result["calls"] == []
    assert result["turns"][0]["model_status"] == "not_run", result
    assert not list((tmp_path / "archives").iterdir())
