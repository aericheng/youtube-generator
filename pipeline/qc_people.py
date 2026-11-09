"""Refuse clips that show a person, using RT-DETR's COCO person class (Apache 2.0).

Usage: python qc_people.py <clip.mp4> [...] [--every-seconds 0.125]
Exit 0 = clean, 3 = person found. Anything else is a crash or an unreadable clip,
which the caller must also treat as a failure.

A clip is flagged when at least MIN_SHARE of its sampled frames score MIN_SCORE or
more, or when MIN_RUN sampled frames in a row do. One frame is not enough: flames spike
to 0.9 on single frames with nobody there, while a person stays across frames.
Blurred, very dark or small people (under about 66x40 in a 480x832 frame) can still
pass; their scores overlap flames, so a lower threshold is not the fix.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # the detector is cached; do not depend on the network

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402
from transformers import RTDetrForObjectDetection  # noqa: E402

MODEL = "PekingU/rtdetr_r50vd"
MIN_SCORE = 0.72
MIN_SHARE = 0.20
MIN_RUN = 4  # half a second at the default sampling of a 5 s master
EXIT_PERSON = 3


def sample(video: str, every: float, tmp: Path) -> list:
    # -xerror: a damaged clip must fail here, not pass on the frames that did decode.
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", video, "-vf", f"fps=1/{every}",
                    str(tmp / "%05d.png")], check=True)
    return sorted(tmp.glob("*.png"))


def longest_run(hits: np.ndarray) -> int:
    best = current = 0
    for hit in hits:
        current = current + 1 if hit else 0
        best = max(best, current)
    return best


def flagged(scores: np.ndarray) -> bool:
    hits = scores >= MIN_SCORE
    return bool(hits.mean() >= MIN_SHARE or longest_run(hits) >= MIN_RUN)


@torch.inference_mode()
def score(det, person: int, path: Path) -> float:
    # RT-DETR input is 640x640 in the 0-1 range with no mean/std, so torchvision is not needed.
    img = Image.open(path).convert("RGB").resize((640, 640), Image.BILINEAR)
    x = torch.from_numpy(np.asarray(img, np.float32) / 255).permute(2, 0, 1)[None].to("cuda")
    return float(det(pixel_values=x).logits[0].sigmoid()[:, person].max())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--every-seconds", type=float, default=0.125)
    args = ap.parse_args()
    det = RTDetrForObjectDetection.from_pretrained(MODEL).eval().to("cuda")
    person = next(i for i, n in det.config.id2label.items() if n == "person")
    found = 0
    for clip in args.clips:
        with tempfile.TemporaryDirectory() as td:
            scores = np.array([score(det, person, f) for f in sample(clip, args.every_seconds, Path(td))])
        hits = scores >= MIN_SCORE
        bad = flagged(scores)
        found += bad
        print(f"{'FLAG' if bad else 'ok  '} max {scores.max():.2f} share {hits.mean():.2f} "
              f"run {longest_run(hits):2d} n {len(scores):3d}  {clip}", flush=True)
    sys.exit(EXIT_PERSON if found else 0)


if __name__ == "__main__":
    main()
