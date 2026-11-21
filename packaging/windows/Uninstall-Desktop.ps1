# 桌面版卸载清理: 停掉原生窗口和它的后端, 再删文件。
#
# 顺序不能反: 进程还活着时文件被锁着, 卸载会留下一堆残余。
Set-StrictMode -Version Latest
$ErrorActionPreference = 'SilentlyContinue'

$appDir = (Resolve-Path $PSScriptRoot).Path
$appHome = Join-Path $env:LOCALAPPDATA 'VPSDeployPanel'

# 1) 先请后端优雅退出 (有部署任务在跑时它会拒绝, 这正是我们要的)
$portFile = Join-Path $appHome 'port'
$port = 8787
if (Test-Path $portFile) {
    $recorded = (Get-Content $portFile -Raw -ErrorAction SilentlyContinue).Trim()
    if ($recorded -match '^\d+$') { $port = [int]$recorded }
}
$token = ''
$envFile = Join-Path $appHome '.env'
if (Test-Path $envFile) {
    try {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^VPSDEPLOY_ADMIN_TOKEN=(.*)$') {
                $token = $Matches[1].Trim('"', "'")
            }
        }
    } catch { $token = '' }
}
if ($token) {
    try {
        Invoke-WebRequest -Method Post -Uri "http://127.0.0.1:$port/api/desktop/stop" `
            -Headers @{ 'X-Admin-Token' = $token } -TimeoutSec 8 -UseBasicParsing | Out-Null
    } catch { }
}

# 2) 停掉原生窗口
Get-Process -Name 'VPSDeployPanel' -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Path -and $_.Path.StartsWith($appDir, [System.StringComparison]::OrdinalIgnoreCase)) {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

# 3) 停掉后端 (只停本安装目录下的那个)
Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = $_.CommandLine
    if ($cmd -and ($cmd -like "*$appDir*" -or $cmd -like '*desktop.py*')) {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

# 4) 等文件句柄释放, 否则 DLL 还被映射着, 删不掉
for ($i = 0; $i -lt 20; $i++) {
    $locked = Get-ChildItem -Path $appDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        try {
            $s = [System.IO.File]::Open($_.FullName, 'Open', 'Read', 'None')
            $s.Close()
            $false
        } catch { $true }
    }
    if (-not $locked) { break }
    Start-Sleep -Milliseconds 500
}

exit 0
