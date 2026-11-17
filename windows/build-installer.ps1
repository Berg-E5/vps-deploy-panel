# 构建 Windows 安装包 (.exe)
#
# 产出: dist\VPSDeployPanel-<版本>-Setup.exe
#
# 关键点:
#   * 自带 Python 运行时 —— 用户机器上不需要先装 Python
#   * 运行时钉死版本 + SHA-256 —— 供应链和面板其它项目一个口径
#   * 依赖从 PyPI 装成 wheel —— 目标机器不需要编译工具链
#   * 代码只取 app/ 与少量脚本, 不把整个仓库塞进安装包
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File windows/build-installer.ps1
param(
    [string]$OutputDir = 'dist',
    [switch]$SkipRuntimeDownload   # 复用已下载的运行时 (离线重打包)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

# ---------------------------------------------------------------- 固定版本
# python-build-standalone: 免安装、可再分发的 CPython。
# 版本与 SHA-256 必须同时改 —— 只改版本号会让校验失效。
$PythonVersion = '3.12.16'
$PythonBuild = '20261110'
$PythonArchive = "cpython-$PythonVersion+$PythonBuild-x86_64-pc-windows-msvc-install_only.tar.gz"
$PythonSha256 = 'e23fe5b16926de1d81661b1a97352e89fb167549c55a6825796ccd0f32ec7f1b'
$PythonUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/$PythonBuild/$([uri]::EscapeDataString($PythonArchive))"

$stage = Join-Path $root 'windows\build'
$cache = Join-Path $root 'windows\build\.cache'
$dist = Join-Path $root $OutputDir

function Say([string]$message) { Write-Host "[winpkg] $message" }

# ---------------------------------------------------------------- 1. 运行时
New-Item -ItemType Directory -Force -Path $stage, $cache, $dist | Out-Null

$archive = Join-Path $cache $PythonArchive
if (-not (Test-Path $archive) -or $SkipRuntimeDownload) {
    if ($SkipRuntimeDownload -and (Test-Path $archive)) {
        Say "复用已下载的运行时"
    } else {
        Say "下载 Python 运行时 ($PythonVersion) ..."
        $previous = $ProgressPreference
        $ProgressPreference = 'SilentlyContinue'
        try {
            Invoke-WebRequest -Uri $PythonUrl -OutFile $archive -UseBasicParsing
        } finally {
            $ProgressPreference = $previous
        }
    }
}

# SHA-256 必须匹配 —— 换版本号就一定要同时换这里的哈希
Say '校验运行时 SHA-256 ...'
$actual = (Get-FileHash -Path $archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $PythonSha256) {
    throw "运行时校验失败: 期望 $PythonSha256, 实际 $actual"
}

$pythonRoot = Join-Path $stage 'runtime'
if (Test-Path $pythonRoot) { Remove-Item $pythonRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $pythonRoot | Out-Null
Say '解压运行时 ...'
# 用 Python 的 tarfile 解压, 不用系统自带的 tar.exe —— 它在部分 Windows 上
# 会因为权限或路径策略直接失败, 而这里必须每次都能复现同样的结果。
$extract = @'
import sys, tarfile
archive, dest = sys.argv[1], sys.argv[2]
with tarfile.open(archive, "r:gz") as tf:
    # python3.14+ 提供数据过滤, 但这里只要确定性: 直接解全部
    tf.extractall(dest, filter="data")
print("extracted")
'@
$extractFile = Join-Path $stage '_extract.py'
Set-Content -Path $extractFile -Value $extract -Encoding UTF8
# 找一台能跑的 Python 来做解压 (构建机上本来就得有 Python 才能装依赖)
$buildPython = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    $probe = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $probe) { continue }
    try {
        $null = & $candidate -c 'import sys; sys.exit(0)' 2>$null
        if ($LASTEXITCODE -eq 0) { $buildPython = $candidate; break }
    } catch { continue }
}
if (-not $buildPython) { throw '构建机上找不到可用的 Python (python / python3 / py)' }
& $buildPython $extractFile $archive $pythonRoot
if ($LASTEXITCODE -ne 0) { throw '运行时解压失败' }
$pythonExe = Join-Path $pythonRoot 'python\python.exe'
if (-not (Test-Path $pythonExe)) { throw "运行时里没有 python.exe: $pythonExe" }

# ---------------------------------------------------------------- 2. 依赖
Say '安装 Python 依赖 (预编译 wheel) ...'
& $pythonExe -m pip install --quiet --disable-pip-version-check --no-warn-script-location `
    --only-binary=:all: `
    -r (Join-Path $root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败' }

# 用文件传参, 避免 PowerShell 把 -c 里的引号吃掉 (中文提示会变成变量名)
$verifyFile = Join-Path $stage '_verify_deps.py'
Set-Content -Path $verifyFile -Encoding UTF8 -Value @'
import fastapi, uvicorn, pydantic, httpx, paramiko, keyring
print("deps ok")
'@
& $pythonExe $verifyFile
if ($LASTEXITCODE -ne 0) { throw '依赖导入校验失败' }

# 运行时里的测试文件和缓存没必要进安装包
foreach ($junk in @('Lib\test', 'Lib\idlelib', 'Lib\tkinter', 'Lib\ensurepip')) {
    $path = Join-Path $pythonRoot "python\$junk"
    if (Test-Path $path) { Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue }
}
Get-ChildItem -Path (Join-Path $pythonRoot 'python\Lib\site-packages') -Directory -Filter '*.dist-info' |
    ForEach-Object {
        $tests = Join-Path $_.FullName 'tests'
        if (Test-Path $tests) { Remove-Item $tests -Recurse -Force -ErrorAction SilentlyContinue }
    }
# 调试符号对运行没用, 但白白占几十 MB
Get-ChildItem -Path $pythonRoot -Filter '*.pdb' -Recurse -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- 3. 应用代码
$appStage = Join-Path $stage 'app'
if (Test-Path $appStage) { Remove-Item $appStage -Recurse -Force }
Copy-Item -Path (Join-Path $root 'app') -Destination $appStage -Recurse
# 源码目录里的缓存不进包
Get-ChildItem -Path $appStage -Directory -Filter '__pycache__' -Recurse |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

Copy-Item -Path (Join-Path $root 'windows\launcher.pyw') -Destination $stage -Force
Copy-Item -Path (Join-Path $root 'windows\PanelState.ps1') -Destination $stage -Force
Copy-Item -Path (Join-Path $root 'windows\Uninstall.ps1') -Destination $stage -Force
Copy-Item -Path (Join-Path $root 'requirements.txt') -Destination $stage -Force
Copy-Item -Path (Join-Path $root 'LICENSE') -Destination $stage -Force
Copy-Item -Path (Join-Path $root 'README.md') -Destination $stage -Force

# 图标: 与界面里的品牌符号一致 (⬢ + 同一套渐变)
Say '生成安装包图标 ...'
# 图标生成器只用标准库, 不依赖 Pillow —— CI 和干净构建机都能跑
& $buildPython (Join-Path $root 'windows\make-icon.py') (Join-Path $stage 'icon.ico')
if ($LASTEXITCODE -ne 0) { throw '图标生成失败' }

# ---------------------------------------------------------------- 4. 打包
$iscc = Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    )
    $iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) { throw '找不到 Inno Setup 编译器 (ISCC.exe)。请先安装: winget install JRSoftware.InnoSetup' }

Say '编译安装包 ...'
$iss = Join-Path $root 'windows\installer.iss'
& $iscc $iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 编译失败 (退出码 $LASTEXITCODE)" }

$setup = Get-ChildItem -Path $dist -Filter '*Setup.exe' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $setup) { throw '没有生成安装包' }
Say "完成: $($setup.FullName) ($([math]::Round($setup.Length / 1MB, 1)) MB)"
