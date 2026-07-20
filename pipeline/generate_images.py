"""Scene spec (JSON) -> images via local SDXL.

Usage: python generate_images.py <scene.json> [--out <dir>]
Writes 01.png..NN.png plus timing.json (per-image seconds, for benchmarking).
"""
import argparse
import json
import time
from pathlib import Path

import torch
from diffusers import StableDiffusionXLPipeline

MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--out", default=None)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    out_dir = Path(args.out or Path("output") / scene["id"] / "images")
    out_dir.mkdir(parents=True, exist_ok=True)

    assert torch.cuda.is_available(), "CUDA not available - check torch cu128+ install"
    print(f"GPU: {torch.cuda.get_device_name(0)}, torch {torch.__version__}")

    pipe = StableDiffusionXLPipeline.from_pretrained(
        MODEL_ID, torch_dtype=torch.float16, variant="fp16", use_safetensors=True
    ).to("cuda")

    timings = []
    for i, prompt in enumerate(scene["prompts"], start=1):
        gen = torch.Generator("cuda").manual_seed(args.seed + i)
        t0 = time.perf_counter()
        image = pipe(
            prompt=prompt,
            negative_prompt=scene.get("negative_prompt", ""),
            width=scene["width"],
            height=scene["height"],
            num_inference_steps=args.steps,
            generator=gen,
        ).images[0]
        dt = time.perf_counter() - t0
        path = out_dir / f"{i:02d}.png"
        image.save(path)
        timings.append({"image": path.name, "seconds": round(dt, 2)})
        print(f"[{i}/{len(scene['prompts'])}] {path.name} in {dt:.1f}s")

    (out_dir / "timing.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")
    total = sum(t["seconds"] for t in timings)
    print(f"done: {len(timings)} images, total {total:.1f}s, avg {total/len(timings):.1f}s/image")


if __name__ == "__main__":
    main()
