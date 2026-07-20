"""Quick test: does Wan 2.2 TI2V-5B run image-to-video via diffusers on this box?

Takes a frame from an existing clip as the start image, generates a short
low-step continuation. Pass/fail + timing only - not a quality benchmark.
"""
import sys
import time

import torch
from diffusers import WanImageToVideoPipeline
from diffusers.utils import export_to_video, load_image

MODEL_ID = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"

image_path, out_path = sys.argv[1], sys.argv[2]

pipe = WanImageToVideoPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
pipe.enable_model_cpu_offload()

image = load_image(image_path)
t0 = time.perf_counter()
frames = pipe(
    image=image,
    prompt="gentle ocean waves rolling onto the beach, foam spreading and receding, static camera, photorealistic",
    negative_prompt="camera movement, scene change, distortion",
    width=704,
    height=1280,
    num_frames=49,
    num_inference_steps=10,
    generator=torch.Generator("cpu").manual_seed(1),
).frames[0]
print(f"I2V_OK {time.perf_counter() - t0:.0f}s for 49 frames @ 10 steps")
export_to_video(frames, out_path, fps=24)
