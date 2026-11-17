# 卸载前清理: 停掉正在运行的面板, 移除开机自启。
#
# 顺序很关键:
#   1. 先停计划任务 (并等它真的停下来)
#   2. 再注销计划任务 —— 任务还在 Running 时注销会失败
#   3. 最后杀掉占用 8787 的面板进程 —— 不停它, 安装目录里的文件就被锁住,
#      Inno 删不干净, 会留下 app\ 和 runtime\ 残余
Set-StrictMode -Version Latest
$ErrorActionPreference = 'SilentlyContinue'

$taskName = 'VPSDeployPanel'
$appDir = (Resolve-Path $PSScriptRoot).Path

# 面板可能因端口冲突改用过别的端口, 端口写在用户数据目录里
$port = 8787
$portFile = Join-Path $env:LOCALAPPDATA 'VPSDeployPanel\port'
if (Test-Path $portFile) {
    $recorded = (Get-Content $portFile -Raw -ErrorAction SilentlyContinue).Trim()
    if ($recorded -match '^\d+$') { $port = [int]$recorded }
}

function Write-Note([string]$message) {
    Write-Host "[VPS Deploy Panel] $message"
}

# ---- 1. 停任务 ----
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 20; $i++) {
        $state = (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue).State
        if (-not $state -or $state -ne 'Running') { break }
        Start-Sleep -Milliseconds 500
    }
}

# ---- 2. 注销任务 (任务仍在 Running 时注销会失败, 所以重试) ----
for ($i = 0; $i -lt 10; $i++) {
    if (-not (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) { break }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Write-Note '开机自启任务未能完全移除，请手动在任务计划程序中删除。'
} else {
    Write-Note '已移除开机自启。'
}

# ---- 3. 停掉占用端口的面板进程 ----
# 只杀本安装目录下的进程, 不碰用户机器上别的 python
$targets = @()
$listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
foreach ($conn in $listeners) {
    $ownerId = $conn.OwningProcess
    if (-not $ownerId) { continue }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerId" -ErrorAction SilentlyContinue
    if (-not $proc) { continue }
    $cmdline = $proc.CommandLine
    if (-not $cmdline) { continue }
    # 路径分隔符要统一: 安装目录是 \, 而进程命令行里可能是 /,
    # 不归一化就匹配不上, 面板进程会活下来把文件锁住。
    $normCmd = $cmdline.Replace('\', '/').ToLowerInvariant()
    $normApp = $appDir.Replace('\', '/').ToLowerInvariant()
    if ($normCmd.Contains($normApp) -or $normCmd.Contains('launcher.pyw')) {
        $targets += $ownerId
    }
}
foreach ($ownerId in ($targets | Select-Object -Unique)) {
    Stop-Process -Id $ownerId -Force -ErrorAction SilentlyContinue
}
if ($targets.Count -gt 0) {
    Start-Sleep -Seconds 2
    Write-Note "已停止 $($targets.Count) 个面板进程。"
}

# ---- 4. 等被占用的文件真正释放 ----
# 面板进程刚被 Stop-Process 掉, 但 Windows 的 DLL 句柄可能还没回收,
# 卸载器随后删文件会失败, 留下一堆 runtime DLL 残余。等句柄释放。
for ($i = 0; $i -lt 30; $i++) {
    $locked = Get-ChildItem -Path $appDir -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            try {
                $s = [System.IO.File]::Open($_.FullName, 'Open', 'Read', 'None')
                $s.Close()
                $false
            } catch { $true }
        }
    if (-not $locked) { break }
    if ($i -eq 0) { Write-Note '等待文件句柄释放...' }
    Start-Sleep -Milliseconds 500
}

# ---- 5. 清掉运行时生成的缓存 ----
# 安装器只知道自己装过的文件; 面板跑起来后 Python 会生成 __pycache__,
# 卸载器不会删它们, 结果留下一个空壳目录。顺手清掉, 装完即净。
Get-ChildItem -Path $appDir -Directory -Filter '__pycache__' -Recurse -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
Get-ChildItem -Path $appDir -Directory -Filter '*.dist-info' -Recurse -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
# 仍然删不掉的文件 (被别的程序占着) 先移走, 让卸载器能删掉目录本身
Get-ChildItem -Path $appDir -Recurse -File -ErrorAction SilentlyContinue |
    ForEach-Object {
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
        if (Test-Path $_.FullName) {
            try {
                Move-Item $_.FullName (Join-Path $env:TEMP ("vpsdeploy-stale-" + [guid]::NewGuid().ToString('N') + $_.Name)) -Force -ErrorAction SilentlyContinue
            } catch { }
        }
    }
# 空目录也一并删掉
for ($i = 0; $i -lt 5; $i++) {
    $left = Get-ChildItem -Path $appDir -Directory -Recurse -ErrorAction SilentlyContinue |
        Sort-Object { $_.FullName.Length } -Descending
    if (-not $left) { break }
    foreach ($dir in $left) {
        if (-not (Get-ChildItem -Path $dir.FullName -Force -ErrorAction SilentlyContinue)) {
            Remove-Item $dir.FullName -Force -Recurse -ErrorAction SilentlyContinue
        }
    }
}

# ---- 6. 删掉安装根目录 ----
# 卸载器自己就装在这个目录里, 运行时删不掉它;
# 卸载器退出后 Inno 再删一次, 但那时目录已经空了, 仍会留下一个空壳。
# 所以这里只能保证内容清干净 —— 根目录由 Inno 的收尾处理。
try {
    if (-not (Get-ChildItem -Path $appDir -Force -ErrorAction SilentlyContinue)) {
        Remove-Item $appDir -Force -Recurse -ErrorAction SilentlyContinue
    }
} catch { }

exit 0
