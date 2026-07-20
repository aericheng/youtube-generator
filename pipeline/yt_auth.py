"""One-time OAuth setup for YouTube upload.

Prereq: secrets/client_secret.json downloaded from Google Cloud Console.
Run:    python pipeline/yt_auth.py
Opens a browser for consent, then stores a refresh token in
secrets/token.json for unattended use by upload_queue.py.
"""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "secrets"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    client_secret = SECRETS / "client_secret.json"
    assert client_secret.exists(), (
        f"missing {client_secret} - download the OAuth client JSON from "
        "Google Cloud Console and save it there first"
    )
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    (SECRETS / "token.json").write_text(creds.to_json(), encoding="utf-8")
    print("OK: token saved to secrets/token.json")


if __name__ == "__main__":
    main()
