"""Images + ambient audio -> vertical 1080x1920 mp4 with Ken Burns + crossfades.

Loop trick: the final crossfade lands on a static clip of image 01 at base zoom,
and image 01's own Ken Burns starts at base zoom, so last frame == first frame.

Usage: python assemble.py <scene.json> [--images <dir>] [--audio <file>] [--out <file>]
"""
import argparse
import json
import subprocess
from pathlib import Path

W, H = 1080, 1920
FPS = 30
UPSCALE = 2  # pre-upscale before zoompan to reduce jitter


def kenburns(idx: int, seconds: float, zoom_in: bool) -> str:
    frames = int(seconds * FPS)
    if zoom_in:
        z = f"min(1+0.0016*on,1.25)"
    else:
        z = f"max(1.25-0.0016*on,1.0)"
    return (
        f"[{idx}:v]scale={W * UPSCALE}:{H * UPSCALE}:force_original_aspect_ratio=increase,"
        f"crop={W * UPSCALE}:{H * UPSCALE},"
        f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={W}x{H}:fps={FPS},format=yuv420p[v{idx}]"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--images", default=None)
    ap.add_argument("--audio", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    base = Path("output") / scene["id"]
    img_dir = Path(args.images or base / "images")
    out = Path(args.out or base / f"{scene['id']}.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    images = sorted(img_dir.glob("*.png"))
    assert images, f"no images in {img_dir}"
    sec = float(scene["seconds_per_image"])
    xf = float(scene.get("crossfade", 1.0))
    n = len(images)

    # inputs: each image once, plus image[0] again as the static loop tail
    cmd = ["ffmpeg", "-y"]
    for p in images:
        cmd += ["-loop", "1", "-t", str(sec), "-i", str(p)]
    cmd += ["-loop", "1", "-t", str(xf + 0.5), "-i", str(images[0])]

    parts = []
    for i in range(n):
        parts.append(kenburns(i, sec, zoom_in=(i % 2 == 0)))
    # static tail at base zoom == first frame of clip 0
    parts.append(
        f"[{n}:v]scale={W * UPSCALE}:{H * UPSCALE}:force_original_aspect_ratio=increase,"
        f"crop={W * UPSCALE}:{H * UPSCALE},scale={W}:{H},fps={FPS},format=yuv420p[v{n}]"
    )

    # chain xfades: each clip contributes (sec - xf) before the next fade starts
    prev = "v0"
    offset = sec - xf
    for i in range(1, n + 1):
        label = f"x{i}"
        parts.append(f"[{prev}][v{i}]xfade=transition=fade:duration={xf}:offset={offset:.3f}[{label}]")
        prev = label
        offset += sec - xf
    total = n * (sec - xf) + xf  # ends exactly when the last fade completes

    audio = args.audio or (base / "ambient.m4a")
    filter_complex = ";".join(parts)
    cmd += [
        "-i", str(audio),
        "-filter_complex", filter_complex,
        "-map", f"[{prev}]", "-map", f"{n + 1}:a",
        "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    print(f"done: {out} ({total:.1f}s, {n} scenes)")


if __name__ == "__main__":
    main()
