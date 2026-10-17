"""In-memory TTL case store."""

from app.services.case_store import DEMO_CASE_ID, CaseStore, get_case_store, load_demo_case


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make_case(case_id):
    return load_demo_case().model_copy(update={"case_id": case_id, "is_demo": False})


def test_put_and_get_round_trip():
    store = CaseStore()
    store.put(make_case("case-a"))
    assert store.get("case-a").case_id == "case-a"
    assert store.get("missing") is None


def test_cases_expire_after_ttl():
    clock = FakeClock()
    store = CaseStore(ttl_seconds=60, clock=clock)
    store.put(make_case("case-a"))
    clock.now += 59
    assert store.get("case-a") is not None
    clock.now += 1
    assert store.get("case-a") is None
    assert len(store) == 0


def test_pinned_cases_never_expire():
    clock = FakeClock()
    store = CaseStore(ttl_seconds=60, clock=clock)
    store.put(load_demo_case(), pinned=True)
    clock.now += 10**9
    assert store.get(DEMO_CASE_ID).is_demo is True


def test_oldest_cases_are_evicted_beyond_capacity():
    store = CaseStore(max_cases=2)
    for case_id in ("case-1", "case-2", "case-3"):
        store.put(make_case(case_id))
    assert store.get("case-1") is None
    assert store.get("case-2") and store.get("case-3")


def test_case_ids_are_unique_and_unguessable():
    ids = {CaseStore.new_case_id() for _ in range(500)}
    assert len(ids) == 500
    assert all(i.startswith("case-") and len(i) >= 20 for i in ids)


def test_shared_store_preloads_demo_case():
    assert get_case_store().get(DEMO_CASE_ID).case_id == DEMO_CASE_ID
