from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from apply_emoti_plugin_overlay import apply_overlay


def _synthetic_repo(root: Path) -> None:
    (root/'src/guanghe_companion').mkdir(parents=True)
    (root/'tools').mkdir(); (root/'tests').mkdir(); (root/'packaging').mkdir()
    (root/'pyproject.toml').write_text('[project]\nname="emoti-contract-fixture"\nversion="0.0.0"\n',encoding='utf-8')
    (root/'.gitignore').write_text('# fixture\n',encoding='utf-8')
    (root/'src/guanghe_companion/controller.py').write_text('class CompanionController:\n    pass\n',encoding='utf-8')
    (root/'src/guanghe_companion/character_local_copy.py').write_text('# fixture\n',encoding='utf-8')
    (root/'src/guanghe_companion/character_performance_profile.py').write_text('# fixture\n',encoding='utf-8')
    (root/'src/guanghe_companion/companion_dialogue_policy.py').write_text('# fixture\n',encoding='utf-8')
    app='''from .controller import CompanionController
class CompanionWindow:
    def __init__(self):
        self.controller = CompanionController()
        self.tts_manager = object()
        self.asr_service = ASRService()
        self._asr_recording = False
    def _build_ui(self):
        voice_page = QWidget()
        voice_layout = QVBoxLayout(voice_page)
        voice_layout.addStretch(1)
        self.content_stack.addWidget(voice_page)
        self._load_capability_settings_into_ui()
    def _build_sidebar_card(self):
        for index, label in enumerate(("总览", "互动", "背包", "角色库", "感知与搜索", "隐私", "LLM表达", "表达规则", "语音")):
            pass
    def _build_actions_card(self) -> QGroupBox:
        box = QGroupBox("互动动作")
        layout = QHBoxLayout(box)
        for action_id in ("touch", "soothe", "rest", "study", "play", "drag"):
            button = QPushButton(action_id)
            button.clicked.connect(lambda checked=False, current=action_id: self._handle_action(current))
            button.setMinimumHeight(42)
            self.action_buttons[action_id] = button
            layout.addWidget(button)
        return box
    def _apply_snapshot(self, snapshot):
        actions = {entry["action_id"]: entry for entry in snapshot["actions"]}
        for action_id, button in self.action_buttons.items():
            entry = actions[action_id]
            button.setText(str(entry["label"]))
            button.setEnabled(bool(entry["enabled"]))
'''
    (root/'src/guanghe_companion/app.py').write_text(app,encoding='utf-8')
    build='''$AssetsPath = Join-Path $RepoRoot "assets"
$AddVoiceServices = "$RuntimeVoiceServicesDir;voice_services"
$Arguments = @(
    "--add-data", $AddVoiceServices,
    "packaging\\launch_control_panel.py"
)
'''
    (root/'tools/build_windows_app.ps1').write_text(build,encoding='utf-8')


def main(argv=None):
    parser=argparse.ArgumentParser(); parser.add_argument('--report',type=Path,required=True); args=parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix='emoti-overlay-contract-') as tmp:
        root=Path(tmp)/'E-Moti'; _synthetic_repo(root)
        dry=apply_overlay(root,dry_run=True,force=True,apply_copy_tuning=False)
        no_write=not (root/'src/guanghe_companion/plugin_runtime.py').exists()
        first=apply_overlay(root,force=True,apply_copy_tuning=False)
        second=apply_overlay(root,force=True,apply_copy_tuning=False)
        app=(root/'src/guanghe_companion/app.py').read_text(encoding='utf-8')
        build=(root/'tools/build_windows_app.ps1').read_text(encoding='utf-8')
        checks={
            'dry_run_ok':dry.ok,'dry_run_did_not_write_runtime':no_write,'first_apply_ok':first.ok,'second_apply_ok':second.ok,
            'idempotent_second_apply':not second.copied and not second.patched,
            'plugin_controller_import':'PluginEnabledCompanionController as CompanionController' in app,
            'memory_page':'create_memory_album_widget' in app,'focus_page':'create_focus_companion_widget' in app,
            'plugin_center_page':'create_plugin_center_widget' in app,'dynamic_actions':'_sync_action_buttons' in app,
            'host_capability_binding':'bind_plugin_capabilities' in app,'plugins_in_windows_build':'$AddPlugins' in build,
            'starter_template_copied':(root/'examples/plugin_starter_template/plugin/emoti-plugin.json').is_file(),
            'one_click_runner_copied':(root/'tools/apply_and_verify_emoti_overlay.py').is_file(),
            'new_docs_copied':(root/'docs/WINDOWS_INTEGRATION_QUICKSTART_CN.md').is_file(),
        }
        payload={'ok':all(checks.values()),'checks':checks,'dry_run':dry.to_dict(),'first_apply':first.to_dict(),'second_apply':second.to_dict()}
    args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(payload,ensure_ascii=False,indent=2)); return 0 if payload['ok'] else 1
if __name__=='__main__': raise SystemExit(main())
