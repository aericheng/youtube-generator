"""Disk cleanup for output/queue. DRY-RUN by default; deletes only with --apply.

Upload state: each <date>-<topic>/metadata.json gets a "videoId" (and
"uploaded_privacy") written by upload_queue.py after a successful upload.
There is no upload timestamp, so metadata.json's mtime (rewritten at upload
time) is used as the upload date.

Rules:
  * folder candidate: uploaded AND upload time older than --keep-days
  * intermediate candidate (--intermediate): uploaded folder whose final
    <folder>.mp4 exists; non-final *.mp4 and *.m4a files inside it
  * folders that are NOT uploaded are never deleted.
"""
import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE = ROOT / "output" / "queue"


def load_state(queue_dir: Path, state_path: Path | None) -> dict:
    """Return {folder_name: {"videoId":..., "uploaded_at": epoch}} for uploaded folders."""
    state = {}
    if state_path and state_path.exists():
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        for name, rec in raw.items():
            if isinstance(rec, dict) and rec.get("videoId"):
                state[name] = {"videoId": rec["videoId"], "uploaded_at": rec.get("uploaded_at")}
        return state
    for meta_file in queue_dir.glob("*/metadata.json"):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if meta.get("videoId"):
            state[meta_file.parent.name] = {
                "videoId": meta["videoId"],
                "uploaded_at": meta_file.stat().st_mtime,
            }
    return state


def fmt_ts(ts) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "-"


def dir_size(d: Path) -> int:
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file())


def is_intermediate(f: Path, final_name: str) -> bool:
    return f.is_file() and f.name != final_name and f.suffix.lower() in (".mp4", ".m4a")


def cleanup(queue_dir: Path, state: dict, keep_days=14, dry_run=True, intermediate=False) -> list[dict]:
    cutoff = time.time() - keep_days * 86400
    out = []
    for d in sorted(queue_dir.iterdir()):
        if not d.is_dir():
            continue
        item = state.get(d.name)
        uploaded_at = item["uploaded_at"] if item else None
        if not item:
            continue  # never touch un-uploaded folders
        if uploaded_at and uploaded_at < cutoff:
            out.append({"path": str(d), "kind": "folder", "size": dir_size(d),
                        "uploaded_at": fmt_ts(uploaded_at),
                        "reason": f"uploaded (videoId set), upload time older than {keep_days}d"})
            if not dry_run:
                shutil.rmtree(d)
        elif intermediate and (d / f"{d.name}.mp4").exists():
            for f in sorted(d.iterdir()):
                if is_intermediate(f, f"{d.name}.mp4"):
                    out.append({"path": str(f), "kind": "intermediate", "size": f.stat().st_size,
                                "uploaded_at": fmt_ts(uploaded_at),
                                "reason": "uploaded, final mp4 exists, intermediate file"})
                    if not dry_run:
                        f.unlink()
    return out


def pending_intermediate_bytes(queue_dir: Path, state: dict) -> tuple[int, int]:
    """Info only: intermediates in NOT-uploaded folders (never deleted)."""
    n = total = 0
    for d in sorted(queue_dir.iterdir()):
        if d.is_dir() and d.name not in state and (d / f"{d.name}.mp4").exists():
            for f in d.iterdir():
                if is_intermediate(f, f"{d.name}.mp4"):
                    n += 1
                    total += f.stat().st_size
    return n, total


def write_report(path: Path, items, dry_run, args, pending_info):
    gb = lambda b: b / 1024**3
    title = "DRY-RUN，未刪除任何檔案" if dry_run else "APPLIED，已刪除下列項目"
    folders = [i for i in items if i["kind"] == "folder"]
    inter = [i for i in items if i["kind"] == "intermediate"]
    L = [f"# youtube generator cleanup 候選清單（{title}）", "",
         f"產生時間：{fmt_ts(time.time())}；keep-days={args.keep_days}；queue={args.queue_dir}", "",
         "已上傳判定：`<資料夾>/metadata.json` 含 `videoId`（upload_queue.py 上傳成功後寫入）；"
         "無上傳時間欄位，以 metadata.json 的 mtime 作為上傳日期。未上傳資料夾永不列入。", ""]
    for name, rows in (("資料夾候選", folders), ("中間檔候選", inter)):
        L += [f"## {name}", ""]
        if name == "中間檔候選" and not args.intermediate:
            L += ["（本次未帶 `--intermediate`，未計算）", ""]
            continue
        L += [f"筆數 {len(rows)}，合計 {gb(sum(i['size'] for i in rows)):.3f} GB", "",
              "| 路徑 | 類型 | 大小 MB | 上傳日期 | 判定依據 |", "|---|---|---|---|---|"]
        L += [f"| {i['path']} | {i['kind']} | {i['size']/1024**2:.1f} | {i['uploaded_at']} | {i['reason']} |" for i in rows]
        L.append("")
    tot = sum(i["size"] for i in items)
    L += ["## 總計", "", f"共 {len(items)} 筆，{gb(tot):.3f} GB", ""]
    if args.intermediate:
        L += [f"備註：未上傳（待傳）資料夾內另有 {pending_info[0]} 個中間檔、{gb(pending_info[1]):.3f} GB，"
              "依規則永不列入，僅供參考。", ""]
    cmd = "python pipeline/cleanup.py --apply" + (" --intermediate" if args.intermediate else "") + \
          f" --keep-days {args.keep_days}"
    L += ["## 實際刪除指令（使用者裁決後才執行）", "", f"`{cmd}`", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--queue-dir", type=Path, default=DEFAULT_QUEUE)
    ap.add_argument("--state", type=Path, default=None,
                    help="optional JSON {folder: {videoId, uploaded_at}}; default: read each folder's metadata.json")
    ap.add_argument("--keep-days", type=int, default=14)
    ap.add_argument("--intermediate", action="store_true")
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    dry_run = not args.apply

    queue_dir = args.queue_dir.resolve()
    if not dry_run:
        try:
            queue_dir.relative_to((ROOT / "output").resolve())
        except ValueError:
            sys.exit(f"refuse: {queue_dir} is not under {ROOT / 'output'}")
    args.queue_dir = queue_dir
    state = load_state(queue_dir, args.state)
    items = cleanup(queue_dir, state, args.keep_days, dry_run, args.intermediate)
    for i in items:
        print(f"{i['kind']:12} {i['size']/1024**2:9.1f} MB  {i['uploaded_at']}  {i['path']}")
    tot = sum(i["size"] for i in items)
    print(f"TOTAL {len(items)} items, {tot/1024**3:.3f} GB ({'DRY-RUN' if dry_run else 'APPLIED'})")
    if args.report:
        write_report(args.report, items, dry_run, args, pending_intermediate_bytes(queue_dir, state))


if __name__ == "__main__":
    main()
