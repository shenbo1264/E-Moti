from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_pyinstaller_build_script_uses_onedir_windowed_app_bundle():
    script = read_text("tools/build_windows_app.ps1")

    assert "PyInstaller" in script
    assert "[string]$PythonPath" in script
    assert "[string]$VoiceRuntimePath" in script
    assert "Resolve-PythonInvocation" in script
    assert "RequestedPath $PythonPath" in script
    assert "runtime_assets" in script
    assert "runtime_voice_services" in script
    assert "item_icons" in script
    assert "--onedir" in script
    assert "--windowed" in script
    assert "--hidden-import" in script
    assert "ddgs" in script
    assert "edge_tts" in script
    assert "--add-data" in script
    assert "assets" in script
    assert "voice_services" in script
    assert "packaging\\launch_control_panel.py" in script
    assert "dist\\E-Moti\\E-Moti.exe" in script
    assert "voice_runtime" in script


def test_pyinstaller_build_script_copies_all_bundled_companion_packs():
    script = read_text("tools/build_windows_app.ps1")

    assert "$RuntimeCompanionDir" in script
    assert "$SourceCompanionDir" in script
    assert "Get-ChildItem -Force -LiteralPath $SourceCompanionDir" in script
    assert "$RuntimeCharacterDir" not in script
    assert "$SourceCharacterDir" not in script
    assert "portrait_manifest.json" in script
    assert "portraits" in script
    assert "portrait_assets_provenance.md" in script
    assert "LICENSE.md" in script


def test_pyinstaller_build_script_copies_voice_service_scripts():
    script = read_text("tools/build_windows_app.ps1")

    assert "$RuntimeVoiceServicesDir" in script
    assert "$SourceVoiceServicesDir" in script
    assert "Get-ChildItem -Force -LiteralPath $SourceVoiceServicesDir" in script
    assert "preflight_voice_services.py" in script
    assert "start_qwen3_tts_server.ps1" in script
    assert "start_ikaros_gptsovits_server.ps1" in script
    assert "start_sensevoice_asr_server.ps1" in script


def test_pyinstaller_build_script_can_copy_optional_portable_voice_runtime():
    script = read_text("tools/build_windows_app.ps1")

    assert "$VoiceRuntimePath" in script
    assert "$PortableVoiceRuntimeDir" in script
    assert "Test-Path -LiteralPath $VoiceRuntimePath" in script
    assert "Copy-Item -LiteralPath $VoiceRuntimePath" in script


def test_pyinstaller_build_script_does_not_hardcode_bare_python():
    script = read_text("tools/build_windows_app.ps1")

    assert "& python @Arguments" not in script
    assert "$PythonArguments = @($ResolvedPython.Arguments) + $Arguments" in script
    assert "& $ResolvedPython.Command @PythonArguments" in script


def test_installer_script_defaults_to_visible_portable_sibling_directory_and_shortcuts():
    script = read_text("packaging/e-moti-installer.iss")

    assert "AppName=E-Moti" in script
    assert "OutputDir=..\\dist\\installer" in script
    assert "OutputBaseFilename=E-Moti_Setup_0.1.0" in script
    assert "DefaultDirName={src}\\E-Moti-portable" in script
    assert "DisableDirPage=no" in script
    assert "UsePreviousAppDir=no" in script
    assert "AlwaysShowDirOnReadyPage=yes" in script
    assert "{localappdata}\\Programs\\E-Moti" not in script
    assert 'Source: "..\\dist\\E-Moti\\*"' in script
    assert "星汐 E-Moti" in script
    assert "星汐桌宠模式" in script
    assert 'Parameters: "--pet-mode"' in script


def test_installer_build_script_calls_inno_and_verifies_artifact():
    script = read_text("tools/build_windows_installer.ps1")

    assert "build_windows_app.ps1" in script
    assert "[string]$PythonPath" in script
    assert "[string]$VoiceRuntimePath" in script
    assert "-PythonPath" in script
    assert "-VoiceRuntimePath" in script
    assert "ISCC.exe" in script
    assert "packaging\\e-moti-installer.iss" in script
    assert "dist\\installer\\E-Moti_Setup_0.1.0.exe" in script
    assert "Test-Path" in script
