"""QC gate for finished shorts: resolution, duration, streams, loudness.

Uses only ffmpeg (no ffprobe needed): stream info is parsed from `ffmpeg -i`
stderr, loudness from the volumedetect filter.

Usage: python qc_check.py <video.mp4> [--min-sec 15] [--max-sec 60]
Exits 1 with a FAIL list if any check fails.
"""
import argparse
import re
import subprocess
import sys


def probe(path: str) -> dict:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path],
                       capture_output=True, text=True)
    err = r.stderr
    dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", err)
    res = re.search(r"Stream .*?: Video: .*?\b(\d{3,5})x(\d{3,5})\b", err)
    return {
        "duration": (int(dur.group(1)) * 3600 + int(dur.group(2)) * 60
                     + float(dur.group(3))) if dur else float("nan"),
        "width": int(res.group(1)) if res else 0,
        "height": int(res.group(2)) if res else 0,
        "has_audio": ": Audio:" in err,
    }


def mean_volume(path: str) -> float:
    r = subprocess.run(
        ["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--min-sec", type=float, default=15)
    ap.add_argument("--max-sec", type=float, default=60)
    args = ap.parse_args()

    info = probe(args.video)
    vol = mean_volume(args.video)

    checks = {
        f"resolution 1080x1920 (got {info['width']}x{info['height']})":
            info["width"] == 1080 and info["height"] == 1920,
        f"duration {args.min_sec}-{args.max_sec}s (got {info['duration']:.1f}s)":
            args.min_sec <= info["duration"] <= args.max_sec,
        "has audio stream": info["has_audio"],
        f"mean volume -35..-10 dB (got {vol:.1f} dB)": -35 <= vol <= -10,
    }
    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(("PASS " if ok else "FAIL ") + name)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
