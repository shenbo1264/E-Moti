import json
from pathlib import Path
from guanghe_companion.plugin_audit import audit_plugin
from guanghe_companion.plugin_manifest import PluginCandidate, load_plugin_manifest


def candidate(tmp_path: Path, source: str, permissions=()):
    root=tmp_path/'p'; root.mkdir()
    (root/'emoti-plugin.json').write_text(json.dumps({'schema_version':1,'id':'emoti.test.audit','name':'audit','version':'0.1.0','api_version':'1','entrypoint':'plugin.py:activate','description':'audit','default_enabled':False,'permissions':list(permissions),'dependencies':[],'settings':{},'contributes':{}},indent=2),encoding='utf-8')
    (root/'plugin.py').write_text(source,encoding='utf-8')
    return PluginCandidate(root,root/'emoti-plugin.json',load_plugin_manifest(root/'emoti-plugin.json'))


def test_clean_plugin_passes_audit(tmp_path: Path):
    report=audit_plugin(candidate(tmp_path,'def activate(ctx):\n    return None\n'))
    assert report.ok and report.risk_level=='low'


def test_network_import_requires_declared_permission(tmp_path: Path):
    report=audit_plugin(candidate(tmp_path,'import urllib.request\ndef activate(ctx): pass\n'))
    assert not report.ok and any(f.code=='permission-not-declared' for f in report.findings)


def test_network_import_with_permission_is_medium_not_blocked(tmp_path: Path):
    report=audit_plugin(candidate(tmp_path,'import urllib.request\ndef activate(ctx): pass\n',permissions=['network.http']))
    assert report.ok and report.risk_level=='medium'


def test_dynamic_exec_is_blocked(tmp_path: Path):
    report=audit_plugin(candidate(tmp_path,'def activate(ctx):\n    exec("pass")\n'))
    assert not report.ok and any(f.code=='call-exec' for f in report.findings)


def test_audit_digest_is_stable(tmp_path: Path):
    c=candidate(tmp_path,'def activate(ctx): pass\n')
    assert audit_plugin(c).digest==audit_plugin(c).digest
