import shutil
from pathlib import Path
from guanghe_companion.plugin_center_controller import PluginCenterController
from guanghe_companion.plugin_subsystem import PluginSubsystem


def center(tmp_path: Path):
    app=tmp_path/'app'; app.mkdir(); shutil.copytree(Path(__file__).resolve().parents[1]/'plugins',app/'plugins')
    subsystem=PluginSubsystem(application_root=app,user_data_root=tmp_path/'user'); subsystem.start()
    return subsystem,PluginCenterController(subsystem,character_id_provider=lambda:'xingxi_pixel_pet',state_snapshot_provider=lambda:{'mood':80})


def test_center_snapshot_has_audit_health_and_settings(tmp_path: Path):
    subsystem,c=center(tmp_path); snap=c.snapshot(); row=next(x for x in snap['plugins'] if x['plugin_id']=='emoti.bundled.stargazing')
    assert row['audit_ok'] and row['risk_level']=='low' and isinstance(row['effective_settings'],dict) and not row['quarantined']


def test_center_enable_disable_and_panel_model(tmp_path: Path):
    subsystem,c=center(tmp_path); assert c.set_enabled('emoti.bundled.stargazing',True).ok
    panels=c.panel_models(); assert any(row['panel_id']=='stargazing.panel' for row in panels)
    assert c.set_enabled('emoti.bundled.stargazing',False).ok


def test_center_settings_reload_plugin(tmp_path: Path):
    subsystem,c=center(tmp_path); c.set_enabled('emoti.bundled.stargazing',True)
    result=c.set_settings('emoti.bundled.stargazing',{'empty_copy':'今天先看云。'})
    assert result.ok and c.effective_settings('emoti.bundled.stargazing')['empty_copy']=='今天先看云。'


def test_center_clear_data_and_quarantine(tmp_path: Path):
    subsystem,c=center(tmp_path); subsystem.health.record_failure('emoti.bundled.stargazing','x'); subsystem.health.record_failure('emoti.bundled.stargazing','x'); subsystem.health.record_failure('emoti.bundled.stargazing','x')
    assert c.clear_quarantine('emoti.bundled.stargazing').ok
    assert c.clear_data('emoti.bundled.stargazing').ok


def test_center_unknown_plugin_returns_failure(tmp_path: Path):
    subsystem,c=center(tmp_path); assert not c.set_enabled('missing',True).ok
