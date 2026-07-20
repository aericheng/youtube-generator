"""AI ambient audio via local Stable Audio Open 1.0 (text-to-audio).

Commercial use OK under Stability AI Community License (<$1M annual revenue,
attribution "Powered by Stability AI"). Weights are HF-gated: accept the
license on the model page once, then authenticate with an HF token.

Usage: python make_ambient_ai.py <scene.json> [--out <file>] [--seconds 30]
Scene JSON needs: id, audio_prompt (and optional audio.gain_db).
"""
import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

import soundfile as sf
import torch
from diffusers import StableAudioPipeline

MODEL_ID = "stabilityai/stable-audio-open-1.0"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--out", default=None)
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--steps", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    out = Path(args.out or Path("output") / scene["id"] / "ambient.m4a")
    out.parent.mkdir(parents=True, exist_ok=True)
    gain_db = scene.get("audio", {}).get("gain_db", -6)

    assert torch.cuda.is_available(), "CUDA not available"
    pipe = StableAudioPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.float16)
    pipe = pipe.to("cuda")

    t0 = time.perf_counter()
    audio = pipe(
        prompt=scene["audio_prompt"],
        negative_prompt=scene.get("audio_negative_prompt", "music, melody, voices, speech"),
        audio_end_in_s=args.seconds,
        num_inference_steps=args.steps,
        generator=torch.Generator("cuda").manual_seed(args.seed),
    ).audios[0]
    dt = time.perf_counter() - t0

    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "raw.wav"
        sf.write(str(wav), audio.T.float().cpu().numpy(), pipe.vae.sampling_rate)
        # no head/tail fades here - looping is handled downstream with a
        # seamless self-crossfade (fades would leave a dip at the loop joint)
        af = f"loudnorm=I=-18:TP=-2:LRA=7,volume={gain_db}dB"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav), "-af", af,
             "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "160k", str(out)],
            check=True, capture_output=True,
        )
    print(f"done: {out} ({args.seconds:.0f}s) generated in {dt:.0f}s")


if __name__ == "__main__":
    main()
