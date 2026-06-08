; blivechat graphical installer (Simplified Chinese UI)
#define MyAppName "blivechat 直播伴侣"
#define MyAppVersion "1.10.2"
#define MyAppPublisher "blivechat-dev"
#define MyAppURL "https://github.com/xfgryujk/blivechat"
#define MyAppExeName "blivechat.exe"

#define DistDir "..\dist\blivechat"
#define ScriptsDir "..\scripts"
#define VendorDir "..\vendor"
#define LanguagesDir "languages"

; Extra space for ProgramData config/logs (MB -> bytes in Code)
#define ExtraDataMB 50

#ifexist "..\vendor\ffmpeg\bin\ffmpeg.exe"
  #define MemoFfmpegLine "· FFmpeg 便携版（已随安装包附带，将安装到程序目录 tools\ffmpeg）"
#else
  #define MemoFfmpegLine "· FFmpeg：未随包附带，将尝试 winget 或提示您手动下载"
#endif

[Setup]
AppId={{A8F3C2E1-9B4D-4F6A-8C2E-1D5B7A9E3F40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\blivechat
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=output
OutputBaseFilename=blivechat-setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120,100
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes
DisableDirPage=no
DisableProgramGroupPage=no
DisableReadyPage=no
ShowComponentSizes=yes
MinVersion=10.0

[Languages]
Name: "chinesesimplified"; MessagesFile: "{#LanguagesDir}\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"; Flags: unchecked
Name: "compileplugin"; Description: "从源码编译 OBS 插件（需 Visual Studio，一般不必选）"; GroupDescription: "高级选项:"; Flags: unchecked unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "obs-plugintemplate\.deps\*,obs-plugintemplate\build_x64\*,obs-blivechat-bridge\build\*,obs-blivechat-bridge\build-macos\*"
Source: "{#ScriptsDir}\*"; DestDir: "{app}\packaging\scripts"; Flags: ignoreversion
Source: "{#VendorDir}\obs-blivechat-bridge.dll"; DestDir: "{app}\vendor"; Flags: ignoreversion
Source: "{#VendorDir}\locale\*"; DestDir: "{app}\vendor\locale"; Flags: ignoreversion recursesubdirs
Source: "{#VendorDir}\manifest.json"; DestDir: "{app}\vendor"; Flags: ignoreversion
Source: "{#VendorDir}\ffmpeg\*"; DestDir: "{app}\vendor\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{#VendorDir}\BUILD_INFO.txt"; DestDir: "{app}\vendor"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\收集 BUG 报告"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\packaging\scripts\collect-bug-report.ps1"""; WorkingDir: "{app}"
Name: "{group}\安装结果说明"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\packaging\scripts\show-install-result.ps1"""; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "powershell.exe"; \
  Parameters: "{code:GetPostInstallArgs}"; \
  StatusMsg: "正在配置组件（优先使用安装包内预置文件）…"; \
  Flags: waituntilterminated; \
  WorkingDir: "{app}"
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  DependencyPage: TWizardPage;
  DependencyMemo: TNewMemo;
  EstimatedAppBytes: Cardinal;

function GetPostInstallArgs(Param: string): string;
begin
  Result :=
    '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' +
    ExpandConstant('{app}\packaging\scripts\post-install.ps1') +
    '" -AppDir "' + ExpandConstant('{app}') + '"';
  if WizardIsTaskSelected('compileplugin') then
    Result := Result + ' -ForceCompilePlugin';
end;

function FormatBytes(const Bytes: Cardinal): string;
var
  MB: Cardinal;
begin
  MB := (Bytes + 1048575) div 1048576;
  if MB < 1 then
    Result := IntToStr(Bytes) + ' 字节'
  else
    Result := IntToStr(MB) + ' MB';
end;

function GetDirFreeSpaceMB(const Path: string): Cardinal;
var
  Free, Total: Cardinal;
begin
  Result := 0;
  if GetSpaceOnDisk(Path, False, Free, Total) then
    Result := Free div (1024 * 1024);
end;

procedure InitializeWizard;
begin
  if EstimatedAppBytes = 0 then
    EstimatedAppBytes := 120 * 1024 * 1024;
  DependencyPage := CreateCustomPage(
    wpSelectDir,
    '组件与空间',
    '请选择安装位置。安装程序会显示所需空间；缺失组件时优先使用安装包内预置文件。'
  );
  DependencyMemo := TNewMemo.Create(DependencyPage);
  DependencyMemo.Parent := DependencyPage.Surface;
  DependencyMemo.Left := ScaleX(0);
  DependencyMemo.Top := ScaleY(0);
  DependencyMemo.Width := DependencyPage.SurfaceWidth;
  DependencyMemo.Height := DependencyPage.SurfaceHeight;
  DependencyMemo.ReadOnly := True;
  DependencyMemo.ScrollBars := ssVertical;
end;

procedure RefreshDependencyMemo;
var
  Dir, Text: string;
  Required, FreeMB: Cardinal;
begin
  Dir := WizardDirValue;
  Required := EstimatedAppBytes + (Cardinal({#ExtraDataMB}) * 1024 * 1024);
  FreeMB := GetDirFreeSpaceMB(Dir);

  Text :=
    '【安装位置】' + #13#10 +
    Dir + #13#10#13#10 +
    '【空间需求（估算）】' + #13#10 +
    '· 程序文件：约 ' + FormatBytes(EstimatedAppBytes) + #13#10 +
    '· 配置与日志（%ProgramData%\blivechat）：约 {#ExtraDataMB} MB' + #13#10 +
    '· 合计建议预留：约 ' + FormatBytes(Required) + #13#10 +
    '· 当前磁盘可用：约 ' + IntToStr(FreeMB) + ' MB' + #13#10#13#10 +
    '【安装包内预置（优先使用）】' + #13#10 +
    '· OBS 桥接插件 obs-blivechat-bridge.dll' + #13#10 +
    '{#MemoFfmpegLine}' + #13#10;
  Text := Text + #13#10 +
    '【需单独安装（无法预制）】' + #13#10 +
    '· OBS Studio：https://obsproject.com/download' + #13#10 +
    '  若未检测到，安装结束时将提示下载。' + #13#10#13#10 +
    '可在下一步勾选「从源码编译 OBS 插件」（需 Visual Studio，默认不必）。';

  DependencyMemo.Text := Text;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = DependencyPage.ID then
    RefreshDependencyMemo;
  if CurPageID = wpSelectDir then
    WizardForm.DirEdit.OnChange := nil;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Required, FreeBytes: Cardinal;
  FreeMB: Cardinal;
begin
  Result := True;
  if CurPageID = DependencyPage.ID then
  begin
    Required := EstimatedAppBytes + (Cardinal({#ExtraDataMB}) * 1024 * 1024);
    FreeMB := GetDirFreeSpaceMB(WizardDirValue);
    if (FreeMB > 0) and (Cardinal(FreeMB) * 1024 * 1024 < Required) then
    begin
      if MsgBox(
        '目标磁盘可用空间可能不足。' + #13#10 +
        '建议至少 ' + FormatBytes(Required) + '，当前约 ' + IntToStr(FreeMB) + ' MB 可用。' + #13#10#13#10 +
        '是否仍要继续？',
        mbConfirmation, MB_YESNO) = IDNO then
        Result := False;
    end;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoUserInfoSetup, MemoAppInfo, MemoAppInfo2, MemoAppInfo3, MemoAppInfo4: String): String;
var
  Required: Cardinal;
begin
  Required := EstimatedAppBytes + (Cardinal({#ExtraDataMB}) * 1024 * 1024);
  Result :=
    MemoAppInfo + NewLine + NewLine +
    '安装位置：' + WizardDirValue + NewLine +
    '程序约需：' + FormatBytes(EstimatedAppBytes) + NewLine +
    '额外数据目录约：{#ExtraDataMB} MB' + NewLine +
    '建议磁盘预留：' + FormatBytes(Required) + NewLine + NewLine +
    '将优先安装包内 OBS 插件 DLL；FFmpeg/OBS Studio 按检测结果处理。';
end;

procedure DeinitializeSetup();
begin
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
end;
