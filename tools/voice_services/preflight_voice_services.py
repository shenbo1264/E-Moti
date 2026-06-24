from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from guanghe_companion.voice_service_control import (
    DEFAULT_VOICE_SERVICE_ENDPOINTS,
    _probe_http as _shared_probe_http,
    probe_voice_services,
)

DEFAULT_ENDPOINTS = {
    endpoint.service_id: endpoint.url for endpoint in DEFAULT_VOICE_SERVICE_ENDPOINTS
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local E-Moti voice services.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args(argv)

    statuses = probe_voice_services(timeout=args.timeout, probe=_probe_http)
    report: dict[str, dict[str, object]] = {
        status.service_id: {
            "ok": status.ok,
            "label": status.label,
            "url": status.url,
            "message": status.message,
        }
        for status in statuses
    }
    exit_code = 0 if all(status.ok for status in statuses) else 1

    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return exit_code


def _probe_http(url: str, timeout: float) -> tuple[bool, str]:
    return _shared_probe_http(url, timeout)


if __name__ == "__main__":
    raise SystemExit(main())
