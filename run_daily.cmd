@echo off
rem Daily lofi short production - ASCII only, absolute paths (Task Scheduler has minimal env)
cd /d "C:\Users\user\Desktop\dev\youtube generator"
set PATH=C:\Users\user\bin;%PATH%
if not exist "output\queue" mkdir "output\queue"
rem Rotate output/queue/scheduler.log output/queue/production.log (over 5 MB, keep 5) while no process holds it open; output must not go to the log itself.
"C:\Program Files\nodejs\node.exe" scripts\rotate-logs.js output/queue/scheduler.log output/queue/production.log >nul 2>&1
echo [%date% %time%] run start >> "output\queue\scheduler.log"
"C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "pipeline\produce_daily.py" >> "output\queue\scheduler.log" 2>&1
set PRODUCE_RC=%errorlevel%
echo [%date% %time%] produce end (exitcode %PRODUCE_RC%) >> "output\queue\scheduler.log"
if not "%PRODUCE_RC%"=="0" "C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "scripts\daily_status.py" fail produce "produce_daily.py failed (exit %PRODUCE_RC%), see output\queue\scheduler.log" >> "output\queue\scheduler.log" 2>&1
"C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "pipeline\upload_queue.py" >> "output\queue\scheduler.log" 2>&1
set UPLOAD_RC=%errorlevel%
echo [%date% %time%] run end (exitcode %UPLOAD_RC%) >> "output\queue\scheduler.log"
if not "%UPLOAD_RC%"=="0" "C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "scripts\daily_status.py" fail upload "upload_queue.py failed (exit %UPLOAD_RC%), see output\queue\scheduler.log" >> "output\queue\scheduler.log" 2>&1
if "%PRODUCE_RC%%UPLOAD_RC%"=="00" "C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "scripts\daily_status.py" ok >> "output\queue\scheduler.log" 2>&1
if not "%PRODUCE_RC%"=="0" exit /b %PRODUCE_RC%
exit /b %UPLOAD_RC%
