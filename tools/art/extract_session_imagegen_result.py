from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SAFE_CALL_ID = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class SessionImagegenResultReport:
    ok: bool
    status: str
    session_path: str
    output_dir: str
    output_path: str
    call_id: str
    source_line: int
    revised_prompt: str
    sha256: str
    byte_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "session_path": self.session_path,
            "output_dir": self.output_dir,
            "output_path": self.output_path,
            "call_id": self.call_id,
            "source_line": self.source_line,
            "revised_prompt": self.revised_prompt,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class _ImagegenRecord:
    call_id: str
    result: str
    revised_prompt: str
    line_number: int


def extract_session_imagegen_result(
    *,
    session_path: Path | str,
    output_dir: Path | str,
    call_id: str = "",
    contains: tuple[str, ...] = (),
    latest: bool = False,
    report_path: Path | str | None = None,
) -> SessionImagegenResultReport:
    session = Path(session_path)
    target_dir = Path(output_dir)
    errors: list[str] = []
    warnings: list[str] = []

    normalized_call_id = call_id.strip()
    contains_terms = tuple(term.strip().casefold() for term in contains if term.strip())
    if normalized_call_id and not normalized_call_id.startswith("ig_"):
        return _report(
            ok=False,
            status="invalid_call_id",
            session=session,
            output_dir=target_dir,
            errors=("call_id must start with ig_",),
        )
    if normalized_call_id and not SAFE_CALL_ID.match(normalized_call_id):
        return _report(
            ok=False,
            status="invalid_call_id",
            session=session,
            output_dir=target_dir,
            errors=("call_id contains unsafe characters",),
        )
    if not normalized_call_id and not contains_terms:
        return _report(
            ok=False,
            status="missing_selector",
            session=session,
            output_dir=target_dir,
            errors=("provide --call-id or at least one --contains term",),
        )
    if not session.is_file():
        return _report(
            ok=False,
            status="missing_session",
            session=session,
            output_dir=target_dir,
            errors=(f"session JSONL not found: {session}",),
        )

    records = _matching_records(
        session,
        call_id=normalized_call_id,
        contains_terms=contains_terms,
        errors=errors,
        warnings=warnings,
    )
    if errors:
        return _report(
            ok=False,
            status="invalid_session",
            session=session,
            output_dir=target_dir,
            errors=tuple(_dedupe(errors)),
            warnings=tuple(_dedupe(warnings)),
        )
    if not records:
        return _report(
            ok=False,
            status="not_found",
            session=session,
            output_dir=target_dir,
            errors=("no matching imagegen result found",),
            warnings=tuple(_dedupe(warnings)),
        )
    if len(records) > 1 and not latest and not normalized_call_id:
        return _report(
            ok=False,
            status="ambiguous",
            session=session,
            output_dir=target_dir,
            errors=("multiple matching imagegen results found; pass --latest or --call-id",),
            warnings=tuple(_dedupe(warnings)),
        )

    record = records[-1] if latest else records[0]
    image_bytes, decode_error = _decode_png(record.result)
    if decode_error:
        return _report(
            ok=False,
            status="invalid_image_payload",
            session=session,
            output_dir=target_dir,
            call_id=record.call_id,
            source_line=record.line_number,
            revised_prompt=record.revised_prompt,
            errors=(decode_error,),
            warnings=tuple(_dedupe(warnings)),
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"{record.call_id}.png"
    if output_path.exists():
        return _report(
            ok=False,
            status="output_exists",
            session=session,
            output_dir=target_dir,
            output_path=output_path,
            call_id=record.call_id,
            source_line=record.line_number,
            revised_prompt=record.revised_prompt,
            errors=(f"output already exists: {output_path}",),
            warnings=tuple(_dedupe(warnings)),
        )
    output_path.write_bytes(image_bytes)
    sha = hashlib.sha256(image_bytes).hexdigest()
    report = _report(
        ok=True,
        status="extracted",
        session=session,
        output_dir=target_dir,
        output_path=output_path,
        call_id=record.call_id,
        source_line=record.line_number,
        revised_prompt=record.revised_prompt,
        sha256=sha,
        byte_count=len(image_bytes),
        warnings=tuple(_dedupe(warnings)),
    )
    if report_path:
        _write_json(Path(report_path), report)
    return report


def _matching_records(
    session: Path,
    *,
    call_id: str,
    contains_terms: tuple[str, ...],
    errors: list[str],
    warnings: list[str],
) -> list[_ImagegenRecord]:
    records: list[_ImagegenRecord] = []
    try:
        lines = session.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"session JSONL unreadable: {exc}")
        return records
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            warnings.append(f"line {line_number} skipped: invalid JSON ({exc})")
            continue
        for record in _iter_records(payload, line_number):
            if call_id and record.call_id != call_id:
                continue
            prompt_text = record.revised_prompt.casefold()
            if contains_terms and not all(term in prompt_text for term in contains_terms):
                continue
            records.append(record)
    return records


def _iter_records(value: object, line_number: int) -> Iterator[_ImagegenRecord]:
    if isinstance(value, dict):
        call_id = _string_value(value, "call_id") or _string_value(value, "id")
        result = _string_value(value, "result")
        if call_id.startswith("ig_") and result:
            revised_prompt = (
                _string_value(value, "revised_prompt")
                or _string_value(value, "prompt")
                or _string_value(value, "text")
            )
            yield _ImagegenRecord(
                call_id=call_id,
                result=result,
                revised_prompt=revised_prompt,
                line_number=line_number,
            )
        for child in value.values():
            yield from _iter_records(child, line_number)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_records(child, line_number)


def _string_value(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _decode_png(result: str) -> tuple[bytes, str]:
    payload = result.strip()
    if payload.startswith("data:image/"):
        if "," not in payload:
            return b"", "data URL image payload is malformed"
        payload = payload.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        return b"", f"image result is not valid base64: {exc}"
    if not image_bytes.startswith(PNG_SIGNATURE):
        return b"", "image result is not a PNG payload"
    return image_bytes, ""


def _report(
    *,
    ok: bool,
    status: str,
    session: Path,
    output_dir: Path,
    output_path: Path | None = None,
    call_id: str = "",
    source_line: int = 0,
    revised_prompt: str = "",
    sha256: str = "",
    byte_count: int = 0,
    errors: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> SessionImagegenResultReport:
    return SessionImagegenResultReport(
        ok=ok,
        status=status,
        session_path=str(session),
        output_dir=str(output_dir),
        output_path=str(output_path or ""),
        call_id=call_id,
        source_line=source_line,
        revised_prompt=revised_prompt,
        sha256=sha256,
        byte_count=byte_count,
        errors=errors,
        warnings=warnings,
    )


def _write_json(path: Path, report: SessionImagegenResultReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract a built-in imagegen PNG payload from a Codex session JSONL.")
    parser.add_argument("session")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--call-id", default="")
    parser.add_argument("--contains", action="append", default=[])
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = extract_session_imagegen_result(
        session_path=args.session,
        output_dir=args.output_dir,
        call_id=args.call_id,
        contains=tuple(args.contains),
        latest=args.latest,
        report_path=args.report or None,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
