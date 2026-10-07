<#
.SYNOPSIS
    Optionally start Teams Presence -> BUSY Bar automatically at logon.

.DESCRIPTION
    Registers a Windows Scheduled Task that launches the presence loop when you
    log in. This is entirely optional - running `python main.py` by hand works
    exactly the same way.

    No administrator rights are needed. The task runs as you, inside your
    session, which it must do: presence detection reads per-user registry keys
    that only exist in your own session.

    By default it runs silently via pythonw.exe and logs to busy-bar.log.
    Remove it again with uninstall-task.ps1.

.PARAMETER ShowWindow
    Run in a visible console window instead, so you can watch it live.
    Useful while testing; there is no log file in this mode.

.PARAMETER TaskName
    Override the scheduled task name.

.EXAMPLE
    .\install-task.ps1

.EXAMPLE
    .\install-task.ps1 -ShowWindow
#>
[CmdletBinding()]
param(
    [switch]$ShowWindow,
    [string]$TaskName = "BUSY Bar Teams Presence"
)

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot

if ($ShowWindow) {
    $interpreter = Join-Path $root ".venv\Scripts\python.exe"
    $target      = Join-Path $root "main.py"
} else {
    $interpreter = Join-Path $root ".venv\Scripts\pythonw.exe"
    $target      = Join-Path $root "run_hidden.pyw"
}

if (-not (Test-Path $interpreter)) {
    Write-Host "Not found: $interpreter" -ForegroundColor Red
    Write-Host ""
    Write-Host "Create the virtual environment first:"
    Write-Host "    python -m venv .venv"
    Write-Host "    .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

if (-not (Test-Path $target)) {
    Write-Host "Not found: $target" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $root ".env"))) {
    Write-Warning "No .env in $root - copy .env.example to .env and set BUSY_BAR_LAN_TOKEN, or the task will fail at startup."
}

$action = New-ScheduledTaskAction -Execute $interpreter -Argument "`"$target`"" -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"

# StartWhenAvailable covers a missed logon trigger; the restart settings cover
# the bar being briefly unreachable. No time limit - this is meant to run all day.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -DontStopOnIdleEnd `
    -StartWhenAvailable `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -RestartCount 3 `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

# Limited run level: this needs no elevation, and must stay in the interactive
# user session to see the per-user presence signals.
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Replacing the existing '$TaskName' task."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Mirrors Microsoft Teams presence onto a BUSY Bar." | Out-Null

Write-Host ""
Write-Host "Installed '$TaskName'." -ForegroundColor Green
Write-Host "  runs    : $interpreter"
Write-Host "  script  : $target"
if ($ShowWindow) {
    Write-Host "  output  : visible console window"
} else {
    Write-Host "  output  : $(Join-Path $root 'busy-bar.log')"
}
Write-Host ""
Write-Host "Start it now without logging out:"
Write-Host "    Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Stop it:"
Write-Host "    Stop-ScheduledTask -TaskName '$TaskName'"
Write-Host "Remove it:"
Write-Host "    .\uninstall-task.ps1"