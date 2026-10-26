#define AppName "BuktiTF"
#define AppVersion "1.0.0"
#define AppExe "BuktiTF.exe"
; Bootstrapper kecil (perlu internet saat instalasi, hanya jika WebView2 belum ada).
; Untuk installer yang sepenuhnya offline, unduh "Evergreen Standalone Installer" (±170 MB)
; dari microsoft.com/edge/webview2, taruh di folder ini, dan ganti nama di bawah.
#define WebView2Installer "MicrosoftEdgeWebview2Setup.exe"

[Setup]
AppId={{C30BBAC2-E3B0-412F-8F58-D09B3410BCE8}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Timbul Fishing
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=BuktiTF-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes
RestartApplications=no

[Files]
Source: "..\dist\BuktiTF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#WebView2Installer}"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
const
  WebView2Key = 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasVersion(RootKey: Integer; const Key: String): Boolean;
var
  V: String;
begin
  Result := RegQueryStringValue(RootKey, Key, 'pv', V) and (V <> '') and (V <> '0.0.0.0');
end;

function NeedsWebView2: Boolean;
begin
  Result := not (HasVersion(HKLM32, WebView2Key) or HasVersion(HKLM64, WebView2Key)
                 or HasVersion(HKCU, WebView2Key));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if (CurStep = ssPostInstall) and NeedsWebView2 then
  begin
    WizardForm.StatusLabel.Caption := 'Installing Microsoft Edge WebView2 Runtime...';
    WizardForm.ProgressGauge.Style := npbstMarquee;
    try
      Exec(ExpandConstant('{tmp}\{#WebView2Installer}'), '/silent /install', '',
           SW_HIDE, ewWaitUntilTerminated, ResultCode);
    finally
      WizardForm.ProgressGauge.Style := npbstNormal;
    end;
    if NeedsWebView2 then
      MsgBox('BuktiTF is installed, but Microsoft Edge WebView2 Runtime could not be installed ' +
             '(an internet connection may be required).' + #13#10 +
             'Please install it from microsoft.com/edge/webview2, then open BuktiTF.',
             mbError, MB_OK);
  end;
end;