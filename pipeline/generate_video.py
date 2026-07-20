"""Single-scene ambient clip via local Wan 2.2 TI2V-5B (text-to-video).

Produces one vertical 704x1280 clip; loop_assemble.py extends it to target
length. 16GB VRAM: model CPU offload is on (64GB system RAM available).

Usage: python generate_video.py <scene.json> [--out <file>] [--steps 35] [--seconds 5]
Scene JSON needs: id, video_prompt, negative_prompt.
"""
import argparse
import json
import time
from pathlib import Path

import torch
from diffusers import WanPipeline
from diffusers.utils import export_to_video

MODEL_ID = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
W, H, FPS = 704, 1280, 24


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--out", default=None)
    ap.add_argument("--steps", type=int, default=35)
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    out = Path(args.out or Path("output") / scene["id"] / "clip.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(args.seconds * FPS) + 1

    assert torch.cuda.is_available(), "CUDA not available"
    print(f"GPU: {torch.cuda.get_device_name(0)}, torch {torch.__version__}")

    pipe = WanPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload()

    t0 = time.perf_counter()
    frames = pipe(
        prompt=scene["video_prompt"],
        negative_prompt=scene.get("negative_prompt", ""),
        width=W,
        height=H,
        num_frames=num_frames,
        num_inference_steps=args.steps,
        generator=torch.Generator("cpu").manual_seed(args.seed),
    ).frames[0]
    dt = time.perf_counter() - t0

    export_to_video(frames, str(out), fps=FPS)
    print(f"done: {out} ({len(frames)} frames, {args.seconds:.0f}s) generated in {dt/60:.1f} min")


if __name__ == "__main__":
    main()
