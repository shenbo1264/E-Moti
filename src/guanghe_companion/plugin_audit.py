from __future__ import annotations

"""Static, best-effort audit for local E-Moti plugins.

This reduces accidental risk. Plugins still run in-process; this is not an OS sandbox.
"""

import ast
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable

from .plugin_api import PluginPermission
from .plugin_manifest import PluginCandidate

_RISK_IMPORTS = {
    "subprocess": PluginPermission.FILESYSTEM_EXTERNAL,
    "socket": PluginPermission.NETWORK_HTTP,
    "requests": PluginPermission.NETWORK_HTTP,
    "httpx": PluginPermission.NETWORK_HTTP,
    "urllib": PluginPermission.NETWORK_HTTP,
    "ctypes": PluginPermission.FILESYSTEM_EXTERNAL,
    "win32api": PluginPermission.FILESYSTEM_EXTERNAL,
    "win32con": PluginPermission.FILESYSTEM_EXTERNAL,
    "keyboard": PluginPermission.FILESYSTEM_EXTERNAL,
    "pynput": PluginPermission.FILESYSTEM_EXTERNAL,
}
_RISK_CALLS = {"eval", "exec", "compile", "__import__"}


@dataclass(frozen=True, slots=True)
class AuditFinding:
    path: str
    line: int
    code: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "line": self.line, "code": self.code, "severity": self.severity, "message": self.message}


@dataclass(frozen=True, slots=True)
class PluginAuditReport:
    plugin_id: str
    ok: bool
    risk_level: str
    scanned_files: int
    declared_permissions: tuple[str, ...]
    detected_permissions: tuple[str, ...]
    findings: tuple[AuditFinding, ...]
    digest: str
    sandbox_notice: str = (
        "Plugins run in-process. Permission checks protect host APIs, while static audit reduces direct-bypass risk; "
        "neither mechanism is an operating-system sandbox."
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "ok": self.ok,
            "risk_level": self.risk_level,
            "scanned_files": self.scanned_files,
            "declared_permissions": list(self.declared_permissions),
            "detected_permissions": list(self.detected_permissions),
            "findings": [row.to_dict() for row in self.findings],
            "digest": self.digest,
            "sandbox_notice": self.sandbox_notice,
        }


def audit_plugin(candidate: PluginCandidate, *, max_files: int = 200, max_file_bytes: int = 512 * 1024) -> PluginAuditReport:
    findings: list[AuditFinding] = []
    detected: set[PluginPermission] = set()
    digest = hashlib.sha256()
    files = [path for path in sorted(candidate.root.rglob("*")) if path.is_file() and path.suffix.lower() in {".py", ".json", ".md", ".txt"}]
    for path in files[:max_files]:
        relative = path.relative_to(candidate.root).as_posix()
        raw = path.read_bytes()
        digest.update(relative.encode("utf-8")); digest.update(b"\0"); digest.update(raw); digest.update(b"\0")
        if len(raw) > max_file_bytes:
            findings.append(AuditFinding(relative, 0, "file-too-large", "high", f"text file exceeds {max_file_bytes} bytes"))
            continue
        if path.suffix.lower() != ".py":
            continue
        try:
            text = raw.decode("utf-8-sig")
            tree = ast.parse(text, filename=relative)
        except (UnicodeDecodeError, SyntaxError) as exc:
            findings.append(AuditFinding(relative, getattr(exc, "lineno", 0) or 0, "invalid-python", "high", str(exc)[:300]))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [str(node.module or "").split(".", 1)[0]]
            else:
                names = []
            for name in names:
                permission = _RISK_IMPORTS.get(name)
                if permission is not None:
                    detected.add(permission)
                    findings.append(AuditFinding(relative, getattr(node, "lineno", 0), f"import-{name}", "medium", f"imports {name}; review direct host bypass risk"))
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else ""
                if name in _RISK_CALLS:
                    findings.append(AuditFinding(relative, getattr(node, "lineno", 0), f"call-{name}", "high", f"uses dynamic execution primitive {name}"))
    if len(files) > max_files:
        findings.append(AuditFinding("<plugin>", 0, "too-many-files", "high", f"plugin has more than {max_files} auditable files"))
    declared = set(candidate.manifest.permissions)
    for permission in sorted(detected - declared, key=lambda p: p.value):
        findings.append(AuditFinding("<manifest>", 0, "permission-not-declared", "high", f"source suggests {permission.value}, but manifest does not declare it"))
    high = any(row.severity == "high" for row in findings)
    medium = any(row.severity == "medium" for row in findings)
    risk = "high" if high else ("medium" if medium else "low")
    return PluginAuditReport(
        plugin_id=candidate.manifest.plugin_id,
        ok=not high,
        risk_level=risk,
        scanned_files=min(len(files), max_files),
        declared_permissions=tuple(sorted(p.value for p in declared)),
        detected_permissions=tuple(sorted(p.value for p in detected)),
        findings=tuple(findings),
        digest=digest.hexdigest(),
    )
