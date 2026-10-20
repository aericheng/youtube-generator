"""Tests for the run-last idle gate in pipeline/produce_daily.py.
Run: python tests/test_idle_gate.py (no pytest needed). Nothing real is probed:
the clock, sleep and busy_reason are faked."""
import datetime as real_dt
import sys
import traceback
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import produce_daily as p  # noqa: E402


class Clock:
    def __init__(self, hhmm: str):
        h, m = map(int, hhmm.split(":"))
        self.now = real_dt.datetime(2026, 10, 21, h, m)
        self.sleeps = 0


def install(clock: Clock, reasons):
    """reasons: list consumed per busy_reason() call; the last one repeats."""
    calls = []

    class FakeDateTime(real_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.now

    p.datetime = types.SimpleNamespace(datetime=FakeDateTime, timedelta=real_dt.timedelta,
                                       date=real_dt.date)

    def fake_sleep(sec):
        clock.sleeps += 1
        clock.now += real_dt.timedelta(seconds=sec)

    def fake_reason():
        calls.append(clock.now)
        return reasons[min(len(calls) - 1, len(reasons) - 1)]

    p.time = types.SimpleNamespace(sleep=fake_sleep, time=lambda: 0)
    p.busy_reason = fake_reason
    p.LAST_BUSY = ""
    return calls


def test_idle_starts_right_away():
    c = Clock("07:00")
    calls = install(c, [None])
    assert p.wait_until_idle() is True
    assert c.sleeps == 0 and len(calls) == 1


def test_waits_while_busy_then_starts():
    c = Clock("07:00")
    install(c, ["CPU 54% >= 30%", "CPU 54% >= 30%", None])
    assert p.wait_until_idle() is True
    assert c.sleeps == 2
    assert c.now == real_dt.datetime(2026, 10, 21, 7, 30)


def test_gives_up_at_deadline():
    c = Clock("07:00")
    install(c, ["GPU in use by python.exe pid 1 473 MiB"])
    assert p.wait_until_idle() is False
    assert p.LAST_BUSY.startswith("GPU in use")
    assert c.now <= real_dt.datetime(2026, 10, 21, 20, 30)


def test_no_start_window_skips_probe():
    c = Clock("11:40")
    calls = install(c, [None])
    assert p.wait_until_idle() is True
    assert calls and calls[0] >= real_dt.datetime(2026, 10, 21, 13, 0)


def test_after_deadline_checks_once():
    c = Clock("21:00")
    calls = install(c, ["RAM 10.0 GB available < 16 GB"])
    assert p.wait_until_idle() is False
    assert c.sleeps == 0 and len(calls) == 1
    c2 = Clock("21:00")
    install(c2, [None])
    assert p.wait_until_idle() is True


def test_nvidia_smi_failure_counts_as_busy():
    real_free = p.free_vram_mb

    def broken():
        raise RuntimeError("nvidia-smi failed")

    p.free_vram_mb = broken
    try:
        reason = REAL_BUSY_REASON()
        assert reason.startswith("nvidia-smi unavailable"), reason
    finally:
        p.free_vram_mb = real_free


REAL_BUSY_REASON = p.busy_reason  # captured at import, before install() fakes it


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception:
                failed += 1
                print("FAIL", name)
                traceback.print_exc()
    sys.exit(1 if failed else 0)
