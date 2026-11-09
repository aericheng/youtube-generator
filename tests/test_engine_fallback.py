"""Tests for the A14B -> Wan 5B master selection and the person check rule.
Run: python tests/test_engine_fallback.py (no pytest needed). Nothing is generated:
produce_daily.run and wait_until_idle are faked in a temp folder."""
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import produce_daily as p  # noqa: E402
import qc_people as q  # noqa: E402


REAL_RUN = p.run  # captured before master_with fakes it


class Fake:
    """people: person-check result per clip, in call order. crash: script name that fails."""

    def __init__(self, people=(), crash=None, slots=()):
        """slots: clear_to_start answers in call order; yes once they run out."""
        self.people, self.crash, self.slots = list(people), crash, list(slots)
        self.seeds, self.calls, self.gates = [], [], []

    def clear(self, last_start):
        self.gates.append(last_start)
        return self.slots.pop(0) if self.slots else True

    def run(self, cmd, timeout_min=30, ok_codes=(0,)):
        cmd = [str(c) for c in cmd]
        script = Path(cmd[1]).name
        self.calls.append(script)
        if script == self.crash:
            raise RuntimeError(f"{script} failed")
        if script == "generate_video_a14b.py":
            self.seeds.append(int(cmd[cmd.index("--seed") + 1]))
            Path(cmd[cmd.index("--out-dir") + 1]).mkdir(parents=True, exist_ok=True)
        elif script == "upscale_clip.py":
            Path(cmd[3]).write_bytes(b"a14b")
        elif script == "generate_video.py":
            Path(cmd[cmd.index("--out") + 1]).write_bytes(b"5b")
        rc = 3 if script == "qc_people.py" and self.people.pop(0) else 0
        return subprocess.CompletedProcess(cmd, rc)


def master_with(fake: Fake):
    tmp = Path(tempfile.mkdtemp())
    try:
        p.run, p.clear_to_start = fake.run, fake.clear
        master = tmp / "clip_master.mp4"
        engine = p.make_master(tmp, tmp / "scene.json", 100, 5, master)
        content = master.read_bytes() if master.exists() else None
        return engine, content, sorted(x.name for x in tmp.iterdir())
    finally:
        shutil.rmtree(tmp)


def test_clean_a14b_take_becomes_master():
    fake = Fake(people=[False])
    engine, content, left = master_with(fake)
    assert (engine, content) == ("a14b", b"a14b")
    assert fake.seeds == [100] and "generate_video.py" not in fake.calls
    assert left == ["clip_master.mp4"]


def test_person_retries_with_new_seed():
    fake = Fake(people=[True, False])
    engine, content, _ = master_with(fake)
    assert (engine, content) == ("a14b", b"a14b")
    assert fake.seeds == [100, 1100]


def test_two_person_takes_fall_back_to_5b():
    fake = Fake(people=[True, True, False])
    engine, content, _ = master_with(fake)
    assert (engine, content) == ("5b", b"5b")
    assert fake.seeds == [100, 1100]


def test_a14b_crash_goes_straight_to_5b():
    fake = Fake(people=[False], crash="generate_video_a14b.py")
    engine, content, _ = master_with(fake)
    assert (engine, content) == ("5b", b"5b")


def test_broken_check_counts_as_failure_not_clean():
    fake = Fake(people=[False], crash="upscale_clip.py")
    assert master_with(fake)[0] == "5b"


def test_no_time_for_retry_uses_5b():
    fake = Fake(people=[True, False], slots=[False, True])
    engine, _, _ = master_with(fake)
    assert engine == "5b" and fake.seeds == [100]
    assert fake.gates == [p.IDLE_DEADLINE, p.FALLBACK_DEADLINE]


def test_no_slot_for_5b_does_not_generate():
    fake = Fake(people=[True], slots=[False, False])
    try:
        master_with(fake)
    except p.NoSlot:
        assert "generate_video.py" not in fake.calls
    else:
        raise AssertionError("expected NoSlot")


def test_a14b_crash_still_waits_for_a_5b_slot():
    fake = Fake(crash="generate_video_a14b.py", slots=[False])
    try:
        master_with(fake)
    except p.NoSlot:
        assert fake.gates == [p.FALLBACK_DEADLINE] and "generate_video.py" not in fake.calls
    else:
        raise AssertionError("expected NoSlot")


def test_stray_bytes_stay_printable_in_cp950():
    child = [p.PY, "-c", "import sys; sys.stderr.buffer.write(b'\\xff\\xfe\\x81'); sys.exit(1)"]
    try:
        REAL_RUN(child)
    except RuntimeError as e:
        str(e).encode("cp950")  # the scheduled run prints this message
    else:
        raise AssertionError("expected RuntimeError")


def test_retry_success_removes_the_first_take():
    fake = Fake(people=[True, False])
    assert master_with(fake)[2] == ["clip_master.mp4"]


def test_person_in_5b_leaves_no_master():
    fake = Fake(people=[True, True, True])
    engine, content, _ = master_with(fake)
    assert engine is None and content is None


def test_rule_ignores_lone_flame_spikes():
    scores = np.zeros(40)
    scores[[3, 9, 15]] = 0.9
    assert not q.flagged(scores)


def test_rule_catches_short_visit():
    scores = np.zeros(40)
    scores[10:14] = 0.9
    assert q.flagged(scores)


def test_rule_catches_scattered_presence():
    scores = np.zeros(40)
    scores[::4] = 0.9
    assert q.flagged(scores)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS", name)
        except Exception:
            failed += 1
            print("FAIL", name)
            traceback.print_exc()
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
