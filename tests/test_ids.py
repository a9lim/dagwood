from dagwood.core.ids import _ALPHABET, new_id


def test_format():
    for _ in range(50):
        i = new_id(set())
        assert len(i) == 3
        assert all(c in _ALPHABET for c in i)


def test_unique_bulk():
    seen: set[str] = set()
    for _ in range(2000):
        i = new_id(seen)
        assert i not in seen
        seen.add(i)
    assert len(seen) == 2000


def test_avoids_existing():
    existing = {"abc", "xyz"}
    for _ in range(100):
        assert new_id(existing) not in existing


def test_grows_when_crowded():
    # Exhaust the entire single-char space so new_id must grow to 2 chars.
    full = set(_ALPHABET)
    i = new_id(full, length=1)
    assert len(i) >= 2
