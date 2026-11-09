"""One-time OAuth setup for YouTube upload.

Prereq: secrets/client_secret.json downloaded from Google Cloud Console.
Run:    python pipeline/yt_auth.py
Opens a browser for consent, then stores a refresh token in
secrets/token.json for unattended use by upload_queue.py. The previous token
is kept next to it as token.json.bak-<timestamp>.

Prints the channel the new token acts as. upload_queue.py only uploads when
that id equals upload_channel_id in pipeline/pool/config.json.
"""
import sys
from datetime import datetime
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "secrets"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",       # video stats
    "https://www.googleapis.com/auth/yt-analytics.readonly",  # traffic sources
]


def main() -> None:
    client_secret = SECRETS / "client_secret.json"
    assert client_secret.exists(), (
        f"missing {client_secret} - download the OAuth client JSON from "
        "Google Cloud Console and save it there first"
    )
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=0, prompt="select_account consent")

    token = SECRETS / "token.json"
    if token.exists():
        stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        backup = token.with_name(f"token.json.bak-{stamp}")
        backup.write_bytes(token.read_bytes())
        print(f"previous token kept: {backup.name}")
    token.write_text(creds.to_json(), encoding="utf-8")
    print("OK: token saved to secrets/token.json")

    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    if not items:
        print("WARNING: this account has no YouTube channel yet - create one, "
              "then run this again")
    for ch in items:
        print(f"channel: {ch['snippet']['title']} ({ch['id']})")


if __name__ == "__main__":
    main()
