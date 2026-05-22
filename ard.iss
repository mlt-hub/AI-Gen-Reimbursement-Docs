; ── AI报账文档生成器 Inno Setup 安装脚本 ──
; 用法（CI 自动编译）: iscc.exe /DMyAppVersion=5.0.2 ard.iss
; 本地编译需先跑 build_exe.ps1 生成 dist\ard\

#ifndef MyAppVersion
#define MyAppVersion "0.0.0"
#endif

#define MyAppName "AI报账文档生成器"
#define MyAppExeName "ard.exe"
#define MyAppPublisher "mlt-hub"
#define MyAppURL "https://github.com/mlt-hub/ai-gen-reimbursement-docs-release"

[Setup]
AppId={{B8F3A2E1-9D5C-4A7E-8F12-C6D3B9A0E5F7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\ard
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=ard-setup_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
; 覆盖安装时自动卸载旧版
Uninstallable=yes
DirExistsWarning=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Files]
Source: "dist\ard\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 桌面快捷方式
Name: "{autodesktop}\启动 Web 界面"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--web"; WorkingDir: "{app}"; Comment: "启动 AI 报账文档生成器 Web 界面"
Name: "{autodesktop}\命令行方式"; Filename: "{cmd}"; Parameters: "/K ""{app}\{#MyAppExeName} --help"""; WorkingDir: "{app}"; Comment: "打开命令行查看使用说明"
; 开始菜单程序组
Name: "{group}\启动 Web 界面"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--web"; WorkingDir: "{app}"
Name: "{group}\命令行方式"; Filename: "{cmd}"; Parameters: "/K ""{app}\{#MyAppExeName} --help"""; WorkingDir: "{app}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"

[Registry]
; 添加到用户 PATH（不覆盖已有值）
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath; Flags: preservestringtype

[Code]
function NeedsAddPath: Boolean;
var
  CurrentPath: string;
begin
  Result := True;
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', CurrentPath) then
    Exit;
  // 检查 {app} 是否已在 PATH 中
  if Pos(UpperCase(ExpandConstant('{app}')), UpperCase(CurrentPath)) > 0 then
    Result := False;
end;
