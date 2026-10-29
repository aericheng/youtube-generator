"""Weekly YouTube channel report -> Discord (Mondays 08:40, task LofiWeeklyReport).

Window: Analytics startDate = today-7, endDate = yesterday. The run-log statistics
cover today-7 .. today inclusive (so Monday's report includes the 07:00 run of the
same morning - 8 shifts).

  python scripts/weekly_report.py --auth             one-time OAuth consent (see README)
  python scripts/weekly_report.py --dry-run          real Analytics data, print + write
                                                     data/weekly-report-<date>.md, no Discord
  python scripts/weekly_report.py --dry-run --mock   fixture Analytics data (no API call);
                                                     the run-log block always uses the real log
  python scripts/weekly_report.py                    real data -> Discord, writes data/last-success-weekly

Exit codes: 0 ok, 2 auth/scope problem, 1 other failure. Never posts on failure.
"""
import argparse
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TOKEN = ROOT / "secrets" / "token.json"
SCHED_LOG = ROOT / "output" / "queue" / "scheduler.log"
sys.path.insert(0, str(ROOT / "scripts"))
from daily_status import BUMP_FILE, WEBHOOK_CONFIG  # noqa: E402  (same webhook as the daily alerts)

NEED_SCOPES = {
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
}
AUTH_CMD = r".venv\Scripts\python.exe scripts\weekly_report.py --auth"
DAY_METRICS = "views,estimatedMinutesWatched,subscribersGained,subscribersLost"

# Fixture rows: day -> [day, views, minutes, gained, lost]; top -> [videoId, views, minutes]
MOCK = {
    "days": [[f"2026-10-{22 + i}", v, m, g, l] for i, (v, m, g, l) in enumerate(
        [(120, 90, 1, 0), (95, 70, 0, 0), (210, 160, 2, 1), (88, 60, 0, 0),
         (143, 110, 1, 0), (77, 50, 0, 1), (102, 80, 1, 0)])],
    "top": [["mockVid1", 210, 160], ["mockVid2", 143, 110], ["mockVid3", 120, 90]],
    "titles": {"mockVid1": "Campfire in the Forest (MOCK) lofi ambience #2",
               "mockVid2": "Rain on Leaves (MOCK) lofi ambience #2",
               "mockVid3": "Koi Pond Ripples (MOCK) lofi ambience #2"},
}


class AuthProblem(Exception):
    pass


def fetch_api(start: str, end: str) -> dict:
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    if not TOKEN.exists():
        raise AuthProblem("no secrets/token.json")
    creds = Credentials.from_authorized_user_file(str(TOKEN))  # granted scopes, not requested ones
    if creds.scopes is not None and not NEED_SCOPES <= set(creds.scopes):
        raise AuthProblem("token is missing the yt-analytics.readonly / youtube.readonly scope")
    try:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN.write_text(creds.to_json(), encoding="utf-8")
        ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        base = dict(ids="channel==MINE", startDate=start, endDate=end)
        days = ya.reports().query(dimensions="day", metrics=DAY_METRICS, sort="day", **base).execute()
        top = ya.reports().query(dimensions="video", metrics="views,estimatedMinutesWatched",
                                 sort="-views", maxResults=3, **base).execute()
        top_rows = top.get("rows", [])
        titles = {}
        if top_rows:
            items = yt.videos().list(part="snippet", id=",".join(r[0] for r in top_rows)).execute()["items"]
            titles = {i["id"]: i["snippet"]["title"] for i in items}
    except RefreshError as e:
        raise AuthProblem(f"token refresh failed ({e})")
    except HttpError as e:
        if e.status_code in (401, 403):
            raise AuthProblem(f"API refused the token ({e.status_code} {e.reason})")
        raise
    return {"days": days.get("rows", []), "top": top_rows, "titles": titles}


def log_stats(today: date) -> dict:
    """Shifts / exitcodes / produce / uploads from scheduler.log for today-7 .. today."""
    lo = today - timedelta(days=7)
    stats = {"shifts": 0, "exit0": 0, "produce_ok": 0, "uploads": 0, "fail_days": []}
    if not SCHED_LOG.exists():
        return stats
    # cmd %date% carries a cp950 weekday char; decode leniently, only the digits matter
    text = SCHED_LOG.read_bytes().decode("cp950", errors="replace")
    head = re.compile(r"^\[(\d{4})/(\d{2})/(\d{2})\b[^\]]*\]\s+(run start|produce end|run end)(?:\s+\(exitcode (\d+)\))?")
    starts, in_window = set(), False
    for line in text.splitlines():
        m = head.match(line)
        if m:
            d = date(int(m[1]), int(m[2]), int(m[3]))
            kind, rc = m[4], m[5]
            in_window = lo <= d <= today
            if not in_window:
                continue
            if kind == "run start":
                starts.add(d)
            elif kind == "produce end":
                if rc == "0":
                    stats["produce_ok"] += 1
                else:
                    stats["fail_days"].append(f"{d.isoformat()} produce exit {rc}")
            else:  # run end
                if rc == "0":
                    stats["exit0"] += 1
                else:
                    stats["fail_days"].append(f"{d.isoformat()} upload exit {rc}")
        elif in_window and line.startswith("OK: https://youtu.be/"):
            stats["uploads"] += 1
    stats["shifts"] = len(starts)
    return stats


def build_report(api: dict, st: dict, start: str, end: str, today: date, mock: bool) -> str:
    days = api["days"]
    views = sum(r[1] for r in days)
    minutes = sum(r[2] for r in days)
    gained = sum(r[3] for r in days)
    lost = sum(r[4] for r in days)
    tag = " [MOCK DATA]" if mock else ""
    L = [f"Lofi Shorts weekly report {today.isoformat()}{tag}",
         f"Analytics window: {start} .. {end} (7 days)", "",
         "== Views ==",
         f"Views: {views:,}",
         f"Watch time: {minutes / 60:,.1f} h ({minutes:,.0f} min)", "",
         "== Subscribers ==",
         f"Net: {gained - lost:+d} (+{gained} / -{lost})", "",
         "== Top 3 videos (by views) =="]
    if api["top"]:
        for i, r in enumerate(api["top"], 1):
            L.append(f"{i}. {api['titles'].get(r[0], r[0])} - {r[1]:,} views")
    else:
        L.append("(no data)")
    pct = f"{100 * st['exit0'] / st['shifts']:.0f}%" if st["shifts"] else "n/a"
    L += ["", f"== Production / upload (run log {(today - timedelta(days=7)).isoformat()} .. {today.isoformat()}) ==",
          f"Scheduled runs: {st['shifts']}",
          f"Run exitcode 0: {st['exit0']} ({pct})",
          f"Produce succeeded: {st['produce_ok']}",
          f"Videos uploaded: {st['uploads']}"]
    if st["fail_days"]:
        L.append("Failures: " + "; ".join(st["fail_days"]))
    return "\n".join(L) + "\n"


def post_discord(content: str) -> None:
    url = json.loads(WEBHOOK_CONFIG.read_text(encoding="utf-8"))["webhookUrl"]
    body = json.dumps({"content": "```\n" + content[:1900] + "```"}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "lofi-weekly-report/1.0"})
    urllib.request.urlopen(req, timeout=15).read()
    try:  # tell the claude-status watcher its dashboard was pushed; never fail the caller
        BUMP_FILE.write_text(datetime.now(timezone.utc).isoformat(timespec="seconds"), encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Weekly YouTube report to Discord")
    ap.add_argument("--auth", action="store_true", help="run the OAuth consent flow once")
    ap.add_argument("--dry-run", action="store_true", help="print + write data/weekly-report-<date>.md, do not post")
    ap.add_argument("--mock", action="store_true", help="fixture Analytics data (requires --dry-run)")
    ap.add_argument("--today", help="override today (YYYY-MM-DD), for testing")
    a = ap.parse_args()

    if a.auth:
        sys.path.insert(0, str(ROOT / "pipeline"))
        import yt_auth
        yt_auth.main()
        return 0
    if a.mock and not a.dry_run:
        print("ERROR: --mock requires --dry-run (mock data is never posted)", file=sys.stderr)
        return 1

    today = date.fromisoformat(a.today) if a.today else date.today()
    start, end = (today - timedelta(days=7)).isoformat(), (today - timedelta(days=1)).isoformat()
    try:
        api = MOCK if a.mock else fetch_api(start, end)
    except AuthProblem as e:
        print(f"ERROR: cannot read YouTube Analytics: {e}.\n"
              f"Run the one-time consent: {AUTH_CMD}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: YouTube API failed: {e}", file=sys.stderr)
        return 1

    md = build_report(api, log_stats(today), start, end, today, a.mock)
    print(md)
    DATA.mkdir(exist_ok=True)
    if a.dry_run:
        out = DATA / f"weekly-report-{today.isoformat()}.md"
        out.write_text(md, encoding="utf-8")
        print(f"[dry-run] wrote {out}; nothing posted")
        return 0
    try:
        post_discord(md)
    except Exception as e:
        print(f"ERROR: Discord post failed: {e}", file=sys.stderr)
        return 1
    (DATA / "last-success-weekly").write_text(
        datetime.now(timezone.utc).isoformat(timespec="seconds"), encoding="utf-8")
    print("posted; last-success-weekly written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
