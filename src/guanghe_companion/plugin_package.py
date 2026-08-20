from __future__ import annotations

"""Safe packaging, installation and removal for local E-Moti plugins."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

from .plugin_audit import PluginAuditReport, audit_plugin
from .plugin_manifest import PluginCandidate, PluginManifestError, load_plugin_manifest

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_EXTRACTED_BYTES = 64 * 1024 * 1024
MAX_FILES = 500


@dataclass(frozen=True, slots=True)
class PluginPackageReport:
    plugin_id: str
    version: str
    output_path: str
    archive_sha256: str
    file_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "version": self.version,
            "output_path": self.output_path,
            "archive_sha256": self.archive_sha256,
            "file_count": self.file_count,
        }


@dataclass(frozen=True, slots=True)
class PluginInstallResult:
    ok: bool
    operation: str
    plugin_id: str = ""
    message: str = ""
    payload: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "operation": self.operation,
            "plugin_id": self.plugin_id,
            "message": self.message,
            "payload": dict(self.payload or {}),
        }


def build_plugin_archive(plugin_root: Path | str, output_path: Path | str) -> PluginPackageReport:
    root = Path(plugin_root).resolve()
    manifest = load_plugin_manifest(root / "emoti-plugin.json")
    files = _package_files(root)
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
    temporary.replace(output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return PluginPackageReport(manifest.plugin_id, manifest.version, str(output), digest, len(files))


class PluginPackageManager:
    def __init__(self, installed_root: Path | str) -> None:
        self.installed_root = Path(installed_root)

    def install(self, archive_path: Path | str, *, allow_update: bool = True) -> PluginInstallResult:
        archive_path = Path(archive_path).resolve()
        if not archive_path.is_file():
            return PluginInstallResult(False, "install", message="插件包不存在")
        if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
            return PluginInstallResult(False, "install", message="插件包超过大小限制")
        try:
            with tempfile.TemporaryDirectory(prefix="emoti-plugin-install-") as tmp:
                staging = Path(tmp) / "plugin"
                staging.mkdir(parents=True)
                _safe_extract(archive_path, staging)
                candidate = _candidate_from_staging(staging)
                audit = audit_plugin(candidate)
                if not audit.ok:
                    return PluginInstallResult(
                        False,
                        "install",
                        candidate.manifest.plugin_id,
                        "插件静态审计未通过",
                        {"audit": audit.to_dict()},
                    )
                target = self.installed_root / candidate.manifest.plugin_id
                updated = target.exists()
                if updated and not allow_update:
                    return PluginInstallResult(False, "install", candidate.manifest.plugin_id, "插件已安装")
                self.installed_root.mkdir(parents=True, exist_ok=True)
                temporary_target = self.installed_root / f".{candidate.manifest.plugin_id}.incoming"
                shutil.rmtree(temporary_target, ignore_errors=True)
                shutil.copytree(candidate.root, temporary_target)
                backup = self.installed_root / f".{candidate.manifest.plugin_id}.backup"
                shutil.rmtree(backup, ignore_errors=True)
                if target.exists():
                    target.replace(backup)
                temporary_target.replace(target)
                shutil.rmtree(backup, ignore_errors=True)
                digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
                return PluginInstallResult(
                    True,
                    "install",
                    candidate.manifest.plugin_id,
                    f"已安装 {candidate.manifest.plugin_id} {candidate.manifest.version}",
                    {
                        "plugin_id": candidate.manifest.plugin_id,
                        "version": candidate.manifest.version,
                        "updated": updated,
                        "installed_path": str(target),
                        "archive_sha256": digest,
                        "audit": audit.to_dict(),
                    },
                )
        except (OSError, ValueError, zipfile.BadZipFile, PluginManifestError) as exc:
            return PluginInstallResult(False, "install", message=f"插件安装失败：{exc}")

    def uninstall(self, plugin_id: str) -> PluginInstallResult:
        target = (self.installed_root / plugin_id).resolve()
        root = self.installed_root.resolve()
        if root != target and root not in target.parents:
            return PluginInstallResult(False, "uninstall", plugin_id, "插件路径无效")
        if not target.exists():
            return PluginInstallResult(False, "uninstall", plugin_id, "插件未安装")
        shutil.rmtree(target)
        return PluginInstallResult(True, "uninstall", plugin_id, f"已卸载 {plugin_id}")


def _candidate_from_staging(staging: Path) -> PluginCandidate:
    manifests = list(staging.rglob("emoti-plugin.json"))
    if len(manifests) != 1:
        raise PluginManifestError("插件包必须且只能包含一个 emoti-plugin.json")
    manifest_path = manifests[0]
    manifest = load_plugin_manifest(manifest_path)
    return PluginCandidate(manifest_path.parent.resolve(), manifest_path.resolve(), manifest)


def _safe_extract(archive_path: Path, staging: Path) -> None:
    total = 0
    count = 0
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            count += 1
            total += max(0, info.file_size)
            if count > MAX_FILES or total > MAX_EXTRACTED_BYTES:
                raise ValueError("插件包解压规模超过限制")
            pure = PurePosixPath(info.filename.replace("\\", "/"))
            if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                raise ValueError(f"插件包包含不安全路径：{info.filename}")
            destination = (staging / Path(*pure.parts)).resolve()
            if staging.resolve() not in destination.parents:
                raise ValueError(f"插件包路径逃逸：{info.filename}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)


def _package_files(root: Path) -> tuple[Path, ...]:
    rows: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(part.startswith(".") or part in {"__pycache__", "data", "artifacts"} for part in relative.parts):
            continue
        rows.append(path)
    if len(rows) > MAX_FILES:
        raise ValueError("插件文件数量超过限制")
    total = sum(path.stat().st_size for path in rows)
    if total > MAX_EXTRACTED_BYTES:
        raise ValueError("插件内容超过大小限制")
    return tuple(rows)
