"""Pull channel / per-video stats and Analytics, group by loop_units and upload week.

Writes data/analytics/<YYYY-MM-DD>.json and a Traditional Chinese summary .md.
loop_units comes from output/queue/*/metadata.json (matched by videoId); videos not
found there are treated as 9 when ~77 s long (the old format), otherwise unknown (None).
The token is loaded WITHOUT a scopes argument (uses the scopes it was granted).

Usage: python scripts/analytics_report.py
"""
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parent.parent
TOKEN = ROOT / "secrets" / "token.json"
OUT = ROOT / "data" / "analytics"
PER_VIDEO_METRICS = ["views,averageViewDuration,averageViewPercentage,engagedViews,likes",
                     "views,averageViewDuration,averageViewPercentage,likes"]  # fallback if engagedViews rejected


def secs(iso: str) -> int:
    h, m, s = (int(x or 0) for x in re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso).groups())
    return h * 3600 + m * 60 + s


def week_start(day: str) -> str:
    d = datetime.strptime(day[:10], "%Y-%m-%d").date()
    return (d - timedelta(days=d.weekday())).isoformat()


def loop_units_by_video() -> dict:
    out = {}
    for f in (ROOT / "output" / "queue").glob("*/metadata.json"):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if m.get("videoId"):
            out[m["videoId"]] = m.get("loop_units") or 9  # pre-F1 metadata has no field = 9 repeats
    return out


def infer_units(vid: str, dur: int, known: dict):
    if vid in known:
        return known[vid]
    if 70 <= dur <= 85:
        return 9
    return None  # unknown: other formats (kept apart from loop_units=1 videos)


def main() -> None:
    creds = Credentials.from_authorized_user_file(str(TOKEN))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)

    ch = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    start_all = ch["snippet"]["publishedAt"][:10]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    vids = []
    for i in range(0, len(ids), 50):
        vids += yt.videos().list(part="snippet,statistics,contentDetails,status",
                                 id=",".join(ids[i:i + 50])).execute()["items"]

    end = date.today().isoformat()

    def query(**kw):
        try:
            return ya.reports().query(ids="channel==MINE", startDate=start_all, endDate=end, **kw).execute()
        except HttpError as e:
            print(f"analytics query failed ({kw.get('dimensions')}): {e.status_code} {e.reason}")
            return None

    per_video = None
    for metrics in PER_VIDEO_METRICS:
        per_video = query(dimensions="video", metrics=metrics, sort="-views", maxResults=200)
        if per_video:
            break
    traffic = query(dimensions="insightTrafficSourceType", metrics="views,estimatedMinutesWatched", sort="-views")

    ana = {}
    if per_video:
        cols = [h["name"] for h in per_video["columnHeaders"]]
        for row in per_video.get("rows", []):
            d = dict(zip(cols, row))
            ana[d.pop("video")] = d

    known = loop_units_by_video()
    rows = []
    for v in vids:
        st, a = v["statistics"], ana.get(v["id"], {})
        dur = secs(v["contentDetails"]["duration"])
        rows.append({
            "videoId": v["id"], "title": v["snippet"]["title"], "published": v["snippet"]["publishedAt"][:10],
            "week": week_start(v["snippet"]["publishedAt"]), "duration_sec": dur,
            "loop_units": infer_units(v["id"], dur, known), "privacy": v["status"]["privacyStatus"],
            "views_api": int(st.get("viewCount", 0)), "likes_api": int(st.get("likeCount", 0)),
            "views": a.get("views"), "averageViewDuration": a.get("averageViewDuration"),
            "averageViewPercentage": a.get("averageViewPercentage"),
            "engagedViews": a.get("engagedViews"), "likes": a.get("likes"),
        })

    groups = defaultdict(list)
    for r in rows:
        groups[(r["loop_units"], r["week"])].append(r)
    summary = []
    for (lu, wk), rs in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        views = sum(r["views"] or 0 for r in rs)
        eng = sum(r["engagedViews"] or 0 for r in rs)
        pct = (sum((r["averageViewPercentage"] or 0) * (r["views"] or 0) for r in rs) / views) if views else None
        summary.append({"loop_units": lu, "week": wk, "videos": len(rs), "views": views,
                        "views_per_video": round(views / len(rs), 1),
                        "engagedViews": eng,
                        "engaged_ratio": round(eng / views, 3) if views else None,
                        "avg_view_pct": round(pct, 1) if pct is not None else None,
                        "likes": sum(r["likes"] or 0 for r in rs)})
    by_units = defaultdict(lambda: {"videos": 0, "views": 0, "eng": 0, "pw": 0.0})
    for s in summary:
        g = by_units[s["loop_units"]]
        g["videos"] += s["videos"]
        g["views"] += s["views"]
        g["eng"] += s["engagedViews"]
        g["pw"] += (s["avg_view_pct"] or 0) * s["views"]

    report = {"generated": end, "channel": {"title": ch["snippet"]["title"], **ch["statistics"]},
              "total_views_api": sum(r["views_api"] for r in rows), "videos": rows,
              "traffic_sources": traffic, "groups": summary}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{end}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    L = [f"# YouTube 成效報告 {end}", "",
         f"- 頻道：{ch['snippet']['title']}；訂閱 {ch['statistics'].get('subscriberCount')}、影片 {len(rows)} 支",
         f"- Data API 總觀看（所有上傳片加總）：{report['total_views_api']}", "",
         "## 依循環次數（loop_units）彙總", "",
         "| loop_units | 影片數 | 觀看 | 每支觀看 | engagedViews/views | 平均觀看比例 % |", "|---|---|---|---|---|---|"]
    for lu, g in sorted(by_units.items(), key=lambda kv: str(kv[0])):
        if g["views"]:
            L.append(f"| {lu} | {g['videos']} | {g['views']} | {g['views'] / g['videos']:.1f} | "
                     f"{g['eng'] / g['views']:.3f} | {g['pw'] / g['views']:.1f} |")
        else:
            L.append(f"| {lu} | {g['videos']} | 0 | 0 | - | - |")
    L += ["", "## 依 loop_units × 上架週", "",
          "| loop_units | 週（週一） | 影片數 | 觀看 | 每支觀看 | engaged/views | 平均觀看比例 % | 讚 |",
          "|---|---|---|---|---|---|---|---|"]
    for s in summary:
        L.append(f"| {s['loop_units']} | {s['week']} | {s['videos']} | {s['views']} | {s['views_per_video']} | "
                 f"{s['engaged_ratio']} | {s['avg_view_pct']} | {s['likes']} |")
    if traffic and traffic.get("rows"):
        L += ["", "## 流量來源（全期間）", "", "| 來源 | 觀看 | 觀看分鐘 |", "|---|---|---|"]
        L += [f"| {r[0]} | {r[1]} | {r[2]} |" for r in traffic["rows"]]
    (OUT / f"{end}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT / (end + '.json')} and .md; videos={len(rows)} total_views_api={report['total_views_api']}")


if __name__ == "__main__":
    main()
