"""Daily-run status helper for run_daily.cmd.

  python scripts/daily_status.py ok
      write data/last-success (ISO time) - read by the claude-status watcher dead-man switch.
  python scripts/daily_status.py fail <key> <message...>
      post an alert to the Discord webhook (webhook URL is read from the claude-status
      config.json, never printed). Same key is sent at most once per 6 hours.

NOTIFY_DRY=1 prints instead of posting. Never raises: always exits 0.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEBHOOK_CONFIG = Path("C:/Users/user/Desktop/dev/claude status/config.json")
BUMP_FILE = Path("C:/Users/user/Desktop/dev/claude status/dashboard.bump")
DEDUPE_SECONDS = 6 * 3600
REASON_FILE = DATA / "last-failure-reason.txt"


def write_ok() -> None:
    DATA.mkdir(exist_ok=True)
    (DATA / "last-success").write_text(
        datetime.now(timezone.utc).isoformat(timespec="seconds"), encoding="utf-8")
    print("last-success written")


def failure_reason(key: str, message: str) -> str:
    """Only for produce_daily.py exit 2 (GPU busy): today's reason written by produce_daily.py."""
    if key != "produce" or "(exit 2)" not in message:
        return ""
    try:
        first, _, rest = REASON_FILE.read_text(encoding="utf-8").partition("\n")
        if first.strip() != datetime.now().date().isoformat() or not rest.strip():
            return ""
        return ("\n\u539f\u56e0\uff1a" + rest.strip()
                + "\n\u4eca\u5929\u4ecd\u6703\u7167\u5e38\u5617\u8a66\u4e0a\u50b3\u4f47\u5217\u4e2d\u7684\u820a\u5f71\u7247"
                "\uff08\u4e0a\u50b3\u5931\u6557\u6703\u53e6\u5916\u901a\u77e5\uff09")
    except Exception:
        return ""


def notify_fail(key: str, message: str) -> None:
    DATA.mkdir(exist_ok=True)
    state_file = DATA / "notify-state.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        state = {}
    now = time.time()
    if now - state.get(key, 0) < DEDUPE_SECONDS:
        print(f"deduped ({key}) - already alerted within 6h")
        return
    content = f"\u26a0\ufe0f Lofi Shorts: {message}" + failure_reason(key, message)
    if os.environ.get("NOTIFY_DRY") == "1":
        print("NOTIFY_DRY would post: " + content)
        return
    else:
        url = json.loads(WEBHOOK_CONFIG.read_text(encoding="utf-8"))["webhookUrl"]
        req = urllib.request.Request(
            url, data=json.dumps({"content": content}).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "lofi-daily-notify/1.0"})
        urllib.request.urlopen(req, timeout=15).read()
        try:  # tell the watcher its dashboard was pushed up; never fail the caller
            BUMP_FILE.write_text(datetime.now(timezone.utc).isoformat(timespec="seconds"), encoding="utf-8")
        except Exception:
            pass
    state[key] = now
    state_file.write_text(json.dumps(state), encoding="utf-8")


if __name__ == "__main__":
    try:
        if len(sys.argv) >= 2 and sys.argv[1] == "ok":
            write_ok()
        elif len(sys.argv) >= 4 and sys.argv[1] == "fail":
            notify_fail(sys.argv[2], " ".join(sys.argv[3:]))
        else:
            print(__doc__)
    except Exception as e:  # never break the caller
        print(f"daily_status error: {e}", file=sys.stderr)
    sys.exit(0)
