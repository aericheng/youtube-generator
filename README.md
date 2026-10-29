# youtube generator — ambient lofi shorts pipeline

Automated daily production of ambient lofi YouTube shorts (Wan 2.2 T2V video +
Stable Audio Open music/ambience), fully local on one RTX 5070 Ti.

## Daily chain

`LofiShortsDaily` (Windows Task Scheduler, 07:00)
→ `run_daily_hidden.vbs` → `run_daily.cmd`
→ `pipeline/produce_daily.py` (topic pick → T2V master clip → slow-motion →
music + ambience mix → loop assembly → QC → queue)
→ `pipeline/upload_queue.py` (1 per run; 2 when more than 3 videos are waiting)

Output lands in `output/queue/<date>-<topic>/` (final mp4 + `metadata.json`).
Logs: `output/queue/scheduler.log` (full run output),
`output/queue/production.log` (one line per day: OK or SKIPPED).

## GPU guard & watchdog

Added after the 2026-07-23 incident: the 03:30 run collided with a game left
running overnight — denoise ground at 109 s/it (normal ~20), crashed after step
1/35, and the leftover contention dragged the whole machine down for hours.

- **Runs last (idle gate)** — added 2026-10-21 after the 07:00 run started next
  to an RL training run and a 6-worker validation job (VRAM full, RAM into
  compression). Before any GPU step `produce_daily.py` waits until the whole
  machine is idle: free VRAM ≥ `GPU_NEED_MB` (12000 MiB), no other python process
  holding ≥ `OTHER_GPU_MB` (256 MiB) of VRAM (read from the Windows
  `GPU Process Memory` counter), available RAM ≥ `RAM_FREE_GB` (16), CPU over a
  60 s sample < `CPU_BUSY_PCT` (30 %). It never starts inside `NO_START`
  (11:30–13:00, lab-slack-watch's 12:30 meeting ASR). Busy → re-check every
  `IDLE_CHECK_MIN` (15) minutes; no idle slot by `IDLE_DEADLINE` (20:30) → skip
  the day: writes `<date> <topic> SKIPPED gpu busy` to `production.log`, the
  reason to `data/last-failure-reason.txt`, and exits 2. The process sets itself
  to idle CPU priority (children inherit it), and the `LofiShortsDaily` task runs
  at priority 10 with a 16 h limit to cover the wait. Tests:
  `python tests/test_idle_gate.py`.
  The gate only decides when to start: a heavy job launched mid-run still
  competes with it until the step watchdog below.
- **Step watchdog** — every external step goes through `run()` with a hard
  timeout: `STEP_TIMEOUT_MIN` (30 min) default, `GEN_TIMEOUT_MIN` (60 min) for
  T2V; a normal full run is ~20 min total. On timeout the whole process tree
  is killed (`taskkill /F /T`) so nothing can hold RAM/VRAM indefinitely.

All knobs are constants at the top of `pipeline/produce_daily.py`.

## Re-running a skipped or failed day

`produce_daily.py` is resumable: run
`.venv\Scripts\python.exe pipeline\produce_daily.py` again the same day and it
continues from whatever artifacts already exist in the day's folder. A partial
folder can never upload: `upload_queue.py` only picks folders that have both
`metadata.json` and the final mp4.

## Weekly report

`LofiWeeklyReport` (Task Scheduler, Mondays 08:40) → `run_weekly_hidden.vbs` →
`run_weekly.cmd` → `scripts/weekly_report.py` posts one Discord message (same
webhook as the daily failure alerts) with four blocks: views and watch time of
the last 7 days (Analytics API `reports.query`, window = today-7 .. yesterday),
subscribers gained/lost, top 3 videos by views (titles via Data API
`videos.list`), and the run-log success rate (today-7 .. today from
`output/queue/scheduler.log`: scheduled runs, exitcode 0, produce OK, videos
uploaded). On success it writes `data/last-success-weekly`; on failure
`run_weekly.cmd` raises a `weekly` alert through `daily_status.py`. Output of
the task: `output/queue/weekly.log`.

**First time: authorize once by hand.** The token needs the
`yt-analytics.readonly` and `youtube.readonly` scopes (both are listed in
`pipeline/yt_auth.py`). If `secrets/token.json` was issued without them, the
report exits 2 and tells you to re-run the consent:

```
.venv\Scripts\python.exe scripts\weekly_report.py --auth
```

(equivalent to `pipeline/yt_auth.py`; a browser opens, pick the channel
account, then "Advanced" → continue, allow all scopes; token is rewritten to
`secrets/token.json`).

Dry run (prints the report and writes `data/weekly-report-<date>.md`, posts
nothing):

```
.venv\Scripts\python.exe scripts\weekly_report.py --dry-run          # real Analytics data
.venv\Scripts\python.exe scripts\weekly_report.py --dry-run --mock   # fixture views/subs, real run log
```

`--mock` is refused without `--dry-run`, so fixture data never reaches Discord.
Register the task (after authorizing):
`powershell -ExecutionPolicy Bypass -File scripts\register-weekly.ps1`.
