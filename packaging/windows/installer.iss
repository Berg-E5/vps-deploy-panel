; VPS Deploy Panel —— Windows 桌面版安装包 (Inno Setup 6)
;
; 与浏览器版 (windows/installer.iss) 的区别:
;   浏览器版  装 Python 运行时 + 面板代码, 启动后开浏览器
;   桌面版    额外装一个原生窗口 (WebView2), 双击就是原生应用
;
; 两版共用同一份运行时和同一份 app/ 代码, 后端完全一样。

#ifndef AppVersion
  #define AppVersion "1.0.3"
#endif
#ifndef BundleDir
  #define BundleDir "..\..\.build\windows-desktop"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

#define AppName "VPS Deploy Panel"
#define AppNameLower "vpsdeploypanel"

[Setup]
AppId={{7E9C2B4A-6D31-4F58-9A0E-2C5B7D8E1F37}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputBaseFilename=VPSDeployPanel-{#AppVersion}-Desktop-Setup
OutputDir={#OutputDir}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; 不需要管理员: 装到当前用户目录
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayName={#AppName} (桌面版)
UninstallDisplayIcon={app}\VPSDeployPanel.exe
SetupIconFile={#BundleDir}\vpsdeploy.ico
LicenseFile={#BundleDir}\LICENSE
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoCompany={#AppName}
VersionInfoDescription={#AppName} 桌面客户端
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimp.CreateDesktopIcon=创建桌面快捷方式
chinesesimp.AutoStart=登录时自动启动（开机自启）
chinesesimp.LaunchApp=安装完成后立即启动 {0}
chinesesimp.InstallDirWarn=建议保持默认目录（当前用户目录，无需管理员权限）。

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "{cm:AutoStart}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 原生外壳 + WebView2 运行时
Source: "{#BundleDir}\VPSDeployPanel.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\VPSDeployPanel.exe.config"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\Microsoft.Web.WebView2.Core.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\Microsoft.Web.WebView2.WinForms.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\WebView2Loader.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\WebView2-LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\BUILD-MANIFEST.json"; DestDir: "{app}"; Flags: ignoreversion
; 自带 Python 运行时
Source: "{#BundleDir}\runtime\*"; DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs
; 面板代码
Source: "{#BundleDir}\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#BundleDir}\requirements-codex-worker.txt"; DestDir: "{app}"; Flags: ignoreversion
; 卸载清理脚本
Source: "{#BundleDir}\scripts\Uninstall-Desktop.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion
; 说明与许可
Source: "{#BundleDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\README.md"; DestDir: "{app}"; DestName: "安装说明.md"; Flags: ignoreversion

[Dirs]
; 用户数据放在安装目录之外: 覆盖升级不会抹掉
Name: "{localappdata}\{#AppNameLower}"; Permissions: users-modify
Name: "{localappdata}\{#AppNameLower}\logs"; Permissions: users-modify

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\VPSDeployPanel.exe"; WorkingDir: "{app}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{group}\在线手册"; Filename: "https://berg-e5.github.io/vps-deploy-panel/"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\VPSDeployPanel.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\VPSDeployPanel.exe"; WorkingDir: "{app}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 停掉后台再删文件, 否则进程锁着文件, 目录删不掉
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\Uninstall-Desktop.ps1"""; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "StopDesktopClient"
