from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def run(tool,*args):
    return subprocess.run([sys.executable,str(ROOT/'tools'/tool),*map(str,args)],capture_output=True,text=True)


def test_render_plugin_center_preview(tmp_path: Path):
    html=tmp_path/'center.html'; png=tmp_path/'center.png'
    result=run('render_plugin_center_preview.py','--output',html,'--png-output',png)
    assert result.returncode==0 and html.is_file() and png.stat().st_size>1000


def test_render_story_feature_previews(tmp_path: Path):
    result=run('render_story_feature_previews.py','--output-dir',tmp_path)
    assert result.returncode==0 and len(list(tmp_path.glob('*.png')))==3


def test_render_plugin_story_demo(tmp_path: Path):
    gif=tmp_path/'story.gif'; cover=tmp_path/'cover.png'; report=tmp_path/'report.json'
    result=run('render_plugin_story_demo.py','--gif-output',gif,'--cover-output',cover,'--report',report)
    assert result.returncode==0, result.stderr or result.stdout
    payload=json.loads(report.read_text()); assert payload['ok'] and payload['memory_survives_disable']


def test_plugin_runtime_v2_smoke(tmp_path: Path):
    report=tmp_path/'runtime.json'; result=run('run_plugin_runtime_v2_smoke.py','--report',report)
    assert result.returncode==0, result.stderr or result.stdout
    assert json.loads(report.read_text())['ok']


def test_overlay_contract_smoke(tmp_path: Path):
    report=tmp_path/'overlay.json'; result=run('run_overlay_contract_smoke.py','--report',report)
    assert result.returncode==0, result.stderr or result.stdout
    assert json.loads(report.read_text())['ok']
