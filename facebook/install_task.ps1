# Registers a Windows task that runs the Facebook autopost every 10 minutes.
# Run once: powershell -ExecutionPolicy Bypass -File install_task.ps1
# Undo:     powershell -ExecutionPolicy Bypass -File uninstall_task.ps1
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = & python -c "import sys; print(sys.executable)"
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"
if (Test-Path $pythonw) { $python = $pythonw }  # no console window every 10 minutes
$action = New-ScheduledTaskAction -Execute $python -Argument "run.py run" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 365)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "Facebook autopost" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "OK: task 'Facebook autopost' runs every 10 minutes ($python)."
