"""Crop A14B frames to 9:16, upscale them to 1080x1920 and encode a 16 fps clip.

Uses Real-ESRGAN general x4v3 (BSD-3) at denoise 0.5, the same blend as upstream's
default. The strong-denoise weights alone wipe out sand grain. basicsr is not needed,
and weights_only=True means the .pth files cannot run code.

Usage: python upscale_clip.py <frames_dir> <out.mp4>
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

WEIGHTS = Path(__file__).resolve().parent.parent / "models" / "upscale"
TARGET = (1080, 1920)
FPS = 16
DENOISE = 0.5


class SRVGG(nn.Module):
    def __init__(self, feat=64, convs=32, up=4):
        super().__init__()
        layers = [nn.Conv2d(3, feat, 3, 1, 1), nn.PReLU(num_parameters=feat)]
        for _ in range(convs):
            layers += [nn.Conv2d(feat, feat, 3, 1, 1), nn.PReLU(num_parameters=feat)]
        layers += [nn.Conv2d(feat, 3 * up * up, 3, 1, 1), nn.PixelShuffle(up)]
        self.body = nn.Sequential(*layers)
        self.up = up

    def forward(self, x):
        return self.body(x) + F.interpolate(x, scale_factor=self.up, mode="nearest")


def load() -> nn.Module:
    strong = torch.load(WEIGHTS / "realesr-general-x4v3.pth", map_location="cpu", weights_only=True)["params"]
    weak = torch.load(WEIGHTS / "realesr-general-wdn-x4v3.pth", map_location="cpu", weights_only=True)["params"]
    net = SRVGG()
    net.load_state_dict({k: DENOISE * strong[k] + (1 - DENOISE) * weak[k] for k in strong})
    return net.eval().to("cuda").half()


def center_crop(img: Image.Image) -> Image.Image:
    """Trim to exact 9:16 so the upscale does not stretch the picture."""
    w, h = img.size
    new_w = round(h * 9 / 16)
    left = (w - new_w) // 2
    return img.crop((left, 0, left + new_w, h))


@torch.inference_mode()
def upscale(net: nn.Module, img: Image.Image) -> Image.Image:
    arr = np.asarray(img.convert("RGB"), np.float32) / 255
    x = torch.from_numpy(arr).permute(2, 0, 1)[None].to("cuda").half()
    y = net(x).clamp(0, 1)[0].permute(1, 2, 0).float().cpu().numpy()
    return Image.fromarray((y * 255).round().astype(np.uint8))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("out")
    args = ap.parse_args()

    paths = sorted(Path(args.frames).glob("*.png"))
    if not paths:
        raise SystemExit(f"no frames in {args.frames}")
    net = load()
    with tempfile.TemporaryDirectory() as td:
        for path in paths:
            big = upscale(net, center_crop(Image.open(path)))
            big.resize(TARGET, Image.LANCZOS).save(Path(td) / path.name)
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(Path(td) / "%04d.png"),
             "-c:v", "libx264", "-preset", "medium", "-crf", "10", "-pix_fmt", "yuv420p", args.out],
            check=True,
        )
    print(f"done: {args.out} ({len(paths)} frames)")


if __name__ == "__main__":
    main()
