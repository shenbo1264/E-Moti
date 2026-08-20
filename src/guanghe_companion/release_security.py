from __future__ import annotations

"""Recursive secret guard for public E-Moti packages and plugin archives."""

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

SECRET_KEY_NAMES = frozenset(
    {
        "api_key", "apikey", "vision_api_key", "token", "access_token",
        "refresh_token", "authorization", "secret", "client_secret", "password",
    }
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\btp-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE),
)
PLACEHOLDERS = frozenset({"", "local", "changeme", "your_api_key", "<api-key>", "${API_KEY}", "***", "[redacted]"})
TEXT_SUFFIXES = frozenset({".json", ".md", ".txt", ".py", ".ps1", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".html", ".js", ".ts"})
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_ZIP_ENTRIES = 5000


@dataclass(frozen=True, slots=True)
class SecretFinding:
    path: str
    field: str
    finding_type: str = "secret"

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "field": self.field, "finding_type": self.finding_type}


@dataclass(frozen=True, slots=True)
class SecretScanReport:
    findings: tuple[SecretFinding, ...]
    scanned_files: int = 0
    skipped_files: int = 0

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "ok": self.ok,
            "scanned_files": self.scanned_files,
            "skipped_files": self.skipped_files,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def scan_json_payload(payload: object, *, path: str = "") -> SecretScanReport:
    findings: list[SecretFinding] = []

    def walk(value: object, field_path: str) -> None:
        if isinstance(value, Mapping):
            for raw_key, child in value.items():
                key = str(raw_key)
                next_path = f"{field_path}.{key}" if field_path else key
                if _normalized_key(key) in SECRET_KEY_NAMES and _looks_live_secret(child):
                    findings.append(SecretFinding(path, next_path, "credential-field"))
                walk(child, next_path)
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                walk(child, f"{field_path}[{index}]")
        elif isinstance(value, str):
            if any(pattern.search(value) for pattern in SECRET_PATTERNS):
                findings.append(SecretFinding(path, field_path or "<text>", "token-pattern"))

    walk(payload, "")
    return SecretScanReport(_unique(findings), scanned_files=1)


def scan_json_file(path: Path | str) -> SecretScanReport:
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return SecretScanReport((), scanned_files=0, skipped_files=1)
    return scan_json_payload(payload, path=str(target))


def scan_path(path: Path | str) -> SecretScanReport:
    target = Path(path)
    if target.is_dir():
        findings: list[SecretFinding] = []
        scanned = skipped = 0
        for file in sorted(target.rglob("*")):
            if not file.is_file() or file.is_symlink():
                continue
            report = _scan_regular_file(file, display=str(file.relative_to(target)))
            findings.extend(report.findings); scanned += report.scanned_files; skipped += report.skipped_files
        return SecretScanReport(_unique(findings), scanned, skipped)
    if target.is_file() and target.suffix.lower() == ".zip":
        return scan_zip(target)
    if target.is_file():
        return _scan_regular_file(target, display=str(target))
    return SecretScanReport((), 0, 1)


def scan_zip(path: Path | str) -> SecretScanReport:
    target = Path(path)
    findings: list[SecretFinding] = []
    scanned = skipped = 0
    try:
        with zipfile.ZipFile(target) as archive:
            for index, info in enumerate(archive.infolist()):
                if index >= MAX_ZIP_ENTRIES:
                    skipped += len(archive.infolist()) - index
                    break
                if info.is_dir():
                    continue
                pure = PurePosixPath(info.filename.replace("\\", "/"))
                if pure.is_absolute() or ".." in pure.parts:
                    findings.append(SecretFinding(info.filename, "<path>", "unsafe-zip-path")); continue
                if pure.suffix.lower() not in TEXT_SUFFIXES or info.file_size > MAX_TEXT_BYTES:
                    skipped += 1; continue
                try:
                    raw = archive.read(info)
                    text = raw.decode("utf-8-sig")
                except (OSError, UnicodeDecodeError, RuntimeError):
                    skipped += 1; continue
                report = _scan_text(text, path=info.filename, suffix=pure.suffix.lower())
                findings.extend(report.findings); scanned += 1
    except (OSError, zipfile.BadZipFile):
        return SecretScanReport((), 0, 1)
    return SecretScanReport(_unique(findings), scanned, skipped)


def redact_json_payload(payload: object) -> object:
    if isinstance(payload, Mapping):
        result: dict[str, object] = {}
        for raw_key, child in payload.items():
            key = str(raw_key)
            result[key] = "" if _normalized_key(key) in SECRET_KEY_NAMES else redact_json_payload(child)
        return result
    if isinstance(payload, list):
        return [redact_json_payload(item) for item in payload]
    if isinstance(payload, str) and any(pattern.search(payload) for pattern in SECRET_PATTERNS):
        return ""
    return payload


def redact_json_file(source: Path | str, destination: Path | str) -> None:
    payload = json.loads(Path(source).read_text(encoding="utf-8-sig"))
    target = Path(destination); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(redact_json_payload(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _scan_regular_file(path: Path, *, display: str) -> SecretScanReport:
    if path.suffix.lower() == ".zip":
        return scan_zip(path)
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return SecretScanReport((), 0, 1)
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return SecretScanReport((), 0, 1)
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return SecretScanReport((), 0, 1)
    return _scan_text(text, path=display, suffix=path.suffix.lower())


def _scan_text(text: str, *, path: str, suffix: str) -> SecretScanReport:
    if suffix == ".json":
        try:
            return scan_json_payload(json.loads(text), path=path)
        except json.JSONDecodeError:
            pass
    findings: list[SecretFinding] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(SecretFinding(path, "<text>", "token-pattern"))
    # Config-style assignments, without preserving the value.
    assignment = re.compile(r"(?im)^\s*([A-Za-z0-9_.-]*(?:api[_-]?key|token|password|secret|authorization)[A-Za-z0-9_.-]*)\s*[:=]\s*['\"]?([^\s'\"#]{12,})")
    for match in assignment.finditer(text):
        if _looks_live_secret(match.group(2)):
            findings.append(SecretFinding(path, match.group(1), "credential-assignment"))
    return SecretScanReport(_unique(findings), scanned_files=1)


def _looks_live_secret(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    lowered = text.lower()
    if lowered in PLACEHOLDERS or len(text) < 12:
        return False
    if lowered.startswith(("list[", "dict[", "tuple[", "set[", "mapping[", "sequence[", "optional[")):
        return False
    if text[:1] in {"[", "{", "("}:
        return False
    return True


def _normalized_key(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _unique(findings: list[SecretFinding]) -> tuple[SecretFinding, ...]:
    return tuple({(row.path, row.field, row.finding_type): row for row in findings}.values())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan a file, directory, or ZIP for public-release secrets.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report = scan_path(args.path)
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
    print(payload)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    return 0 if report.ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
