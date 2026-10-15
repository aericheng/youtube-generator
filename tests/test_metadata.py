"""Tests for pipeline/metadata.py. Run: python tests/test_metadata.py (no pytest needed)."""
import json
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import metadata as md  # noqa: E402

TOPIC = {"id": "rain-on-leaves", "category": "water", "title": "Rain on Leaves 🌧 lofi ambience",
         "title_variants": ["A", "B", "C"], "keywords": ["rain", "relaxing"], "hashtag": "rainsounds",
         "scene_line": "Soft rain falling on green leaves."}
FOOTER = "footer line"


def test_title_rotation_skips_published():
    assert md.pick_title(TOPIC, set()) == "A"
    assert md.pick_title(TOPIC, {"A"}) == "B"
    assert md.pick_title(TOPIC, {"A", "B"}) == "C"


def test_title_never_repeats_after_exhaustion():
    taken = {"A", "B", "C"}
    t = md.pick_title(TOPIC, taken)
    assert t not in taken and t.startswith("A")
    taken.add(t)
    t2 = md.pick_title(TOPIC, taken)
    assert t2 not in taken and t2 != t


def test_real_topics_have_unique_variants_and_dont_clash_with_published():
    topics = json.loads((ROOT / "pipeline" / "pool" / "topics.json").read_text(encoding="utf-8"))
    published = {t["title"] for t in topics}  # the original single titles were all published
    seen = set()
    for t in topics:
        assert 3 <= len(t["title_variants"]) <= 4 and 3 <= len(t["keywords"]) <= 5, t["id"]
        assert md.pick_title(t, published) not in published, t["id"]
        for v in t["title_variants"]:
            assert v not in seen and len(v) <= md.MAX_TITLE, v
            seen.add(v)


def test_description_and_tags():
    m = md.build_metadata(TOPIC, FOOTER, set())
    assert "#shorts" in m["description"] and "#rainsounds" in m["description"]
    assert m["description"].startswith("Soft rain falling") and m["description"].endswith(FOOTER)
    assert m["tags"][:5] == md.BASE_TAGS and "rain" in m["tags"] and len(set(m["tags"])) == len(m["tags"])


def test_taken_titles_reads_queue_and_extra():
    with tempfile.TemporaryDirectory() as d:
        q = Path(d)
        (q / "x").mkdir()
        (q / "x" / "metadata.json").write_text(json.dumps({"title": "A"}), encoding="utf-8")
        assert md.taken_titles(q, {"Z"}) == {"A", "Z"}
        assert md.pick_title(TOPIC, md.taken_titles(q)) == "B"


def test_loop_units_read_from_config():
    cfg = json.loads((ROOT / "pipeline" / "pool" / "config.json").read_text(encoding="utf-8"))
    assert md.get_loop_units(cfg) == 1
    assert md.get_loop_units({"loop_units": 3}) == 3
    assert md.get_loop_units({}) == 1
    assert md.get_loop_units({"loop_units": 1}, override=4) == 4


def test_expected_duration_and_recut_length():
    assert abs(md.expected_duration(1, 8.54) - 8.54) < 1e-9
    assert abs(md.expected_duration(9, 8.54) - 76.86) < 1e-9
    lo, hi = md.duration_bounds(1, 8.5)
    assert abs(lo - 6.8) < 1e-9 and abs(hi - 11.05) < 1e-9
    assert abs(md.recut_unit_len(76.9) - 8.5444) < 1e-3


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
