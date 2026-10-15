"""Title / description / tag generation for the daily shorts (pure local templates).

Shared by produce_daily.py and scripts/recut_backlog.py. Titles rotate through
each topic's `title_variants` and never repeat one that is already on the
channel (or queued); when all variants are taken a numeric suffix is added.
"""
import json
from pathlib import Path

BASE_TAGS = ["lofi", "ambience", "relaxing", "chill", "shorts"]
MAX_TITLE = 100


def taken_titles(queue_dir: Path, extra=()) -> set:
    """Titles already used: every queue metadata.json (uploaded or still waiting)
    plus `extra` (e.g. titles listed from the channel via the Data API)."""
    taken = set(extra)
    for f in Path(queue_dir).glob("*/metadata.json"):
        try:
            meta = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("title"):
            taken.add(meta["title"])
    return taken


def pick_title(topic: dict, taken: set) -> str:
    variants = topic.get("title_variants") or [topic["title"]]
    for v in variants:
        if v not in taken:
            return v
    n = 2
    while True:
        suffix = f" #{n}"
        cand = variants[0][:MAX_TITLE - len(suffix)] + suffix
        if cand not in taken:
            return cand
        n += 1


def build_metadata(topic: dict, footer: str, taken: set) -> dict:
    title = pick_title(topic, taken)
    tag = topic.get("hashtag") or topic["id"].replace("-", "")
    scene = topic.get("scene_line") or "Sit back, relax and enjoy."
    description = (f"{scene}\n\n#shorts #lofi #ambience #{tag}\n\n{footer}")
    tags = list(BASE_TAGS)
    for k in topic.get("keywords", []):
        if k not in tags:
            tags.append(k)
    return {"title": title, "description": description, "tags": tags}


def get_loop_units(cfg: dict, override=None) -> int:
    return max(1, int(override if override else cfg.get("loop_units", 1)))


def expected_duration(loop_units: int, unit_len: float) -> float:
    return loop_units * unit_len


def duration_bounds(loop_units: int, unit_len: float) -> tuple:
    """QC range: same proportions as the old 0.8x-1.3x of the target."""
    exp = expected_duration(loop_units, unit_len)
    return exp * 0.8, exp * 1.3


def recut_unit_len(duration_sec: float, reps: int = 9) -> float:
    """Old backlog videos are 9 repeats of one loop unit."""
    return duration_sec / reps


def channel_titles(root: Path) -> set:
    """Titles of every video on the channel (Data API, youtube.readonly).
    Best effort: any failure (no token, offline, quota) returns an empty set so
    callers fall back to the local queue metadata."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        token = Path(root) / "secrets" / "token.json"
        creds = Credentials.from_authorized_user_file(str(token))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token.write_text(creds.to_json(), encoding="utf-8")
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        ch = yt.channels().list(part="contentDetails", mine=True).execute()
        uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        titles, page = set(), None
        while True:
            r = yt.playlistItems().list(part="snippet", playlistId=uploads,
                                        maxResults=50, pageToken=page).execute()
            titles.update(i["snippet"]["title"] for i in r.get("items", []))
            page = r.get("nextPageToken")
            if not page:
                return titles
    except Exception as e:
        print(f"channel_titles unavailable ({type(e).__name__}); using local queue only")
        return set()
