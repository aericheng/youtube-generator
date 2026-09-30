# youtube generator — ambient lofi shorts pipeline

Automated daily production of ambient lofi YouTube shorts (Wan 2.2 T2V video +
Stable Audio Open music/ambience), fully local on one RTX 5070 Ti.

## Daily chain

`LofiShortsDaily` (Windows Task Scheduler, 03:30)
→ `run_daily_hidden.vbs` → `run_daily.cmd`
→ `pipeline/produce_daily.py` (topic pick → T2V master clip → slow-motion →
music + ambience mix → loop assembly → QC → queue)
→ `pipeline/upload_queue.py --max 1`

Output lands in `output/queue/<date>-<topic>/` (final mp4 + `metadata.json`).
Logs: `output/queue/scheduler.log` (full run output),
`output/queue/production.log` (one line per day: OK or SKIPPED).

## GPU guard & watchdog

Added after the 2026-07-23 incident: the 03:30 run collided with a game left
running overnight — denoise ground at 109 s/it (normal ~20), crashed after step
1/35, and the leftover contention dragged the whole machine down for hours.

- **VRAM pre-check** — `produce_daily.py` checks free VRAM via `nvidia-smi`
  before any GPU step. Below `GPU_NEED_MB` (12000 MiB) it re-checks
  `GPU_TRIES` (5) times every `GPU_WAIT_MIN` (15) minutes, then skips the day:
  writes `<date> <topic> SKIPPED gpu busy` to `production.log` and exits 2.
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
