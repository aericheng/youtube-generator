"""Pre-audit API smoke test: upload ONE throwaway file as private.

The uploaded video will be permanently locked private (expected for an
unaudited project) - it is a disposable test artifact, delete it in Studio
afterwards. Never point this at real queue videos.

Usage: python pipeline/yt_smoketest.py <path-to-throwaway.mp4>
"""
import sys

from upload_queue import yt_client, upload


def main() -> None:
    video = sys.argv[1]
    assert "queue" not in video.replace("\\", "/").lower(), \
        "refusing to smoke-test with a queue video - use a throwaway file"
    meta = {
        "title": "API test - delete me",
        "description": "Throwaway upload to verify API access. Safe to delete.",
        "tags": ["test"],
        "ai_disclosure": True,
    }
    yt = yt_client()
    vid = upload(yt, video, meta, privacy="private")
    print(f"OK videoId={vid} (locked private - expected pre-audit; "
          f"delete it in YouTube Studio)")


if __name__ == "__main__":
    main()
