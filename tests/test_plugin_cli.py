from pathlib import Path
import json
import shutil
import subprocess
import sys


def test_plugin_cli_lists_plugins(tmp_path: Path):
    root=Path(__file__).resolve().parents[1]
    app=tmp_path/'app'; app.mkdir(); shutil.copytree(root/'plugins',app/'plugins')
    completed=subprocess.run([sys.executable,str(root/'tools/emoti_plugin_cli.py'),'--app-root',str(app),'--user-data-root',str(tmp_path/'user'),'list'],capture_output=True,text=True)
    assert completed.returncode==0
    payload=json.loads(completed.stdout); assert len(payload['plugins'])>=3
