from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_pyinstaller_build_script_uses_onedir_windowed_app_bundle():
    script = read_text("tools/build_windows_app.ps1")

    assert "PyInstaller" in script
    assert "runtime_assets" in script
    assert "item_icons" in script
    assert "--onedir" in script
    assert "--windowed" in script
    assert "--add-data" in script
    assert "assets" in script
    assert "packaging\\launch_control_panel.py" in script
    assert "dist\\E-Moti\\E-Moti.exe" in script


def test_installer_script_outputs_local_appdata_installer_and_shortcuts():
    script = read_text("packaging/e-moti-installer.iss")

    assert "AppName=E-Moti" in script
    assert "OutputDir=..\\dist\\installer" in script
    assert "OutputBaseFilename=E-Moti_Setup_0.1.0" in script
    assert "DefaultDirName={localappdata}\\Programs\\E-Moti" in script
    assert 'Source: "..\\dist\\E-Moti\\*"' in script
    assert "星汐 E-Moti" in script
    assert "星汐桌宠模式" in script
    assert 'Parameters: "--pet-mode"' in script


def test_installer_build_script_calls_inno_and_verifies_artifact():
    script = read_text("tools/build_windows_installer.ps1")

    assert "build_windows_app.ps1" in script
    assert "ISCC.exe" in script
    assert "packaging\\e-moti-installer.iss" in script
    assert "dist\\installer\\E-Moti_Setup_0.1.0.exe" in script
    assert "Test-Path" in script
