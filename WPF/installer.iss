#define AppVersion "2.0.0-beta.1"
#define BuildDir "..\release\CryptArch V2 Beta (external FFmpeg)"
#define FFmpegArchive "ffmpeg-9.0.2-essentials_build.7z"
#define FFmpegDir "ffmpeg-9.0.2-essentials_build"

[Setup]
#ifdef SmokeInstall
AppId={{158E1F00-FED0-4A37-A43F-9AC5E14F9A38}
OutputBaseFilename=CryptArch-V2-Beta-Setup-Test
#else
AppId={{2D5C6DB0-CC36-45E9-9645-A4910A5F4C4A}
OutputBaseFilename=CryptArch-V2-Beta-Setup
#endif
AppName=CryptArch V2 Beta
AppVersion={#AppVersion}
VersionInfoVersion=2.0.0.1
AppPublisher=CryptArch
DefaultDirName={localappdata}\Programs\CryptArch V2 Beta
DefaultGroupName=CryptArch V2 Beta
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\CryptArch V2 Beta.exe
SetupIconFile=..\assets\CryptArch.ico
OutputDir=..\release
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchiveExtraction=enhanced/nopassword
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
english.DownloadTitle=Downloading FFmpeg
english.DownloadHint=Setup downloads the pinned FFmpeg build from Gyan.dev and verifies its checksum.
english.DownloadFailed=Could not download or extract FFmpeg: %1
russian.DownloadTitle=Загрузка FFmpeg
russian.DownloadHint=Установщик скачивает выбранную версию FFmpeg от Gyan.dev и сверяет контрольную сумму.
russian.DownloadFailed=Не удалось скачать или распаковать FFmpeg: %1

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{tmp}\{#FFmpegDir}\bin\ffmpeg.exe"; DestDir: "{app}\engine\_internal\bin"; Flags: external ignoreversion; ExternalSize: 180000000
Source: "{tmp}\{#FFmpegDir}\bin\ffprobe.exe"; DestDir: "{app}\engine\_internal\bin"; Flags: external ignoreversion; ExternalSize: 180000000
Source: "{tmp}\{#FFmpegDir}\LICENSE"; DestDir: "{app}"; DestName: "FFMPEG-LICENSE.txt"; Flags: external ignoreversion; ExternalSize: 36000
Source: "{tmp}\{#FFmpegDir}\README.txt"; DestDir: "{app}"; DestName: "FFMPEG-README.txt"; Flags: external ignoreversion; ExternalSize: 60000

[Icons]
Name: "{group}\CryptArch V2 Beta"; Filename: "{app}\CryptArch V2 Beta.exe"
Name: "{userdesktop}\CryptArch V2 Beta"; Filename: "{app}\CryptArch V2 Beta.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CryptArch V2 Beta.exe"; Description: "{cm:LaunchProgram,CryptArch V2 Beta}"; Flags: nowait postinstall skipifsilent

[Code]
var DownloadPage: TDownloadWizardPage;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(CustomMessage('DownloadTitle'), CustomMessage('DownloadHint'), nil);
  DownloadPage.ShowBaseNameInsteadOfUrl := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  DownloadPage.Clear;
  DownloadPage.Add(
    'https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/{#FFmpegArchive}',
    '{#FFmpegArchive}', '4705843ccaaf54257c16ad90f3e952ece33c17df964ecf7bfdbb0f49c7171077');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
      ExtractArchive(ExpandConstant('{tmp}\{#FFmpegArchive}'), ExpandConstant('{tmp}'), '', True, nil);
      if not (FileExists(ExpandConstant('{tmp}\{#FFmpegDir}\bin\ffmpeg.exe')) and
              FileExists(ExpandConstant('{tmp}\{#FFmpegDir}\bin\ffprobe.exe'))) then
        RaiseException('FFmpeg binaries are missing from the archive.');
    except
      Result := FmtMessage(CustomMessage('DownloadFailed'), [GetExceptionMessage]);
    end;
  finally
    DownloadPage.Hide;
  end;
end;
