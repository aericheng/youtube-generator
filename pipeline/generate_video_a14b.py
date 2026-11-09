"""Single-scene clip via local Wan 2.2 T2V A14B (GGUF Q4_K_M, 480x832, 16 fps).

Encodes the prompt first and frees the text encoder, because loading all three
models together hits os error 1455 on a busy desktop. Latents are saved before the
VAE decode, so a rerun with the same --out-dir does not lose an hour of denoising.
16 GB VRAM: peak 12.6 GiB, about 57 min. 576x1024 and up overflow the card.

Usage: python generate_video_a14b.py <scene.json> --out-dir <dir> --seed N [--steps 30]
Writes <dir>/latents.pt and <dir>/frames/*.png. Scene JSON needs video_prompt, negative_prompt.
"""
import argparse
import gc
import json
import os
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # every model is local; do not depend on the network

import numpy as np  # noqa: E402
import torch  # noqa: E402
from diffusers import AutoencoderKLWan, GGUFQuantizationConfig, WanPipeline, WanTransformer3DModel  # noqa: E402
from PIL import Image  # noqa: E402
from transformers import T5TokenizerFast, UMT5EncoderModel  # noqa: E402

MODELS = Path(__file__).resolve().parent.parent / "models" / "a14b"
DIFFUSERS = str(MODELS / "diffusers")
GGUF = MODELS / "gguf"
ENCODER_REPO = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"  # same UMT5, already cached for the 5B model
W, H, FRAMES = 480, 832, 81


def encode(scene: dict) -> tuple:
    text_encoder = UMT5EncoderModel.from_pretrained(
        ENCODER_REPO, subfolder="text_encoder", torch_dtype=torch.bfloat16
    ).to("cuda")
    tokenizer = T5TokenizerFast.from_pretrained(ENCODER_REPO, subfolder="tokenizer")
    encoder = WanPipeline(tokenizer=tokenizer, text_encoder=text_encoder, vae=None, scheduler=None)
    with torch.no_grad():
        pos, neg = encoder.encode_prompt(
            scene["video_prompt"],
            negative_prompt=scene.get("negative_prompt", ""),
            max_sequence_length=512,
            device=torch.device("cuda"),
            dtype=torch.bfloat16,
        )
    pos, neg = pos.cpu(), neg.cpu()
    del encoder, text_encoder
    gc.collect()
    torch.cuda.empty_cache()
    return pos, neg


def transformer(gguf_path: Path, subfolder: str) -> WanTransformer3DModel:
    return WanTransformer3DModel.from_single_file(
        str(gguf_path),
        quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        config=DIFFUSERS,
        subfolder=subfolder,
        torch_dtype=torch.bfloat16,
    )


def denoise(args, scene: dict, vae) -> torch.Tensor:
    pos, neg = encode(scene)
    pipe = WanPipeline.from_pretrained(
        DIFFUSERS,
        transformer=transformer(GGUF / "HighNoise/Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf", "transformer"),
        transformer_2=transformer(GGUF / "LowNoise/Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf", "transformer_2"),
        vae=vae,
        text_encoder=None,
        tokenizer=None,
        torch_dtype=torch.bfloat16,
    )
    pipe.enable_model_cpu_offload()
    latents = pipe(
        prompt_embeds=pos.to("cuda"),
        negative_prompt_embeds=neg.to("cuda"),
        width=W,
        height=H,
        num_frames=FRAMES,
        num_inference_steps=args.steps,
        guidance_scale=4.0,
        guidance_scale_2=3.0,
        generator=torch.Generator("cpu").manual_seed(args.seed),
        output_type="latent",
    ).frames
    del pipe
    gc.collect()
    torch.cuda.empty_cache()
    return latents.cpu()


def decode(latents: torch.Tensor, vae, frames_dir: Path) -> None:
    vae.to("cuda")
    latents = latents.to("cuda", dtype=vae.dtype)
    mean = torch.tensor(vae.config.latents_mean).view(1, vae.config.z_dim, 1, 1, 1).to(latents)
    std = 1.0 / torch.tensor(vae.config.latents_std).view(1, vae.config.z_dim, 1, 1, 1).to(latents)
    with torch.no_grad():
        video = vae.decode(latents / std + mean, return_dict=False)[0]
    arr = ((video[0].clamp(-1, 1) + 1) / 2 * 255).round().byte().permute(1, 2, 3, 0).cpu().numpy()
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(arr):
        Image.fromarray(np.asarray(frame)).save(frames_dir / f"{i:04d}.png")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--steps", type=int, default=30)
    args = ap.parse_args()

    assert torch.cuda.is_available(), "CUDA not available"
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    vae = AutoencoderKLWan.from_pretrained(DIFFUSERS, subfolder="vae", torch_dtype=torch.float32)
    latents_file = out / "latents.pt"
    t0 = time.perf_counter()
    if latents_file.exists():
        latents = torch.load(latents_file, weights_only=True)
    else:
        latents = denoise(args, scene, vae)
        partial = latents_file.with_suffix(".tmp")  # a kill mid-save must not leave a bad latents.pt
        torch.save(latents, partial)
        partial.replace(latents_file)
    decode(latents, vae, out / "frames")
    peak = torch.cuda.max_memory_allocated() / 2**30
    print(f"done: {out} in {(time.perf_counter() - t0) / 60:.1f} min, peak {peak:.1f} GiB")


if __name__ == "__main__":
    main()
