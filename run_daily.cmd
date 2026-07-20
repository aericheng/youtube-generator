@echo off
rem Daily lofi short production - ASCII only, absolute paths (Task Scheduler has minimal env)
cd /d "C:\Users\user\Desktop\dev\youtube generator"
set PATH=C:\Users\user\bin;%PATH%
if not exist "output\queue" mkdir "output\queue"
echo [%date% %time%] run start >> "output\queue\scheduler.log"
"C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "pipeline\produce_daily.py" >> "output\queue\scheduler.log" 2>&1
echo [%date% %time%] produce end (exitcode %errorlevel%) >> "output\queue\scheduler.log"
"C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "pipeline\upload_queue.py" --max 1 >> "output\queue\scheduler.log" 2>&1
echo [%date% %time%] run end (exitcode %errorlevel%) >> "output\queue\scheduler.log"
