"""Daily lofi short producer: pick topic -> master clip -> I2V motion variants
-> shuffled seamless assembly -> lofi music + ambience mix -> QC -> queue.

Output lands in output/queue/<date>-<topic>/ with final mp4 + metadata.json.
State (rotation, seeds) lives in pipeline/pool/state.json.

Usage: python produce_daily.py [--topic <id>] [--target-sec N] [--dry-run]
"""
import argparse
import datetime
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "pipeline" / "pool"
PY = sys.executable
XF = 1.5


def done_already(p: Path) -> bool:
    return p.exists() and p.stat().st_size > 0


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"step failed: {cmd[:3]}...\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
    return r


def duration_of(path: Path) -> float:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


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


def assemble_repeat(unit: Path, audio: Path, out: Path, target: float) -> float:
    unit_len = duration_of(unit)
    reps = max(1, round(target / unit_len))
    total = reps * unit_len
    run(["ffmpeg", "-y", "-stream_loop", str(reps - 1), "-i", unit,
         "-stream_loop", "-1", "-i", audio,
         "-vf", "scale=1080:1920:flags=lanczos",
         "-t", f"{total:.3f}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", out])
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default=None)
    ap.add_argument("--target-sec", type=float, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = json.loads((POOL / "config.json").read_text(encoding="utf-8"))
    topics = json.loads((POOL / "topics.json").read_text(encoding="utf-8"))
    state_file = POOL / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}

    topic = pick_topic(topics, state, args.topic)
    counter = state.get("counter", 0)
    seed = counter * 13 + 7
    target = args.target_sec or cfg["target_seconds"]
    date = datetime.date.today().isoformat()
    work = ROOT / "output" / "queue" / f"{date}-{topic['id']}"

    if args.dry_run:
        print(json.dumps({"topic": topic["id"], "seed": seed, "workdir": str(work)}, indent=2))
        return
    work.mkdir(parents=True, exist_ok=True)
    style = cfg["style_suffixes"][cfg["channel_style"]]
    video_prompt = f"{topic['subject']}, {style}"

    # 1) master clip (T2V)
    scene = {"id": f"{date}-{topic['id']}", "video_prompt": video_prompt,
             "negative_prompt": cfg["video_negative_prompt"]}
    scene_file = work / "scene.json"
    scene_file.write_text(json.dumps(scene, ensure_ascii=False), encoding="utf-8")
    master = work / "clip_master.mp4"
    if not done_already(master):
        run([PY, ROOT / "pipeline" / "generate_video.py", scene_file,
             "--seconds", cfg["clip_seconds"], "--steps", 35, "--seed", seed, "--out", master])
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
    music, ambient, mixed = work / "music.m4a", work / "ambient.m4a", work / "mix.m4a"
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
    total = assemble_repeat(unit, mix_loop, final, target)
    print(f"[4/5] assembled {total:.1f}s ({duration_of(slowmo):.1f}s continuous take)", flush=True)

    # 5) QC + metadata + state
    run([PY, ROOT / "pipeline" / "qc_check.py", final,
         "--min-sec", target * 0.8, "--max-sec", target * 1.3])
    meta = {
        "title": topic["title"],
        "description": f"{topic['title']}\n\nSit back, relax and enjoy.\n\n"
                       f"{cfg['metadata_footer']}",
        "tags": ["lofi", "ambience", "relaxing", "asmr", "chill", topic["category"]],
        "ai_disclosure": True,
        "topic_id": topic["id"], "seed": seed, "duration_sec": round(total, 1),
        "created": date,
    }
    (work / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
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
