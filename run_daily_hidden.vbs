' Hidden launcher for the daily production task - keeps no console window
' on the desktop so it cannot be closed by accident. ASCII only.
Set sh = CreateObject("WScript.Shell")
sh.Run """C:\Users\user\Desktop\dev\youtube generator\run_daily.cmd""", 0, True
