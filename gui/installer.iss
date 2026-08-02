; TurtleDesktop-Setup.exe - a real Windows installer you can hand to someone.
;
; PyInstaller has no ARM64 wheel, so rather than freezing an .exe this ships the actual
; application (a small Python program plus the engine it drives) and wires it into Windows
; the way a normal app is wired: Start menu, desktop icon, auto-start, Add/Remove Programs.
;
; Build:  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" gui\installer.iss
; Output: gui\Output\TurtleDesktop-Setup.exe

#define AppName    "Turtle Desktop"
#define AppVer     "1.0"
#define AppPub     "Zeeshan"
#define AppExeName "TurtleDesktop.bat"

[Setup]
AppId={{9E1C4A6B-7C2D-4F31-9A5E-A1B2C3D40001}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher={#AppPub}
DefaultDirName={autopf}\TurtleDesktop
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=TurtleDesktop-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "autostart";  Description: "Start {#AppName} automatically when I log in"; GroupDescription: "Startup:"

[Files]
; the application
Source: "claude_ea_gui.py";   DestDir: "{app}\gui"; Flags: ignoreversion
Source: "trade_book.py";      DestDir: "{app}\gui"; Flags: ignoreversion
Source: "settings.py";        DestDir: "{app}\gui"; Flags: ignoreversion
Source: "lessons.py";      DestDir: "{app}\gui"; Flags: ignoreversion
Source: "research.py";      DestDir: "{app}\gui"; Flags: ignoreversion
Source: "funnel.py";         DestDir: "{app}\gui"; Flags: ignoreversion
Source: "windows.py";        DestDir: "{app}\gui"; Flags: ignoreversion
Source: "lifecycle.py"; DestDir: "{app}\gui"; Flags: ignoreversion
Source: "autolearn.py"; DestDir: "{app}\gui"; Flags: ignoreversion
Source: "attach_ea.py";   DestDir: "{app}\gui"; Flags: ignoreversion
Source: "philosophy.py";     DestDir: "{app}\gui"; Flags: ignoreversion
Source: "labels_explorer.py";DestDir: "{app}\gui"; Flags: ignoreversion
Source: "install.ps1";        DestDir: "{app}\gui"; Flags: ignoreversion
Source: "test_gui.py";        DestDir: "{app}\gui"; Flags: ignoreversion
Source: "BUILD_INSTALLER.md"; DestDir: "{app}\gui"; Flags: ignoreversion
; the engine it drives
Source: "..\monitor\*.py";              DestDir: "{app}\monitor";              Flags: ignoreversion
Source: "..\monitor\strategy_lab\*.py"; DestDir: "{app}\monitor\strategy_lab"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\mt5\*.mq5";                 DestDir: "{app}\mt5";                  Flags: ignoreversion skipifsourcedoesntexist
Source: "..\monitor\setup_labels\zee_labels.json"; DestDir: "{app}\monitor\setup_labels"; Flags: ignoreversion onlyifdoesntexist
Source: "..\CLAUDE_REALTIME_EA.md";     DestDir: "{app}";                      Flags: ignoreversion
Source: "..\WINNING_STRATEGY.md";       DestDir: "{app}";                      Flags: ignoreversion skipifsourcedoesntexist
; launcher + first-run notes
Source: "TurtleDesktop.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "FIRST_RUN.txt";     DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Playbook";             Filename: "{app}\CLAUDE_REALTIME_EA.md"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}";     Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent shellexec




