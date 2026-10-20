"""Daily lofi short producer: pick topic -> master clip -> I2V motion variants
-> shuffled seamless assembly -> lofi music + ambience mix -> QC -> queue.

Output lands in output/queue/<date>-<topic>/ with final mp4 + metadata.json.
State (rotation, seeds) lives in pipeline/pool/state.json.

Usage: python produce_daily.py [--topic <id>] [--target-sec N] [--dry-run] [--preview]

Length is `loop_units` (config.json) repeats of the ~8.5 s loop unit; --target-sec
overrides it with the old "repeat until ~N seconds" behaviour. --preview writes to
output/preview/ and leaves state.json and output/queue/ untouched.
"""
import argparse
import datetime
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metadata as md  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "pipeline" / "pool"
PY = sys.executable
XF = 1.5
SEAM_FADE = 0.25      # afade in/out so Shorts auto-replay has no click at the seam
GPU_NEED_MB = 12000    # T2V wants nearly the whole 16 GB card
# This job runs last: it only starts once the whole machine is idle, otherwise it
# keeps waiting (2026-10-21: it started next to an RL training run and a 6-worker
# validation job, filled VRAM and pushed RAM into compression).
IDLE_CHECK_MIN = 15    # re-check interval while the machine is busy
IDLE_DEADLINE = "20:30"  # last start; a run (~20 min, 60 min cap) ends before lab-slack-watch 21:30
NO_START = [("11:30", "13:00")]  # lab-slack-watch Meeting ASR at 12:30 needs ~7 GB VRAM
CPU_BUSY_PCT = 30      # system-wide CPU over a 60 s sample (idle desktop ~5-15 %)
RAM_FREE_GB = 16       # available RAM needed (T2V takes ~5 GB on top of what is in use)
OTHER_GPU_MB = 256     # another python holding this much VRAM = someone's training/inference
STEP_TIMEOUT_MIN = 30  # per-step hard cap (a normal full run is ~20 min)
GEN_TIMEOUT_MIN = 60   # T2V denoise cap; 6x slowdown means GPU contention


def done_already(p: Path) -> bool:
    return p.exists() and p.stat().st_size > 0


def run(cmd: list, timeout_min: float = STEP_TIMEOUT_MIN) -> subprocess.CompletedProcess:
    """Hard cap per step: a stalled child would otherwise hold RAM+VRAM
    indefinitely, so on timeout the whole process tree gets killed."""
    cmd = [str(c) for c in cmd]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = p.communicate(timeout=timeout_min * 60)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        p.communicate()
        raise RuntimeError(f"step timed out after {timeout_min} min (tree killed): {cmd[:3]}...")
    if p.returncode != 0:
        raise RuntimeError(f"step failed: {cmd[:3]}...\n{out[-800:]}\n{err[-800:]}")
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def duration_of(path: Path) -> float:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True, timeout=60)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def free_vram_mb() -> int:
    r = subprocess.run(["nvidia-smi", "--query-gpu=memory.free",
                        "--format=csv,noheader,nounits"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"nvidia-smi failed:\n{r.stderr[-400:]}")
    return int(r.stdout.strip().splitlines()[0])


def other_gpu_pythons(min_mb: int) -> list:
    """Python processes outside this run holding >= min_mb of dedicated VRAM.
    Under WDDM nvidia-smi reports N/A per process; the GPU Process Memory
    counter does not. If the counter is unavailable, rely on the other checks."""
    ps = (r"(Get-Counter '\GPU Process Memory(*)\Dedicated Usage').CounterSamples | "
          r"ForEach-Object { '{0} {1}' -f $_.InstanceName, [int64]$_.CookedValue }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return []
    if r.returncode != 0:
        return []
    used = {}
    for line in r.stdout.splitlines():
        m = re.match(r"pid_(\d+)_\S*\s+(\d+)$", line.strip())
        if m:  # one instance per adapter, so sum per pid
            used[int(m.group(1))] = used.get(int(m.group(1)), 0) + int(m.group(2))
    me = psutil.Process()
    mine = {me.pid, *(c.pid for c in me.children(recursive=True))}
    found = []
    for pid, b in used.items():
        if pid in mine or b < min_mb * 2**20:
            continue
        try:
            name = psutil.Process(pid).name()
        except psutil.Error:
            continue
        if name.lower().startswith("python"):
            found.append(f"{name} pid {pid} {b // 2**20} MiB")
    return found


def busy_reason() -> str | None:
    """None when the machine is idle enough to generate; else what is in the way."""
    try:  # a transient nvidia-smi failure must not end a 13 h wait
        free = free_vram_mb()
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as e:
        return f"nvidia-smi unavailable ({type(e).__name__})"
    if free < GPU_NEED_MB:
        return f"VRAM {free} MiB free < {GPU_NEED_MB} MiB"
    others = other_gpu_pythons(OTHER_GPU_MB)
    if others:
        return "GPU in use by " + ", ".join(others)
    avail = psutil.virtual_memory().available / 2**30
    if avail < RAM_FREE_GB:
        return f"RAM {avail:.1f} GB available < {RAM_FREE_GB} GB"
    cpu = psutil.cpu_percent(interval=60)
    if cpu >= CPU_BUSY_PCT:
        return f"CPU {cpu:.0f}% >= {CPU_BUSY_PCT}%"
    return None


def today_at(hhmm: str) -> datetime.datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime.datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)


LAST_BUSY = ""  # last reason seen by wait_until_idle (for the failure note)


def wait_until_idle() -> bool:
    """This job runs last. While anything else uses the GPU, CPU or RAM, or a
    no-start window is on, wait; at IDLE_DEADLINE give up for the day cleanly.
    Generating anyway grinds ~6x slower and drags the whole machine down
    (2026-07-23 game left on overnight, 2026-10-21 RL training + validation)."""
    global LAST_BUSY
    deadline = today_at(IDLE_DEADLINE)
    while True:
        now = datetime.datetime.now()
        window = next((e for s, e in NO_START if today_at(s) <= now < today_at(e)), None)
        reason = f"no-start window until {window}" if window else busy_reason()
        if reason is None:
            return True
        LAST_BUSY = reason
        print(f"{now:%H:%M} waiting: {reason}", flush=True)
        if now + datetime.timedelta(minutes=IDLE_CHECK_MIN) > deadline:
            return False
        time.sleep(IDLE_CHECK_MIN * 60)


def pick_topic(topics: list, state: dict, forced: str | None) -> dict:
    if forced:
        return next(t for t in topics if t["id"] == forced)
    want = "water" if state.get("last_category") == "fire" else "fire"
    used = state.get("used", [])
    pool = [t for t in topics if t["category"] == want]
    fresh = [t for t in pool if t["id"] not in used] or pool
    return fresh[0]


def build_loop_unit(clip: Path, out: Path) -> None:
    T = duration_of(clip)
    offset = T - XF
    run(["ffmpeg", "-y", "-i", clip, "-i", clip,
         "-filter_complex",
         f"[0:v][1:v]xfade=transition=fade:duration={XF}:offset={offset:.3f},"
         f"trim=start={offset:.3f}:end={offset + T - XF:.3f},setpts=PTS-STARTPTS[v]",
         "-map", "[v]", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
         "-pix_fmt", "yuv420p", out])


def slow_motion(clip: Path, out: Path) -> None:
    """Optical-flow interpolate 2x and half the speed: 5s clip -> 10s
    continuous take. One generation = zero scene drift, zero joints."""
    run(["ffmpeg", "-y", "-i", clip,
         "-vf", "minterpolate=fps=48:mi_mode=mci:mc_mode=aobmc:me_mode=bidir,"
                "setpts=2*PTS,fps=24",
         "-c:v", "libx264", "-preset", "medium", "-crf", "16",
         "-pix_fmt", "yuv420p", out])


def assemble_repeat(unit: Path, audio: Path, out: Path, reps: int) -> float:
    unit_len = duration_of(unit)
    reps = max(1, reps)
    total = reps * unit_len
    run(["ffmpeg", "-y", "-stream_loop", str(reps - 1), "-i", unit,
         "-stream_loop", "-1", "-i", audio,
         "-vf", "scale=1080:1920:flags=lanczos",
         "-af", f"afade=t=in:st=0:d={SEAM_FADE},afade=t=out:st={total - SEAM_FADE:.3f}:d={SEAM_FADE}",
         "-t", f"{total:.3f}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", out])
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default=None)
    ap.add_argument("--target-sec", type=float, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--preview", action="store_true",
                    help="write to output/preview/, do not touch state.json or the queue")
    args = ap.parse_args()

    cfg = json.loads((POOL / "config.json").read_text(encoding="utf-8"))
    topics = json.loads((POOL / "topics.json").read_text(encoding="utf-8"))
    state_file = POOL / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}

    topic = pick_topic(topics, state, args.topic)
    counter = state.get("counter", 0)
    seed = counter * 13 + 7
    loop_units = md.get_loop_units(cfg)
    date = datetime.date.today().isoformat()
    if args.preview:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        work = ROOT / "output" / "preview" / f"{stamp}-{topic['id']}"
    else:
        work = ROOT / "output" / "queue" / f"{date}-{topic['id']}"

    if args.dry_run:
        print(json.dumps({"topic": topic["id"], "seed": seed, "workdir": str(work)}, indent=2))
        return
    work.mkdir(parents=True, exist_ok=True)
    try:  # lowest CPU priority; the T2V and ffmpeg children inherit it
        psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
    except Exception:
        pass
    master = work / "clip_master.mp4"
    music, ambient = work / "music.m4a", work / "ambient.m4a"
    if not all(done_already(p) for p in (master, music, ambient)):
        started = time.time()
        if not wait_until_idle():
            if args.preview:  # previews must not touch the real queue log or failure note
                sys.exit(2)
            with open(ROOT / "output" / "queue" / "production.log", "a", encoding="utf-8") as f:
                f.write(f"{date} {topic['id']} SKIPPED gpu busy\n")
            waited = round((time.time() - started) / 60)
            try:  # human-readable reason for scripts/daily_status.py (never block the exit)
                (ROOT / "data").mkdir(exist_ok=True)
                (ROOT / "data" / "last-failure-reason.txt").write_text(
                    f"{date}\n"
                    f"\u96fb\u8166\u5fd9\u788c\uff1a{LAST_BUSY}\uff0c\u5df2\u7b49 {waited}"
                    f" \u5206\u9418\uff0c\u5230 {IDLE_DEADLINE} \u90fd\u6c92\u6709\u7a7a\u6a94\n",
                    encoding="utf-8")
            except Exception:
                pass
            sys.exit(2)
    style = cfg["style_suffixes"][cfg["channel_style"]]
    video_prompt = f"{topic['subject']}, {style}"

    # 1) master clip (T2V)
    scene = {"id": f"{date}-{topic['id']}", "video_prompt": video_prompt,
             "negative_prompt": cfg["video_negative_prompt"]}
    scene_file = work / "scene.json"
    scene_file.write_text(json.dumps(scene, ensure_ascii=False), encoding="utf-8")
    if not done_already(master):
        run([PY, ROOT / "pipeline" / "generate_video.py", scene_file,
             "--seconds", cfg["clip_seconds"], "--steps", 35, "--seed", seed, "--out", master],
            timeout_min=GEN_TIMEOUT_MIN)
    print(f"[1/5] master clip done", flush=True)

    # 2) 2x slow motion -> 10s continuous take (no joints, no drift)
    slowmo = work / "slowmo.mp4"
    if not done_already(slowmo):
        slow_motion(master, slowmo)
    print(f"[2/5] slow-motion done", flush=True)

    # 3) audio: lofi music (main) + scene ambience (bed), mixed
    music_prompt = cfg["music_prompts"][counter % len(cfg["music_prompts"])]
    music_scene = {"id": scene["id"], "audio_prompt": music_prompt,
                   "audio_negative_prompt": cfg["music_negative_prompt"],
                   "audio": {"gain_db": cfg["music_gain_db"]}}
    ambient_scene = {"id": scene["id"], "audio_prompt": topic["ambient_prompt"],
                     "audio": {"gain_db": cfg["ambient_gain_db"]}}
    (work / "music_scene.json").write_text(json.dumps(music_scene), encoding="utf-8")
    (work / "ambient_scene.json").write_text(json.dumps(ambient_scene), encoding="utf-8")
    mixed = work / "mix.m4a"
    if not done_already(music):
        run([PY, ROOT / "pipeline" / "make_ambient_ai.py", work / "music_scene.json",
             "--seconds", 47, "--seed", seed, "--out", music])
    if not done_already(ambient):
        run([PY, ROOT / "pipeline" / "make_ambient_ai.py", work / "ambient_scene.json",
             "--seconds", 47, "--seed", seed + 1, "--out", ambient])
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", music, "-stream_loop", "-1", "-i", ambient,
         "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a]",
         "-map", "[a]", "-t", "47", "-c:a", "aac", "-b:a", "160k", mixed])
    # seamless audio loop unit: self-crossfade tail into head (same idea as
    # the video loop) so repeats have no silence gap at the joint
    mix_loop = work / "mix_loop.m4a"
    mlen = duration_of(mixed)
    run(["ffmpeg", "-y", "-i", mixed, "-i", mixed,
         "-filter_complex",
         f"[0:a][1:a]acrossfade=d={XF},atrim=start={mlen - XF:.3f}:end={2 * (mlen - XF):.3f},"
         f"asetpts=PTS-STARTPTS[a]",
         "-map", "[a]", "-c:a", "aac", "-b:a", "160k", mix_loop])
    print(f"[3/5] audio done", flush=True)

    # 4) self-loop the take, repeat to target
    unit = work / "loop_unit.mp4"
    build_loop_unit(slowmo, unit)
    final = work / f"{scene['id']}.mp4"
    unit_len = duration_of(unit)
    if args.target_sec:  # legacy behaviour: repeat until ~N seconds
        loop_units = max(1, round(args.target_sec / unit_len))
    total = assemble_repeat(unit, mix_loop, final, loop_units)
    print(f"[4/5] assembled {total:.1f}s ({duration_of(slowmo):.1f}s continuous take)", flush=True)

    # 5) QC + metadata + state
    run([PY, ROOT / "pipeline" / "qc_check.py", final,
         "--loop-units", loop_units, "--unit-sec", unit_len, "--json-out", work / "qc.json"])
    taken = md.taken_titles(ROOT / "output" / "queue", md.channel_titles(ROOT))
    meta = {
        **md.build_metadata(topic, cfg["metadata_footer"], taken),
        "ai_disclosure": True,
        "topic_id": topic["id"], "seed": seed, "duration_sec": round(total, 1),
        "loop_units": loop_units,
        "created": date,
    }
    try:
        meta["motion_score"] = json.loads((work / "qc.json").read_text(encoding="utf-8"))["motion_score"]
    except (OSError, KeyError, ValueError):
        pass
    (work / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    if args.preview:
        print(f"[5/5] preview only (state and queue untouched): {final}", flush=True)
        return
    used = state.get("used", [])
    used.append(topic["id"])
    all_ids = {t["id"] for t in topics}
    if all_ids.issubset(set(used)):
        used = [topic["id"]]  # pool exhausted -> new rotation round
    state.update({"counter": counter + 1, "last_category": topic["category"], "used": used})
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    with open(ROOT / "output" / "queue" / "production.log", "a", encoding="utf-8") as f:
        f.write(f"{date} {topic['id']} seed={seed} dur={total:.1f}s OK\n")
    print(f"[5/5] queued: {final}", flush=True)


if __name__ == "__main__":
    main()
