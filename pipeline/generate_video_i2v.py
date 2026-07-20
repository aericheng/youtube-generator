"""Image-to-video via Wan 2.2 TI2V-5B: same scene, new motion.

Usage: python generate_video_i2v.py <start.png> <prompt> <out.mp4>
       [--negative <str>] [--steps 35] [--seconds 5] [--seed 1]
"""
import argparse
import time

import torch
from diffusers import WanImageToVideoPipeline
from diffusers.utils import export_to_video, load_image

MODEL_ID = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
W, H, FPS = 704, 1280, 24


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("prompt")
    ap.add_argument("out")
    ap.add_argument("--negative", default="camera movement, scene change, distortion, low quality")
    ap.add_argument("--steps", type=int, default=35)
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    pipe = WanImageToVideoPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload()

    t0 = time.perf_counter()
    frames = pipe(
        image=load_image(args.image),
        prompt=args.prompt,
        negative_prompt=args.negative,
        width=W,
        height=H,
        num_frames=int(args.seconds * FPS) + 1,
        num_inference_steps=args.steps,
        generator=torch.Generator("cpu").manual_seed(args.seed),
    ).frames[0]
    export_to_video(frames, args.out, fps=FPS)
    print(f"done: {args.out} ({len(frames)} frames) in {(time.perf_counter() - t0)/60:.1f} min")


if __name__ == "__main__":
    main()
