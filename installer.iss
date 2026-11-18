#define AppName "CryptArch"
#define AppVersion "1.0.1"
#define AppExe "CryptArch.exe"

[Setup]
#ifdef TEST_BUILD
AppId={{932AA688-21A1-49D2-8855-C039649F85BE}
AppName=CryptArch Installer Test
OutputBaseFilename=CryptArch-Setup-Test
PrivilegesRequired=lowest
#else
AppId={{16ACBF91-8D0B-4EC9-817E-B5E50A86F10F}
AppName={#AppName}
OutputBaseFilename=CryptArch-Setup
PrivilegesRequired=admin
#endif
AppVersion={#AppVersion}
AppPublisher=CryptArch
DefaultDirName={autopf}\CryptArch
DefaultGroupName=CryptArch
DisableProgramGroupPage=yes
DisableWelcomePage=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=CryptArch
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=assets\CryptArch.ico
OutputDir=release
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "release\CryptArch-icon\*"; Excludes: "README.md"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
#ifdef TEST_BUILD
Name: "{app}\test-startmenu\CryptArch"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{app}\test-desktop\CryptArch"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon
#else
Name: "{group}\CryptArch"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\CryptArch"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon
#endif

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,CryptArch}"; Flags: nowait postinstall skipifsilent
