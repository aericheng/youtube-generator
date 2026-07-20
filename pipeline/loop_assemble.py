"""Short clip -> seamless-looping vertical short with ambient audio.

Loop unit: crossfade the clip onto its own start, then trim to the segment
[offset, offset + (T - xf)] whose first and last frames coincide, so both
internal seams and the video's own end->start wrap are continuous. The unit
is repeated to reach the target length, upscaled to 1080x1920.

Usage: python loop_assemble.py <scene.json> [--clip <file>] [--audio <file>]
       [--out <file>] [--target-sec 25] [--xfade 1.0]
"""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path

W, H = 1080, 1920


def duration_of(path: Path) -> float:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--clip", default=None)
    ap.add_argument("--audio", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--target-sec", type=float, default=25.0)
    ap.add_argument("--xfade", type=float, default=1.0)
    args = ap.parse_args()

    scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    base = Path("output") / scene["id"]
    base.mkdir(parents=True, exist_ok=True)
    clip = Path(args.clip or base / "clip.mp4")
    audio = Path(args.audio or base / "ambient.m4a")
    out = Path(args.out or base / f"{scene['id']}.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    T = duration_of(clip)
    xf = args.xfade
    unit_len = T - xf
    reps = max(1, math.ceil(args.target_sec / unit_len))
    total = reps * unit_len

    # 1) build the loop unit: self-crossfade, keep [xf_offset, xf_offset+unit_len]
    unit = base / "loop_unit.mp4"
    offset = T - xf
    subprocess.run([
        "ffmpeg", "-y", "-i", str(clip), "-i", str(clip),
        "-filter_complex",
        f"[0:v][1:v]xfade=transition=fade:duration={xf}:offset={offset:.3f},"
        f"trim=start={offset:.3f}:end={offset + unit_len:.3f},setpts=PTS-STARTPTS[v]",
        "-map", "[v]", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
        "-pix_fmt", "yuv420p", str(unit),
    ], check=True, capture_output=True)

    # 2) repeat the unit, upscale to 1080x1920, mux ambient audio
    subprocess.run([
        "ffmpeg", "-y",
        "-stream_loop", str(reps - 1), "-i", str(unit),
        "-stream_loop", "-1", "-i", str(audio),
        "-vf", f"scale={W}:{H}:flags=lanczos",
        "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        str(out),
    ], check=True, capture_output=True)
    print(f"done: {out} ({total:.1f}s = {reps} x {unit_len:.1f}s loop unit)")


if __name__ == "__main__":
    main()
