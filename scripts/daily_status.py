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
DEDUPE_SECONDS = 6 * 3600


def write_ok() -> None:
    DATA.mkdir(exist_ok=True)
    (DATA / "last-success").write_text(
        datetime.now(timezone.utc).isoformat(timespec="seconds"), encoding="utf-8")
    print("last-success written")


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
    content = f"\u26a0\ufe0f Lofi Shorts: {message}"
    if os.environ.get("NOTIFY_DRY") == "1":
        print("NOTIFY_DRY would post: " + content)
        return
    else:
        url = json.loads(WEBHOOK_CONFIG.read_text(encoding="utf-8"))["webhookUrl"]
        req = urllib.request.Request(
            url, data=json.dumps({"content": content}).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "lofi-daily-notify/1.0"})
        urllib.request.urlopen(req, timeout=15).read()
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
