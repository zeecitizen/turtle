; Claude EA — Windows installer (Inno Setup)
; Build ClaudeEA.exe first (build_exe.bat), then compile this file.
[Setup]
AppName=Claude EA
AppVersion=1.0
AppPublisher=Zeeshan
DefaultDirName={autopf}\ClaudeEA
DefaultGroupName=Claude EA
OutputDir=Output
OutputBaseFilename=ClaudeEA-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Files]
Source: "dist\ClaudeEA.exe";            DestDir: "{app}"; Flags: ignoreversion
Source: "..\CLAUDE_REALTIME_EA.md";     DestDir: "{app}"; Flags: ignoreversion
Source: "BUILD_INSTALLER.md";           DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Claude EA";        Filename: "{app}\ClaudeEA.exe"
Name: "{autodesktop}\Claude EA";  Filename: "{app}\ClaudeEA.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Run]
Filename: "{app}\ClaudeEA.exe"; Description: "Launch Claude EA"; Flags: nowait postinstall skipifsilent
