; VPS Deploy Panel —— Windows 安装包定义 (Inno Setup 6)
;
; 装出来的是一个自包含的本机控制台:
;   * 自带 Python 运行时和依赖 —— 用户机器上不需要先装 Python
;   * 自带面板代码和启动器
;   * 安装到当前用户目录 (不需要管理员权限)
;   * 开始菜单 + 桌面快捷方式, 可选开机自启
;   * 完整卸载, 不留残余
;
; 输入由 windows/build-installer.ps1 准备到 windows\build\ :
;   runtime\   自带 Python 运行时 + 依赖
;   app\       面板代码
;   launcher.pyw / PanelState.ps1 / Uninstall.ps1 / icon.ico / requirements.txt

#define AppName "VPS Deploy Panel"
#define AppNameLower "vpsdeploypanel"
#define AppVersion "1.0.7"
#define AppPublisher "VPS Deploy Panel"
#define AppUrl "https://github.com/Berg-E5/vps-deploy-panel"
#define AppDocsUrl "https://berg-e5.github.io/vps-deploy-panel/"

[Setup]
AppId={{7E9C2B4A-6D31-4F58-9A0E-2C5B7D8E1F36}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppDocsUrl}
AppUpdatesURL={#AppUrl}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputBaseFilename=VPSDeployPanel-{#AppVersion}-Setup
OutputDir=..\dist
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; 不需要管理员: 装到当前用户目录
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\runtime\python\python.exe
SetupIconFile=build\icon.ico
LicenseFile=build\LICENSE
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} 安装程序
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimp.CreateDesktopIcon=创建桌面快捷方式
chinesesimp.LaunchApp=安装完成后立即启动 {0}
chinesesimp.AutoStart=登录时自动启动（开机自启）
chinesesimp.NoOpenSSH=未检测到系统 OpenSSH 客户端。面板会自动改用内置的 Paramiko 完成 SSH 连接，部署功能不受影响；需要系统级 OpenSSH 时可在 Windows「可选功能」里安装。
chinesesimp.InstallDirWarn=建议保持默认目录（当前用户目录，无需管理员权限）。

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "{cm:AutoStart}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 自带 Python 运行时 + 已装好的依赖
Source: "build\runtime\*"; DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs
; 面板代码
Source: "build\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
; 启动器与辅助脚本
Source: "build\launcher.pyw"; DestDir: "{app}"; Flags: ignoreversion
Source: "build\PanelState.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "build\Uninstall.ps1"; DestDir: "{app}"; Flags: ignoreversion
; 说明与许可
Source: "build\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "build\requirements-codex-worker.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "build\requirements-win.lock"; DestDir: "{app}"; Flags: ignoreversion
Source: "build\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "build\README.md"; DestDir: "{app}"; DestName: "安装说明.md"; Flags: ignoreversion

[Dirs]
; 用户数据放在安装目录之外: 升级覆盖安装时不会被抹掉
Name: "{localappdata}\{#AppNameLower}"; Permissions: users-modify
Name: "{localappdata}\{#AppNameLower}\logs"; Permissions: users-modify

[Icons]
; 启动器用相对脚本名: 安装目录名含空格, 绝对路径当参数传会被引号规则坑掉
Name: "{group}\{#AppName}"; Filename: "{app}\runtime\python\pythonw.exe"; Parameters: "launcher.pyw"; WorkingDir: "{app}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{group}\在线手册"; Filename: "{#AppDocsUrl}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\runtime\python\pythonw.exe"; Parameters: "launcher.pyw"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; 装完立刻起一次面板, 用户马上能打开界面
Filename: "{app}\runtime\python\pythonw.exe"; Parameters: "launcher.pyw"; WorkingDir: "{app}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent
; 登记开机自启 (可选)
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\PanelState.ps1"" -RegisterAutoStart"; WorkingDir: "{app}"; Flags: runhidden; Tasks: autostart; StatusMsg: "正在配置开机自启..."

[UninstallRun]
; 停掉后台面板并移除开机自启, 再删文件
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\Uninstall.ps1"""; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "StopPanelAndRemoveAutostart"
