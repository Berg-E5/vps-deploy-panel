# 安装包辅助脚本: 开机自启登记 / 状态检查。
# 由安装程序在安装后和卸载前调用。
param(
    [switch]$RegisterAutoStart,
    [switch]$UnregisterAutoStart,
    [switch]$Status
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$taskName = 'VPSDeployPanel'
# 脚本本身就在安装目录里 (不是 scripts\ 子目录)
$appDir = (Resolve-Path $PSScriptRoot).Path
$pythonw = Join-Path $appDir 'runtime\python\pythonw.exe'
$launcher = Join-Path $appDir 'launcher.pyw'

function Test-Task {
    return $null -ne (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)
}

try {
    if ($UnregisterAutoStart) {
        if (Test-Task) {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
            Write-Host '[VPS Deploy Panel] 已移除开机自启。'
        }
        exit 0
    }

    if ($RegisterAutoStart) {
        if (-not (Test-Path $pythonw)) { throw "找不到自带运行时: $pythonw" }
        $action = New-ScheduledTaskAction -Execute $pythonw -Argument ('"' + $launcher + '"') -WorkingDirectory $appDir
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        # 登录即启动: 面板只监听 127.0.0.1, 不对外暴露。
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'VPS Deploy Panel 本机控制台' -Force | Out-Null
        Write-Host '[VPS Deploy Panel] 已加入开机自启。'
        exit 0
    }

    if ($Status) {
        Write-Host ('installed=' + (Test-Path $pythonw))
        Write-Host ('autostart=' + (Test-Task))
        exit 0
    }
} catch {
    Write-Host "[VPS Deploy Panel] 辅助脚本失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
