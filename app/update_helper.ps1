param(
    [Parameter(Mandatory = $true)][string]$InstallerPath,
    [Parameter(Mandatory = $true)][string]$InstallDir,
    [Parameter(Mandatory = $true)][string]$LogPath,
    [int]$DelaySeconds = 3
)

$ErrorActionPreference = 'Stop'
$normalizedInstall = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd('\')
$installerLog = Join-Path $env:TEMP ("vpsdeploy-inno-{0}.log" -f $PID)

function Write-UpdateLog([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Get-PanelProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and (
            ($_.ExecutablePath -and $_.ExecutablePath.StartsWith(
                $normalizedInstall, [System.StringComparison]::OrdinalIgnoreCase)) -or
            ($_.CommandLine -and $_.CommandLine.Contains($normalizedInstall))
        )
    }
}

$installerSucceeded = $false
try {
    Write-UpdateLog "Updater helper started; waiting $DelaySeconds seconds"
    Start-Sleep -Seconds $DelaySeconds

    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        $processes = @(Get-PanelProcesses)
        if ($processes.Count -eq 0) {
            break
        }
        foreach ($process in $processes) {
            Write-UpdateLog ("Stopping PID {0}: {1}" -f $process.ProcessId, $process.Name)
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 500
    }

    $remaining = @(Get-PanelProcesses)
    if ($remaining.Count -ne 0) {
        throw "Panel processes are still running"
    }

    $installer = Start-Process -FilePath $InstallerPath -ArgumentList @(
        '/VERYSILENT',
        '/SUPPRESSMSGBOXES',
        '/NORESTART',
        '/CLOSEAPPLICATIONS',
        '/SP-',
        "/LOG=$installerLog"
    ) -Wait -PassThru
    Write-UpdateLog ("Installer exit code: {0}" -f $installer.ExitCode)
    if ($installer.ExitCode -ne 0) {
        throw ("Installer failed with exit code {0}; log: {1}" -f $installer.ExitCode, $installerLog)
    }
    $installerSucceeded = $true
}
catch {
    Write-UpdateLog ("Update failed: {0}" -f $_.Exception.Message)
}
finally {
    Remove-Item -LiteralPath $InstallerPath -Force -ErrorAction SilentlyContinue

    $desktop = Join-Path $normalizedInstall 'VPSDeployPanel.exe'
    $pythonw = Join-Path $normalizedInstall 'runtime\python\pythonw.exe'
    $launcher = Join-Path $normalizedInstall 'launcher.pyw'
    if (Test-Path -LiteralPath $desktop -PathType Leaf) {
        Start-Process -FilePath $desktop -WorkingDirectory $normalizedInstall
        Write-UpdateLog "Desktop client restarted"
    }
    elseif ((Test-Path -LiteralPath $pythonw -PathType Leaf) -and
            (Test-Path -LiteralPath $launcher -PathType Leaf)) {
        $launcherArgument = '"' + $launcher + '"'
        Start-Process -FilePath $pythonw -ArgumentList $launcherArgument `
            -WorkingDirectory $normalizedInstall
        Write-UpdateLog "Browser client restarted"
    }
    else {
        Write-UpdateLog "Update finished but no restart entry point was found"
    }

    if (-not $installerSucceeded) {
        exit 1
    }
}
