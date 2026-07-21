# youtube-generator

A local, end-to-end pipeline that produces short, dialogue-free "immersive scene" videos (rain window, campfire, ocean aerial, etc.) for YouTube Shorts — from AI video/audio generation to QC and (once the channel's API audit passes) automated upload.

## What it does

- **Scene video generation** — `pipeline/generate_video.py` runs local Wan 2.2 TI2V-5B (text-to-video, via `diffusers`) to produce a short vertical clip per scene; `pipeline/generate_video_i2v.py` offers an image-to-video variant of the same scene. An older SDXL-image + Ken Burns path (`pipeline/generate_images.py` + `pipeline/assemble.py`) is kept as a fallback.
- **Seamless looping** — `pipeline/loop_assemble.py` extends a short generated clip into a full-length short via self-crossfade looping (no visible seams), instead of a simple freeze/zoom.
- **AI ambient audio** — `pipeline/make_ambient_ai.py` generates unique ambience per video with local Stable Audio Open 1.0; `pipeline/make_ambient.py` is a $0 procedural (ffmpeg noise-shaping) fallback.
- **QC gate** — `pipeline/qc_check.py` verifies resolution, duration, stream layout, and loudness with ffmpeg before a video is allowed into the upload queue.
- **Daily production + upload queue** — `pipeline/produce_daily.py` runs the full pick-topic → generate → assemble → QC → queue flow; `pipeline/upload_queue.py` uploads queued videos via the YouTube Data API, gated so it only touches real videos once `pipeline/pool/config.json`'s `upload_privacy` is `"public"` (i.e. after the channel's compliance audit passes).
- **One-time OAuth + smoke test** — `pipeline/yt_auth.py` performs the one-time OAuth authorization; `pipeline/yt_smoketest.py` validates the upload path with a throwaway file without ever touching the real queue.

## Project structure

```
pipeline/
  produce_daily.py       daily orchestrator: topic -> clip -> loop -> ambience -> QC -> queue
  generate_video.py       text-to-video scene generation (Wan 2.2 TI2V-5B)
  generate_video_i2v.py   image-to-video variant
  generate_images.py      SDXL image generation (fallback path)
  assemble.py             images + audio -> Ken Burns mp4 (fallback path)
  loop_assemble.py        clip -> seamless-looping short
  make_ambient_ai.py      AI ambient audio (Stable Audio Open)
  make_ambient.py         procedural ambient audio (ffmpeg, fallback)
  qc_check.py             resolution/duration/loudness QC gate
  upload_queue.py         YouTube Data API uploader (privacy-gated)
  yt_auth.py              one-time OAuth authorization
  yt_smoketest.py         throwaway-file API upload smoke test
  pool/                   config.json (style/prompts/gates), state.json (rotation), topics.json
  scenes/                 sample scene definitions (JSON)
research/                  feasibility & policy write-ups (API limits, ToS/policy risk, production routes, local-gen model comparison)
run_daily.cmd               scheduled-task entry point (produce -> upload, logs to output/queue/scheduler.log)
run_daily_hidden.vbs        hidden launcher so the scheduled console window can't be closed by accident
ASSESSMENT.md                full feasibility assessment and workflow design (Chinese)
SETUP-YOUTUBE-API.md         user-facing steps to enable API upload (Chinese)
COWORK-RUNBOOK.md            runbook for an agent to do the Google Cloud/OAuth setup (Chinese)
```

`output/`, `secrets/`, and local venv/model-weight directories are not checked in (generated data, credentials, and large binaries).

## How to run

Requires a Python virtualenv with `torch` (CUDA build matching your GPU), `diffusers`, `soundfile`, `google-api-python-client`, `google-auth-oauthlib`, and `ffmpeg` available on `PATH` (no `requirements.txt` is checked in — these are the packages actually imported under `pipeline/`). Video/audio generation is compute-heavy and expects a CUDA GPU.

```bash
# generate + assemble + QC one day's video, add it to the queue
python pipeline/produce_daily.py [--topic <id>] [--target-sec N] [--dry-run]

# check a finished video against the QC gate manually
python pipeline/qc_check.py output/queue/<date>-<topic>/final.mp4

# upload queued videos (only proceeds once upload_privacy == "public")
python pipeline/upload_queue.py --max 1 [--dry-run]
```

Before the uploader can authenticate, complete the one-time Google Cloud / OAuth setup described in `SETUP-YOUTUBE-API.md`, then run `python pipeline/yt_auth.py` once to write `secrets/token.json`.

## Scheduling

A Windows Task Scheduler entry runs `run_daily_hidden.vbs` (a hidden launcher, so the console window can't be closed by accident), which invokes `run_daily.cmd`: it `cd`s into the project root and runs `pipeline/produce_daily.py` followed by `pipeline/upload_queue.py --max 1`, appending timestamped output to `output/queue/scheduler.log` (see `COWORK-RUNBOOK.md` for the full daily-schedule background).

## License

MIT — see `LICENSE`.
