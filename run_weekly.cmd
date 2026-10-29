@echo off
rem Weekly YouTube channel report to Discord - ASCII only, absolute paths
cd /d "C:\Users\user\Desktop\dev\youtube generator"
if not exist "output\queue" mkdir "output\queue"
echo [%date% %time%] weekly report start >> "output\queue\weekly.log"
"C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "scripts\weekly_report.py" >> "output\queue\weekly.log" 2>&1
set WEEKLY_RC=%errorlevel%
echo [%date% %time%] weekly report end (exitcode %WEEKLY_RC%) >> "output\queue\weekly.log"
if not "%WEEKLY_RC%"=="0" "C:\Users\user\Desktop\dev\youtube generator\.venv\Scripts\python.exe" "scripts\daily_status.py" fail weekly "weekly_report.py failed (exit %WEEKLY_RC%), see output\queue\weekly.log (exit 2 = re-run: scripts\weekly_report.py --auth)" >> "output\queue\weekly.log" 2>&1
exit /b %WEEKLY_RC%
