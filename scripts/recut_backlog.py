"""Cut every not-yet-uploaded queue video down to ONE loop unit and refresh its metadata.

Old backlog videos are 9 repeats of a ~8.5 s loop unit, so the unit is
duration / 9. The original mp4 is kept as <name>.long.mp4; metadata gets
loop_units=1, the new duration, new title/description/tags (old ones saved in
`orig`) and a motion_score. Idempotent: entries that already have loop_units
are skipped.

Usage: python scripts/recut_backlog.py [--dry-run]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import metadata as md  # noqa: E402
from produce_daily import SEAM_FADE, duration_of  # noqa: E402
from qc_check import motion_score  # noqa: E402

QUEUE = ROOT / "output" / "queue"
OLD_REPS = 9


def pending() -> list:
    items = []
    for meta_file in sorted(QUEUE.glob("*/metadata.json")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        video = meta_file.parent / f"{meta_file.parent.name}.mp4"
        if meta.get("videoId") or meta.get("loop_units") or not video.exists():
            continue
        items.append((video, meta_file, meta))
    return items


def cut(video: Path, unit: float, out: Path) -> None:
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(video),
         "-t", f"{unit:.3f}",
         "-af", f"afade=t=in:st=0:d={SEAM_FADE},afade=t=out:st={unit - SEAM_FADE:.3f}:d={SEAM_FADE}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", str(out)],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {video.name}: {r.stderr[-400:]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    items = pending()
    print(f"{len(items)} video(s) to recut")
    if args.dry_run:
        for video, _, meta in items:
            full = duration_of(video)
            print(f"  {video.parent.name}: {full:.1f}s -> {md.recut_unit_len(full, OLD_REPS):.2f}s")
        return
    if not items:
        return

    cfg = json.loads((ROOT / "pipeline" / "pool" / "config.json").read_text(encoding="utf-8"))
    topics = {t["id"]: t for t in json.loads(
        (ROOT / "pipeline" / "pool" / "topics.json").read_text(encoding="utf-8"))}
    taken = md.taken_titles(QUEUE, md.channel_titles(ROOT))
    done = 0
    for video, meta_file, meta in items:
        topic = topics.get(meta.get("topic_id"))
        if topic is None:
            print(f"SKIP {video.parent.name}: unknown topic {meta.get('topic_id')}")
            continue
        unit = md.recut_unit_len(duration_of(video), OLD_REPS)
        tmp = video.with_name(video.stem + ".recut.mp4")
        cut(video, unit, tmp)
        long_name = video.with_name(video.stem + ".long.mp4")
        video.replace(long_name)
        tmp.replace(video)
        new = md.build_metadata(topic, cfg["metadata_footer"], taken)
        taken.add(new["title"])
        meta["orig"] = {k: meta[k] for k in ("title", "description", "tags") if k in meta}
        meta.update(new)
        meta["duration_sec"] = round(duration_of(video), 1)
        meta["loop_units"] = 1
        meta["motion_score"] = motion_score(str(video))
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        done += 1
        print(f"OK {video.parent.name}: {meta['duration_sec']}s motion={meta['motion_score']} | {meta['title']}")
    print(f"recut {done} video(s)")


if __name__ == "__main__":
    main()
