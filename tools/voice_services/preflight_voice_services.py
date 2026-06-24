from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Sequence

DEFAULT_ENDPOINTS = {
    "qwen3tts": "http://127.0.0.1:9880/tts",
    "gptsovits": "http://127.0.0.1:9882/",
    "sensevoice_asr": "http://127.0.0.1:8899/v1/models",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local E-Moti voice services.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args(argv)

    report: dict[str, dict[str, object]] = {}
    exit_code = 0
    for name, url in DEFAULT_ENDPOINTS.items():
        ok, message = _probe_http(url, args.timeout)
        report[name] = {"ok": ok, "url": url, "message": message}
        if not ok:
            exit_code = 1

    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return exit_code


def _probe_http(url: str, timeout: float) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return True, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        if 200 <= exc.code < 500:
            return True, f"HTTP {exc.code}"
        return False, f"HTTP {exc.code}"
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return False, str(exc)


if __name__ == "__main__":
    raise SystemExit(main())

