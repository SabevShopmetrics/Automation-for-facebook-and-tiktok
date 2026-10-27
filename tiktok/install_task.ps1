# Registers a Windows task that starts the TikTok tool at every Windows logon.
# Run once: powershell -ExecutionPolicy Bypass -File install_task.ps1
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = & python -c "import sys; print(sys.executable)"
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"
if (Test-Path $pythonw) { $python = $pythonw }  # no console window
$action = New-ScheduledTaskAction -Execute $python -Argument "run.py serve" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 0)
Register-ScheduledTask -TaskName "TikTok tool" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName "TikTok tool"
Write-Host "OK: the TikTok tool runs now and at every Windows logon: http://localhost:8765"
