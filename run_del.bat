echo Starting batch file > C:\Users\ROG\AppData\Local\Temp\task.log
powershell -Command "Remove-Item -Path C:\Users\ROG\Documents\app.lock -Force" >> C:\Users\ROG\AppData\Local\Temp\task.log 2>&1
echo Done file1 >> C:\Users\ROG\AppData\Local\Temp\task.log
powershell -Command "Remove-Item -Path C:\Users\ROG\Documents\ComfyUI\.venv\.lock -Force" >> C:\Users\ROG\AppData\Local\Temp\task.log 2>&1
echo Done file2 >> C:\Users\ROG\AppData\Local\Temp\task.log
