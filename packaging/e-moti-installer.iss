#define AppVersion "0.1.0"

[Setup]
AppId={{50F129D4-9601-4ED2-A218-90E217711FFB}
AppName=E-Moti
AppVersion={#AppVersion}
AppPublisher=Guanghe Demo
DefaultDirName={localappdata}\Programs\E-Moti
DefaultGroupName=E-Moti
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=E-Moti_Setup_0.1.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=E-Moti

[Files]
Source: "..\dist\E-Moti\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\星汐 E-Moti"; Filename: "{app}\E-Moti.exe"; WorkingDir: "{app}"
Name: "{autoprograms}\星汐桌宠模式"; Filename: "{app}\E-Moti.exe"; Parameters: "--pet-mode"; WorkingDir: "{app}"
Name: "{autodesktop}\星汐 E-Moti"; Filename: "{app}\E-Moti.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\星汐桌宠模式"; Filename: "{app}\E-Moti.exe"; Parameters: "--pet-mode"; WorkingDir: "{app}"
