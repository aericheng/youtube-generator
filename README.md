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
