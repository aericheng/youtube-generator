"""Upload finished queue videos to YouTube via the official Data API.

Scans output/queue/*/metadata.json for entries without a videoId, uploads
the oldest ones (up to --max per run), and writes the videoId back so a
video is never uploaded twice.

Safety gate: queue uploads only run when pipeline/pool/config.json has
upload_privacy == "public" (i.e., after the API project passes the YouTube
compliance audit). Pre-audit API uploads are permanently locked private, so
uploading real videos before approval would destroy them. For pre-audit
smoke testing use pipeline/yt_smoketest.py with a throwaway file instead.

Usage: python pipeline/upload_queue.py [--max 1] [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "output" / "queue"
SECRETS = ROOT / "secrets"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CATEGORY_MUSIC = "10"


def yt_client():
    token = SECRETS / "token.json"
    assert token.exists(), "run pipeline/yt_auth.py first"
    creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def pending_videos() -> list:
    items = []
    for meta_file in sorted(QUEUE.glob("*/metadata.json")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if meta.get("videoId"):
            continue
        video = meta_file.parent / f"{meta_file.parent.name}.mp4"
        if video.exists():
            items.append((video, meta_file, meta))
    return items


def upload(yt, video: Path, meta: dict, privacy: str) -> str:
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta.get("tags", []),
            "categoryId": CATEGORY_MUSIC,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": bool(meta.get("ai_disclosure", True)),
        },
    }
    media = MediaFileUpload(str(video), mimetype="video/mp4",
                            chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  {int(status.progress() * 100)}%", flush=True)
    return resp["id"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "pipeline" / "pool" / "config.json").read_text(encoding="utf-8"))
    privacy = cfg.get("upload_privacy", "private")
    todo = pending_videos()[: args.max]
    if not todo:
        print("nothing to upload")
        return
    if args.dry_run:
        for video, _, meta in todo:
            print(f"would upload [{privacy}]: {video.name} - {meta['title']}")
        return
    if privacy != "public":
        print(f"upload_privacy is '{privacy}' (pre-audit) - queue auto-upload "
              "disabled: API uploads from unaudited projects are permanently "
              "locked private. Set upload_privacy to 'public' after the audit "
              "passes.")
        return
    if not (SECRETS / "token.json").exists():
        print("no OAuth token yet (run pipeline/yt_auth.py) - skipping upload")
        return

    yt = yt_client()
    for video, meta_file, meta in todo:
        print(f"uploading [{privacy}]: {video.name}", flush=True)
        try:
            vid = upload(yt, video, meta, privacy)
        except Exception as e:
            print(f"FAILED {video.name}: {e}", file=sys.stderr)
            continue
        meta["videoId"] = vid
        meta["uploaded_privacy"] = privacy
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"OK: https://youtu.be/{vid}")


if __name__ == "__main__":
    main()
