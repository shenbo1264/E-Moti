import json
from pathlib import Path
import zipfile
from guanghe_companion.plugin_package import PluginPackageManager, build_plugin_archive


def plugin(root: Path, plugin_id='emoti.community.package'):
    root.mkdir(parents=True)
    (root/'emoti-plugin.json').write_text(json.dumps({'schema_version':1,'id':plugin_id,'name':'Package','version':'0.1.0','api_version':'1','entrypoint':'plugin.py:activate','description':'package test','default_enabled':False,'permissions':[],'dependencies':[],'settings':{},'contributes':{}},indent=2),encoding='utf-8')
    (root/'plugin.py').write_text('def activate(ctx): return None\n',encoding='utf-8')
    (root/'README.md').write_text('# package\n',encoding='utf-8')


def test_build_install_and_uninstall(tmp_path: Path):
    src=tmp_path/'src'; plugin(src); archive=tmp_path/'plugin.zip'
    report=build_plugin_archive(src,archive); assert report.file_count==3 and archive.exists()
    manager=PluginPackageManager(tmp_path/'installed'); installed=manager.install(archive)
    assert installed.ok and (tmp_path/'installed/emoti.community.package/plugin.py').is_file()
    assert manager.uninstall('emoti.community.package').ok


def test_install_rejects_traversal(tmp_path: Path):
    archive=tmp_path/'bad.zip'
    with zipfile.ZipFile(archive,'w') as z: z.writestr('../evil.txt','bad')
    assert not PluginPackageManager(tmp_path/'installed').install(archive).ok


def test_install_rejects_multiple_manifests(tmp_path: Path):
    archive=tmp_path/'bad.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('a/emoti-plugin.json','{}'); z.writestr('b/emoti-plugin.json','{}')
    assert not PluginPackageManager(tmp_path/'installed').install(archive).ok


def test_install_can_update_existing_plugin(tmp_path: Path):
    src=tmp_path/'src'; plugin(src); archive=tmp_path/'a.zip'; build_plugin_archive(src,archive)
    manager=PluginPackageManager(tmp_path/'installed'); assert manager.install(archive).ok
    (src/'README.md').write_text('# updated\n'); build_plugin_archive(src,archive)
    result=manager.install(archive); assert result.ok and result.payload['updated'] is True


def test_build_skips_hidden_and_cache_files(tmp_path: Path):
    src=tmp_path/'src'; plugin(src); (src/'.secret').write_text('x'); (src/'__pycache__').mkdir(); (src/'__pycache__/x.pyc').write_bytes(b'x')
    archive=tmp_path/'p.zip'; report=build_plugin_archive(src,archive)
    with zipfile.ZipFile(archive) as z: names=z.namelist()
    assert '.secret' not in names and all('__pycache__' not in n for n in names)
