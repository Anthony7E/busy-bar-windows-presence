<#
.SYNOPSIS
    Remove the scheduled task created by install-task.ps1.

.DESCRIPTION
    Stops the presence loop if it is running and unregisters the task. Nothing
    else is touched - the project, the .env file and the virtual environment
    stay put, and `python main.py` keeps working by hand.

.PARAMETER TaskName
    Override the scheduled task name. Must match what install-task.ps1 used.

.EXAMPLE
    .\uninstall-task.ps1
#>
[CmdletBinding()]
param(
    [string]$TaskName = "BUSY Bar Teams Presence"
)

$ErrorActionPreference = "Stop"

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Host "No task named '$TaskName' is registered. Nothing to remove."
    return
}

if ($task.State -eq "Running") {
    Write-Host "Stopping '$TaskName'."
    Stop-ScheduledTask -TaskName $TaskName
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

Write-Host "Removed '$TaskName'." -ForegroundColor Green
Write-Host ""
Write-Host "The bar may still be showing your last status. To clear it:"
Write-Host "    .venv\Scripts\python main.py"
Write-Host "then press Ctrl+C - shutdown stops the BUSY session."