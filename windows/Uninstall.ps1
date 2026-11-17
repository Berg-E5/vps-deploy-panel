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
$port = 8787

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
    if ($cmdline -and ($cmdline -like "*$appDir*" -or $cmdline -like '*launcher.pyw*')) {
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

# ---- 4. 清掉运行时生成的缓存 ----
# 安装器只知道自己装过的文件; 面板跑起来后 Python 会生成 __pycache__,
# 卸载器不会删它们, 结果留下一个空壳目录。顺手清掉, 装完即净。
Get-ChildItem -Path $appDir -Directory -Filter '__pycache__' -Recurse -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
Get-ChildItem -Path $appDir -Directory -Filter '*.dist-info' -Recurse -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
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

exit 0
