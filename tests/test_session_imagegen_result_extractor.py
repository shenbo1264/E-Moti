from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from tools.art.extract_session_imagegen_result import extract_session_imagegen_result


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "art" / "extract_session_imagegen_result.py"


def _png_base64(path: Path, color: tuple[int, int, int, int]) -> str:
    image = Image.new("RGBA", (4, 4), color)
    image.save(path)
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_extract_session_imagegen_result_writes_png_and_report(tmp_path: Path) -> None:
    source_png = tmp_path / "payload.png"
    payload = _png_base64(source_png, (255, 0, 255, 255))
    session = tmp_path / "session.jsonl"
    output_dir = tmp_path / "out"
    report_path = tmp_path / "report.json"
    _write_jsonl(
        session,
        [
            {
                "type": "event_msg",
                "payload": {
                    "type": "image_generation_end",
                    "call_id": "ig_idle_001",
                    "result": payload,
                    "revised_prompt": "idle row candidate",
                },
            }
        ],
    )

    report = extract_session_imagegen_result(
        session_path=session,
        output_dir=output_dir,
        call_id="ig_idle_001",
        report_path=report_path,
    )

    assert report.ok is True
    assert report.status == "extracted"
    assert report.call_id == "ig_idle_001"
    assert report.source_line == 1
    assert Path(report.output_path).is_file()
    assert Path(report.output_path).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    payload_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload_report["ok"] is True
    assert payload_report["sha256"]


def test_extract_session_imagegen_result_rejects_non_ig_call_id(tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    _write_jsonl(session, [])

    report = extract_session_imagegen_result(
        session_path=session,
        output_dir=tmp_path / "out",
        call_id="not_imagegen",
    )

    assert report.ok is False
    assert report.status == "invalid_call_id"
    assert report.errors == ("call_id must start with ig_",)


def test_extract_session_imagegen_result_selects_latest_matching_prompt(tmp_path: Path) -> None:
    first_png = tmp_path / "first.png"
    second_png = tmp_path / "second.png"
    session = tmp_path / "session.jsonl"
    _write_jsonl(
        session,
        [
            {
                "type": "event_msg",
                "payload": {
                    "call_id": "ig_idle_old",
                    "result": _png_base64(first_png, (255, 0, 0, 255)),
                    "revised_prompt": "Generate the idle row for Xingxi",
                },
            },
            {
                "type": "event_msg",
                "payload": {
                    "call_id": "ig_idle_new",
                    "result": _png_base64(second_png, (0, 255, 0, 255)),
                    "revised_prompt": "Generate the idle row for Xingxi with better blink",
                },
            },
        ],
    )

    report = extract_session_imagegen_result(
        session_path=session,
        output_dir=tmp_path / "out",
        contains=("idle row",),
        latest=True,
    )

    assert report.ok is True
    assert report.call_id == "ig_idle_new"
    with Image.open(report.output_path) as image:
        assert image.getpixel((0, 0)) == (0, 255, 0, 255)


def test_extract_session_imagegen_result_cli_writes_report(tmp_path: Path) -> None:
    source_png = tmp_path / "payload.png"
    session = tmp_path / "session.jsonl"
    report_path = tmp_path / "report.json"
    _write_jsonl(
        session,
        [
            {
                "type": "event_msg",
                "payload": {
                    "call_id": "ig_cli_001",
                    "result": _png_base64(source_png, (0, 0, 255, 255)),
                    "revised_prompt": "running-right row candidate",
                },
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            str(session),
            "--call-id",
            "ig_cli_001",
            "--output-dir",
            str(tmp_path / "out"),
            "--report",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert report_path.is_file()
