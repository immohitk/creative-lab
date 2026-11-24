#define MyAppName "CL System Monitor"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Creative Lab"
#define MyAppExeName "CLSystemMonitor.exe"

[Setup]
AppId={{A7D9F2C1-6B43-4E85-9A21-7C5B3D8E4F60}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CL System Monitor
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\CL-SM.ico
OutputDir=release
OutputBaseFilename=CL-System-Monitor-Setup-0.1.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\CLSystemMonitor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\CL System Monitor"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\CL System Monitor"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch CL System Monitor"; Flags: postinstall nowait skipifsilent
