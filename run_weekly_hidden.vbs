' Hidden launcher for the weekly report task - keeps no console window. ASCII only.
Set sh = CreateObject("WScript.Shell")
sh.Run """C:\Users\user\Desktop\dev\youtube generator\run_weekly.cmd""", 0, True
