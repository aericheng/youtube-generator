"""Procedural ambient audio via ffmpeg noise shaping (sample-grade, $0).

Types: rain (filtered white noise), waves (brown noise + slow swell),
fire (brown noise + fast flicker). Production audio should come from a
licensed library or generative API instead - this is for style samples.

Usage: python make_ambient.py <rain|waves|fire> <seconds> <out.m4a> [--gain-db -6]
"""
import argparse
import subprocess

# each recipe = (lavfi source, post filters applied via -af)
RECIPES = {
    "rain": (
        "anoisesrc=color=white:amplitude=0.6:seed={seed}",
        "highpass=f=400,lowpass=f=7000,tremolo=f=0.3:d=0.15",
    ),
    "waves": (
        "anoisesrc=color=brown:amplitude=0.8:seed={seed}",
        "lowpass=f=850,highpass=f=60,tremolo=f=0.11:d=0.85",
    ),
    "fire": (
        "anoisesrc=color=brown:amplitude=0.7:seed={seed}",
        "lowpass=f=2500,highpass=f=120,tremolo=f=9:d=0.5,tremolo=f=0.7:d=0.3",
    ),
}
FADE = 1.0  # soft in/out so the loop seam is not a click


def build(kind: str, seconds: float, out: str, gain_db: float = -6.0, seed: int = 7) -> None:
    src, shaping = RECIPES[kind]
    src = src.format(seed=seed) + f":duration={seconds}"
    af = (
        f"{shaping},loudnorm=I=-18:TP=-2:LRA=7,volume={gain_db}dB,"
        f"afade=t=in:d={FADE},afade=t=out:st={seconds - FADE}:d={FADE}"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-af", af,
         "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "160k", out],
        check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=sorted(RECIPES))
    ap.add_argument("seconds", type=float)
    ap.add_argument("out")
    ap.add_argument("--gain-db", type=float, default=-6.0)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    build(args.kind, args.seconds, args.out, args.gain_db, args.seed)


if __name__ == "__main__":
    main()
