import json
from pathlib import Path
import subprocess
import sys
import zipfile
from guanghe_companion.release_security import redact_json_payload, scan_json_payload, scan_path, scan_zip


def test_json_scan_reports_field_without_secret_value():
    secret = 'sk-' + 'abcdefghijklmnop'
    report=scan_json_payload({'api_key':secret},path='x.json')
    assert not report.ok and report.findings[0].field=='api_key'
    assert 'abcdefghijklmnop' not in json.dumps(report.to_dict())


def test_directory_scan_handles_text_and_json(tmp_path: Path):
    (tmp_path/'a.json').write_text('{"api_key":"private-value-123456"}')
    (tmp_path/'b.txt').write_text('hello')
    report=scan_path(tmp_path); assert not report.ok and report.scanned_files==2


def test_zip_scan_finds_nested_secret(tmp_path: Path):
    archive=tmp_path/'x.zip'
    with zipfile.ZipFile(archive,'w') as z: z.writestr('config/settings.json','{"token":"private-value-123456"}')
    report=scan_zip(archive); assert not report.ok and report.findings[0].path=='config/settings.json'


def test_zip_scan_flags_unsafe_path(tmp_path: Path):
    archive=tmp_path/'x.zip'
    with zipfile.ZipFile(archive,'w') as z: z.writestr('../evil.txt','hello')
    report=scan_zip(archive); assert not report.ok and report.findings[0].finding_type=='unsafe-zip-path'


def test_redact_json_payload_clears_secret_fields():
    assert redact_json_payload({'api_key':'x','nested':{'password':'y'}})=={'api_key':'','nested':{'password':''}}


def test_release_security_module_cli(tmp_path: Path):
    (tmp_path/'clean.json').write_text('{"api_key":""}')
    report=tmp_path/'report.json'
    completed=subprocess.run([sys.executable,'-m','guanghe_companion.release_security',str(tmp_path),'--report',str(report)],capture_output=True,text=True)
    assert completed.returncode==0 and json.loads(report.read_text())['ok']
