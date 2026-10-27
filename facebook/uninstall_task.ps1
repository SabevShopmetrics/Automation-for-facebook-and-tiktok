# Removes the every-10-minutes task (the opposite of install_task.ps1).
# Posts already scheduled stay in Facebook. To remove them: python run.py cancel all
Unregister-ScheduledTask -TaskName "Facebook autopost" -Confirm:$false
Write-Host "OK: task 'Facebook autopost' removed."
