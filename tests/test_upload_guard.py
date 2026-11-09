"""Tests for the upload channel gate in pipeline/upload_queue.py.
Run: python tests/test_upload_guard.py (no pytest needed).

Everything runs in a temp folder with a stub YouTube client: no network, no
real token, no real queue.
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import upload_queue as uq  # noqa: E402

NEW_CHANNEL = "UCnewchannel"
PERSONAL_CHANNEL = "UCpersonal"


class FakeYouTube:
    """Answers channels().list(...).execute() with the given channel ids."""

    def __init__(self, ids):
        self.ids = ids

    def channels(self):
        return self

    def list(self, **_):
        return self

    def execute(self):
        if isinstance(self.ids, Exception):
            raise self.ids
        return {"items": [{"id": i} for i in self.ids]}


def run_main(channel_id, token_channels, token_exists=True):
    """Run upload_queue.main() against a temp project.
    Returns (exit_code, uploads, metadata, stdout, stderr)."""
    tmp = Path(tempfile.mkdtemp())
    (tmp / "pipeline" / "pool").mkdir(parents=True)
    (tmp / "secrets").mkdir()
    if token_exists:
        (tmp / "secrets" / "token.json").write_text("{}", encoding="utf-8")
    cfg = {"upload_privacy": "public"}
    if channel_id is not None:
        cfg["upload_channel_id"] = channel_id
    (tmp / "pipeline" / "pool" / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    folder = tmp / "output" / "queue" / "2026-11-06-test"
    folder.mkdir(parents=True)
    (folder / "2026-11-06-test.mp4").write_bytes(b"x")
    meta_file = folder / "metadata.json"
    meta_file.write_text(json.dumps({"title": "t", "description": "d"}), encoding="utf-8")

    uploads = []
    saved = (uq.ROOT, uq.QUEUE, uq.SECRETS, uq.yt_client, uq.upload, sys.argv)

    def fake_upload(yt, video, meta, privacy):
        uploads.append(video.name)
        return "newVideoId"

    uq.ROOT, uq.QUEUE, uq.SECRETS = tmp, tmp / "output" / "queue", tmp / "secrets"
    uq.yt_client = lambda: FakeYouTube(token_channels)
    uq.upload = fake_upload
    sys.argv = ["upload_queue.py"]
    out, err, code = io.StringIO(), io.StringIO(), 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            uq.main()
    except SystemExit as e:
        code = e.code
    except Exception as e:
        code = f"raised {type(e).__name__}"
    finally:
        uq.ROOT, uq.QUEUE, uq.SECRETS, uq.yt_client, uq.upload, sys.argv = saved
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    shutil.rmtree(tmp, ignore_errors=True)
    return code, uploads, meta, out.getvalue(), err.getvalue()


def test_empty_id_pauses_without_uploading():
    code, uploads, meta, out, _ = run_main("", [NEW_CHANNEL])
    assert code == 0 and uploads == [] and "videoId" not in meta
    assert "paused" in out and "1 video" in out


def test_missing_key_pauses_without_uploading():
    code, uploads, _, out, _ = run_main(None, [NEW_CHANNEL])
    assert code == 0 and uploads == [] and "paused" in out


def test_whitespace_id_pauses_without_uploading():
    code, uploads, _, out, _ = run_main("   ", [NEW_CHANNEL])
    assert code == 0 and uploads == [] and "paused" in out


def test_wrong_channel_refuses_and_exits_1():
    code, uploads, meta, _, err = run_main(NEW_CHANNEL, [PERSONAL_CHANNEL])
    assert code == 1 and uploads == [] and "videoId" not in meta
    assert "REFUSING" in err and PERSONAL_CHANNEL in err


def test_no_channel_on_token_refuses():
    code, uploads, _, _, err = run_main(NEW_CHANNEL, [])
    assert code == 1 and uploads == [] and "REFUSING" in err


def test_ambiguous_token_refuses():
    code, uploads, _, _, _ = run_main(NEW_CHANNEL, [NEW_CHANNEL, PERSONAL_CHANNEL])
    assert code == 1 and uploads == []


def test_channel_lookup_error_does_not_upload():
    code, uploads, meta, _, _ = run_main(NEW_CHANNEL, RuntimeError("quota"))
    assert code == "raised RuntimeError" and uploads == [] and "videoId" not in meta


def test_missing_token_alerts_without_uploading():
    code, uploads, _, _, err = run_main(NEW_CHANNEL, [NEW_CHANNEL], token_exists=False)
    assert code == 1 and uploads == [] and "no OAuth token" in err


def test_matching_channel_uploads():
    code, uploads, meta, _, _ = run_main(NEW_CHANNEL, [NEW_CHANNEL])
    assert code == 0 and uploads == ["2026-11-06-test.mp4"]
    assert meta["videoId"] == "newVideoId" and meta["uploaded_privacy"] == "public"


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                failed += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    print(f"{failed} failed" if failed else "all passed")
    sys.exit(1 if failed else 0)
