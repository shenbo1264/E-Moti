from __future__ import annotations

"""Apply the verified E-Moti plugin/memory overlay to a full repository checkout.

The script is deliberately conservative:
- it never edits ``controller.py``;
- it switches the app to a drop-in subclass with one import replacement;
- every overwritten file receives a timestamped backup;
- current upstream files are checked by Git blob SHA when known;
- repeated execution is idempotent;
- ``--dry-run`` reports work without touching the target.
"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

OVERLAY_ROOT = Path(__file__).resolve().parents[1]

NEW_MODULES = (
    "companion_story_runtime.py",
    "emotional_memory.py",
    "emotional_memory_policy.py",
    "emotional_memory_reflection.py",
    "emotional_memory_retrieval.py",
    "emotional_memory_service.py",
    "focus_companion.py",
    "focus_companion_runtime.py",
    "focus_companion_qt.py",
    "legacy_memory_migration.py",
    "memory_album_controller.py",
    "memory_album_qt.py",
    "memory_album_view_model.py",
    "memory_integration_bridge.py",
    "plugin_api.py",
    "plugin_audit.py",
    "plugin_catalog_view_model.py",
    "plugin_center_app.py",
    "plugin_center_controller.py",
    "plugin_center_qt.py",
    "plugin_configuration.py",
    "plugin_enabled_controller.py",
    "plugin_health.py",
    "plugin_host.py",
    "plugin_journal.py",
    "plugin_manifest.py",
    "plugin_package.py",
    "plugin_provider_adapters.py",
    "plugin_runtime.py",
    "plugin_story_bridge.py",
    "plugin_subsystem.py",
    "release_security.py",
)

# These files already exist on the inspected E-Moti main branch. The overlay
# contains the reviewed character-copy tuning. Unknown upstream revisions are
# not overwritten unless --force is supplied.
TUNED_EXISTING = {
    "character_local_copy.py": "47256e582bfacee73dc43d2b5da1afe41a2fe2cf",
    "character_performance_profile.py": "546f3961f46cf64f9628109708c128f45430fe15",
    "companion_dialogue_policy.py": "0de368315a99eab1f928aac56f7a8dc70eb31a49",
}

EXPECTED_APP_BLOB = "33e0ce0318d487cc12b583c834c2199620c9bcdb"
EXPECTED_BUILD_BLOB = "939c89e3c8015576bb252494956f7fdd3169c88b"

TOOL_FILES = (
    "apply_and_verify_emoti_overlay.py",
    "apply_and_verify_emoti_overlay.ps1",
    "apply_emoti_plugin_overlay.py",
    "emoti_plugin_cli.py",
    "render_plugin_center_preview.py",
    "render_plugin_story_demo.py",
    "render_story_feature_previews.py",
    "run_integrated_story_smoke.py",
    "run_plugin_runtime_v2_smoke.py",
    "run_plugin_smoke.py",
    "run_overlay_contract_smoke.py",
    "run_private_provider_smoke.py",
    "scaffold_emoti_plugin.py",
    "validate_emoti_plugin.py",
)

DOC_FILES = (
    "APP_INTEGRATION_PATCH_MAP_CN.md",
    "COPY_STYLE_SEPARATION_CN.md",
    "DEEPSEEK_HARNESS_ADAPTATION_CN.md",
    "PLUGIN_ARCHITECTURE_CN.md",
    "PLUGIN_AUTHORING_GUIDE_CN.md",
    "PLUGIN_RUNTIME_REMAINING_WORK_CN.md",
    "PLUGIN_RUNTIME_V2_IMPLEMENTATION_CN.md",
    "PLUGIN_SECURITY_AND_BOUNDARIES_CN.md",
    "PLUGIN_VERIFICATION_REPORT_CN.md",
    "SECURITY_NOTICE_CN.md",
    "WINDOWS_INTEGRATION_QUICKSTART_CN.md",
    "emoti-plugin.schema.json",
)


@dataclass(slots=True)
class ApplyReport:
    target: str
    dry_run: bool
    copied: list[str] = field(default_factory=list)
    patched: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backups: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(item.startswith("BLOCKED:") for item in self.warnings)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "target": self.target,
            "dry_run": self.dry_run,
            "copied": self.copied,
            "patched": self.patched,
            "skipped": self.skipped,
            "warnings": self.warnings,
            "backups": self.backups,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply the verified E-Moti plugin overlay.")
    parser.add_argument("target", type=Path, help="Full E-Moti repository checkout")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Allow replacing unknown upstream revisions")
    parser.add_argument("--skip-copy-tuning", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    try:
        report = apply_overlay(
            args.target,
            dry_run=args.dry_run,
            force=args.force,
            apply_copy_tuning=not args.skip_copy_tuning,
        )
    except Exception as exc:
        payload = {"ok": False, "error_type": type(exc).__name__, "message": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    text = json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    return 0 if report.ok else 3


def apply_overlay(
    target: Path | str,
    *,
    dry_run: bool = False,
    force: bool = False,
    apply_copy_tuning: bool = True,
) -> ApplyReport:
    root = Path(target).resolve()
    _validate_target(root)
    report = ApplyReport(str(root), dry_run)
    backup_root = root / "artifacts" / "plugin-overlay-backup" / _timestamp()

    source_pkg = OVERLAY_ROOT / "src" / "guanghe_companion"
    target_pkg = root / "src" / "guanghe_companion"
    for name in NEW_MODULES:
        _copy_file(source_pkg / name, target_pkg / name, report, backup_root, dry_run=dry_run)

    if apply_copy_tuning:
        for name, expected_blob in TUNED_EXISTING.items():
            destination = target_pkg / name
            actual = _git_blob_sha(destination.read_bytes()) if destination.exists() else ""
            if actual and actual != expected_blob and not force:
                report.warnings.append(
                    f"BLOCKED: copy-tuning file changed upstream; review manually: {destination.relative_to(root)} ({actual})"
                )
                continue
            _copy_file(source_pkg / name, destination, report, backup_root, dry_run=dry_run)

    _copy_tree(OVERLAY_ROOT / "plugins", root / "plugins", report, backup_root, dry_run=dry_run)
    _copy_tree(
        OVERLAY_ROOT / "examples" / "plugin_starter_template",
        root / "examples" / "plugin_starter_template",
        report,
        backup_root,
        dry_run=dry_run,
    )
    _copy_tree(OVERLAY_ROOT / "public_config_template", root / "public_config_template", report, backup_root, dry_run=dry_run)

    for name in TOOL_FILES:
        _copy_file(OVERLAY_ROOT / "tools" / name, root / "tools" / name, report, backup_root, dry_run=dry_run)

    for name in DOC_FILES:
        _copy_file(OVERLAY_ROOT / "docs" / name, root / "docs" / name, report, backup_root, dry_run=dry_run)

    for source in sorted((OVERLAY_ROOT / "tests").glob("test_plugin*.py")):
        _copy_file(source, root / "tests" / source.name, report, backup_root, dry_run=dry_run)
    for source in sorted((OVERLAY_ROOT / "tests").glob("test_bundled*.py")):
        _copy_file(source, root / "tests" / source.name, report, backup_root, dry_run=dry_run)
    for name in (
        "test_emotional_memory.py",
        "test_emotional_memory_policy.py",
        "test_emotional_memory_service.py",
        "test_focus_companion.py",
        "test_focus_companion_runtime.py",
        "test_integrated_story_runtime.py",
        "test_integrated_story_smoke_tool.py",
        "test_memory_album_controller.py",
        "test_memory_album_qt_contract.py",
        "test_focus_companion_qt_contract.py",
        "test_apply_emoti_plugin_overlay.py",
        "test_apply_and_verify_emoti_overlay.py",
        "test_render_plugin_center_preview.py",
        "test_render_plugin_story_demo.py",
        "test_render_story_feature_previews.py",
        "test_overlay_contract_smoke_tool.py",
        "test_private_provider_smoke_tool.py",
        "test_release_security_cli.py",
        "test_qt_optional_contracts.py",
        "test_render_tools.py",
        "test_xingxi_product_copy.py",
    ):
        source = OVERLAY_ROOT / "tests" / name
        if source.exists():
            _copy_file(source, root / "tests" / name, report, backup_root, dry_run=dry_run)

    launcher = root / "packaging" / "launch_plugin_center.py"
    _write_text(
        launcher,
        "from guanghe_companion.plugin_center_app import main\n\nif __name__ == '__main__':\n    raise SystemExit(main())\n",
        report,
        backup_root,
        dry_run=dry_run,
    )

    _patch_app_import(root / "src" / "guanghe_companion" / "app.py", report, backup_root, dry_run=dry_run, force=force)
    _patch_build_script(root / "tools" / "build_windows_app.ps1", report, backup_root, dry_run=dry_run, force=force)
    _append_gitignore(root / ".gitignore", report, backup_root, dry_run=dry_run)
    return report


def _validate_target(root: Path) -> None:
    required = (
        root / "pyproject.toml",
        root / "src" / "guanghe_companion" / "controller.py",
        root / "src" / "guanghe_companion" / "app.py",
        root / "tools" / "build_windows_app.ps1",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("target is not a complete E-Moti checkout; missing: " + ", ".join(missing))


def _patch_app_import(path: Path, report: ApplyReport, backup_root: Path, *, dry_run: bool, force: bool) -> None:
    content = path.read_text(encoding="utf-8")
    actual = _git_blob_sha(content.encode("utf-8"))
    if actual != EXPECTED_APP_BLOB and not force:
        report.warnings.append(
            f"app.py differs from inspected main ({actual}); anchor patches applied conservatively"
        )

    replacements = (
        (
            "from .controller import CompanionController",
            "from .plugin_enabled_controller import PluginEnabledCompanionController as CompanionController\n"
            "from .focus_companion_qt import create_focus_companion_widget\n"
            "from .memory_album_qt import create_memory_album_widget\n"
            "from .plugin_center_qt import create_plugin_center_widget",
            "controller + plugin center imports",
        ),
        (
            "        self.asr_service = ASRService()\n        self._asr_recording = False",
            "        self.asr_service = ASRService()\n"
            "        bind_plugin_capabilities = getattr(self.controller, \"bind_plugin_capabilities\", None)\n"
            "        if callable(bind_plugin_capabilities):\n"
            "            bind_plugin_capabilities(\n"
            "                tts_manager=self.tts_manager,\n"
            "                asr_transcriber=self.asr_service,\n"
            "                screen_observer=self.screen_observation_service,\n"
            "                web_search_service=self.web_search_service,\n"
            "            )\n"
            "        self._asr_recording = False",
            "app capability seam binding",
        ),
        (
            "        voice_layout.addStretch(1)\n        self.content_stack.addWidget(voice_page)\n        self._load_capability_settings_into_ui()",
            "        voice_layout.addStretch(1)\n"
            "        self.content_stack.addWidget(voice_page)\n\n"
            "        memory_album_controller = getattr(self.controller, \"memory_album_controller\", None)\n"
            "        if memory_album_controller is not None:\n"
            "            self.memory_album_page = create_memory_album_widget(\n"
            "                memory_album_controller,\n"
            "                on_changed=lambda: self._apply_snapshot(self.controller.get_snapshot()),\n"
            "            )\n"
            "        else:\n"
            "            self.memory_album_page = QWidget()\n"
            "            memory_album_layout = QVBoxLayout(self.memory_album_page)\n"
            "            memory_album_layout.addWidget(QLabel(\"当前控制器未启用情感记忆。\"))\n"
            "            memory_album_layout.addStretch(1)\n"
            "        self.content_stack.addWidget(self.memory_album_page)\n\n"
            "        if hasattr(self.controller, \"get_focus_companion_view_model\"):\n"
            "            self.focus_companion_page = create_focus_companion_widget(\n"
            "                self.controller,\n"
            "                on_changed=lambda: self._apply_snapshot(self.controller.get_snapshot()),\n"
            "            )\n"
            "        else:\n"
            "            self.focus_companion_page = QWidget()\n"
            "            focus_companion_layout = QVBoxLayout(self.focus_companion_page)\n"
            "            focus_companion_layout.addWidget(QLabel(\"当前控制器未启用探头时刻。\"))\n"
            "            focus_companion_layout.addStretch(1)\n"
            "        self.content_stack.addWidget(self.focus_companion_page)\n\n"
            "        plugin_center_controller = getattr(self.controller, \"plugin_center\", None)\n"
            "        if plugin_center_controller is not None:\n"
            "            self.plugin_center_page = create_plugin_center_widget(\n"
            "                plugin_center_controller,\n"
            "                on_changed=lambda: self._apply_snapshot(self.controller.get_snapshot()),\n"
            "            )\n"
            "        else:\n"
            "            self.plugin_center_page = QWidget()\n"
            "            plugin_center_layout = QVBoxLayout(self.plugin_center_page)\n"
            "            plugin_center_layout.addWidget(QLabel(\"当前控制器未启用插件运行时。\"))\n"
            "            plugin_center_layout.addStretch(1)\n"
            "        self.content_stack.addWidget(self.plugin_center_page)\n"
            "        self._load_capability_settings_into_ui()",
            "memory album, focus companion, and plugin center pages",
        ),
        (
            "for index, label in enumerate((\"总览\", \"互动\", \"背包\", \"角色库\", \"感知与搜索\", \"隐私\", \"LLM表达\", \"表达规则\", \"语音\")):",
            "for index, label in enumerate((\"总览\", \"互动\", \"背包\", \"角色库\", \"感知与搜索\", \"隐私\", \"LLM表达\", \"表达规则\", \"语音\", \"回忆\", \"探头时刻\", \"插件\")):",
            "memory, focus, and plugin navigation entries",
        ),
        (
            "    def _build_actions_card(self) -> QGroupBox:\n"
            "        box = QGroupBox(\"互动动作\")\n"
            "        layout = QHBoxLayout(box)\n"
            "        for action_id in (\"touch\", \"soothe\", \"rest\", \"study\", \"play\", \"drag\"):\n"
            "            button = QPushButton(action_id)\n"
            "            button.clicked.connect(lambda checked=False, current=action_id: self._handle_action(current))\n"
            "            button.setMinimumHeight(42)\n"
            "            self.action_buttons[action_id] = button\n"
            "            layout.addWidget(button)\n"
            "        return box\n",
            "    def _build_actions_card(self) -> QGroupBox:\n"
            "        box = QGroupBox(\"互动动作\")\n"
            "        self.actions_layout = QGridLayout(box)\n"
            "        self._sync_action_buttons(self.controller.get_snapshot().get(\"actions\", ()))\n"
            "        return box\n\n"
            "    def _sync_action_buttons(self, entries: object) -> None:\n"
            "        rows = [entry for entry in entries if isinstance(entry, dict)]\n"
            "        expected_ids = [str(entry.get(\"action_id\", \"\")) for entry in rows if entry.get(\"action_id\")]\n"
            "        for action_id in tuple(self.action_buttons):\n"
            "            if action_id in expected_ids:\n"
            "                continue\n"
            "            button = self.action_buttons.pop(action_id)\n"
            "            self.actions_layout.removeWidget(button)\n"
            "            button.deleteLater()\n"
            "        for index, entry in enumerate(rows):\n"
            "            action_id = str(entry.get(\"action_id\", \"\"))\n"
            "            if not action_id:\n"
            "                continue\n"
            "            button = self.action_buttons.get(action_id)\n"
            "            if button is None:\n"
            "                button = QPushButton(action_id)\n"
            "                button.clicked.connect(\n"
            "                    lambda checked=False, current=action_id: self._handle_action(current)\n"
            "                )\n"
            "                button.setMinimumHeight(42)\n"
            "                self.action_buttons[action_id] = button\n"
            "            self.actions_layout.removeWidget(button)\n"
            "            self.actions_layout.addWidget(button, index // 3, index % 3)\n"
            "            button.setText(str(entry.get(\"label\", action_id)))\n"
            "            button.setEnabled(bool(entry.get(\"enabled\", True)))\n"
            "            description = str(entry.get(\"description\", \"\"))\n"
            "            if description:\n"
            "                button.setToolTip(description)\n",
            "dynamic built-in and plugin action buttons",
        ),
        (
            "        actions = {entry[\"action_id\"]: entry for entry in snapshot[\"actions\"]}\n"
            "        for action_id, button in self.action_buttons.items():\n"
            "            entry = actions[action_id]\n"
            "            button.setText(str(entry[\"label\"]))\n"
            "            button.setEnabled(bool(entry[\"enabled\"]))",
            "        self._sync_action_buttons(snapshot[\"actions\"])",
            "snapshot action synchronization",
        ),
    )

    next_content = content
    applied: list[str] = []
    for old, replacement, label in replacements:
        if replacement in next_content:
            continue
        if old not in next_content:
            report.warnings.append(f"BLOCKED: app.py integration anchor missing: {label}")
            return
        next_content = next_content.replace(old, replacement, 1)
        applied.append(label)

    if not applied:
        report.skipped.append("app.py: plugin integration already present")
        return
    _write_text(
        path,
        next_content,
        report,
        backup_root,
        dry_run=dry_run,
        label="app.py: " + ", ".join(applied),
    )


def _patch_build_script(path: Path, report: ApplyReport, backup_root: Path, *, dry_run: bool, force: bool) -> None:
    content = path.read_text(encoding="utf-8")
    marker = "# E-Moti plugin runtime integration"
    if marker in content:
        report.skipped.append("build_windows_app.ps1: plugin data already included")
        return
    actual = _git_blob_sha(content.encode("utf-8"))
    if actual != EXPECTED_BUILD_BLOB and not force:
        report.warnings.append(
            f"build_windows_app.ps1 differs from inspected main ({actual}); anchor patch applied conservatively"
        )
    replacements = (
        (
            '$AssetsPath = Join-Path $RepoRoot "assets"\n',
            '$AssetsPath = Join-Path $RepoRoot "assets"\n$PluginsPath = Join-Path $RepoRoot "plugins"  # E-Moti plugin runtime integration\n',
        ),
        (
            '$AddVoiceServices = "$RuntimeVoiceServicesDir;voice_services"\n',
            '$AddVoiceServices = "$RuntimeVoiceServicesDir;voice_services"\n$AddPlugins = "$PluginsPath;plugins"\n',
        ),
        (
            '    "--add-data", $AddVoiceServices,\n',
            '    "--add-data", $AddVoiceServices,\n    "--add-data", $AddPlugins,\n',
        ),
    )
    next_content = content
    for old, new in replacements:
        if old not in next_content:
            report.warnings.append(f"BLOCKED: build script anchor missing: {old.strip()}")
            return
        next_content = next_content.replace(old, new, 1)
    _write_text(path, next_content, report, backup_root, dry_run=dry_run, label="Windows plugin packaging")


def _append_gitignore(path: Path, report: ApplyReport, backup_root: Path, *, dry_run: bool) -> None:
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    block = "\n# E-Moti local plugin runtime\ndata/plugins/\n.codex_private/\n"
    if "# E-Moti local plugin runtime" in content:
        report.skipped.append(".gitignore: plugin runtime rules already present")
        return
    _write_text(path, content.rstrip() + block, report, backup_root, dry_run=dry_run, label=".gitignore plugin runtime")


def _copy_tree(source: Path, destination: Path, report: ApplyReport, backup_root: Path, *, dry_run: bool) -> None:
    if not source.is_dir():
        return
    for path in sorted(source.rglob("*")):
        if path.is_dir() or any(part in {"__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        _copy_file(path, destination / path.relative_to(source), report, backup_root, dry_run=dry_run)


def _copy_file(source: Path, destination: Path, report: ApplyReport, backup_root: Path, *, dry_run: bool) -> None:
    if not source.is_file():
        report.warnings.append(f"BLOCKED: overlay file missing: {source}")
        return
    data = source.read_bytes()
    if destination.exists() and destination.read_bytes() == data:
        report.skipped.append(str(destination))
        return
    if not dry_run:
        _backup(destination, backup_root, report)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".emoti-plugin.tmp")
        temporary.write_bytes(data)
        temporary.replace(destination)
    report.copied.append(str(destination))


def _write_text(
    destination: Path,
    content: str,
    report: ApplyReport,
    backup_root: Path,
    *,
    dry_run: bool,
    label: str = "",
) -> None:
    data = content.encode("utf-8")
    if destination.exists() and destination.read_bytes() == data:
        report.skipped.append(str(destination))
        return
    if not dry_run:
        _backup(destination, backup_root, report)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".emoti-plugin.tmp")
        temporary.write_bytes(data)
        temporary.replace(destination)
    report.patched.append(label or str(destination))


def _backup(destination: Path, backup_root: Path, report: ApplyReport) -> None:
    if not destination.exists():
        return
    relative = destination.anchor and Path(destination.name) or destination
    # Preserve repository-relative layout when possible.
    try:
        repo_root = Path(report.target)
        relative = destination.resolve().relative_to(repo_root)
    except ValueError:
        relative = Path(destination.name)
    target = backup_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(destination, target)
    report.backups.append(str(target))


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
