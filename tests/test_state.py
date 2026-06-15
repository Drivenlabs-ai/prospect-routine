"""État machine : déjà-vus (fenêtre glissante), historique, status de reprise — écritures atomiques."""
from prospect_engine import state


def test_merge_seen_dedups_and_stringifies():
    assert state.merge_seen([1, 2], [2, 3, "3"]) == ["1", "2", "3"]


def test_merge_seen_preserves_first_seen_order():
    assert state.merge_seen(["b", "a"], ["a", "c"]) == ["b", "a", "c"]


def test_apply_commit_appends_history_entry():
    st = {"seen_lead_ids": [], "page_cursor": 1, "last_run": None, "history": []}
    state.apply_commit(st, "2026-06-15", ["x", "y"], 1, 1)
    assert st["last_run"] == "2026-06-15"
    assert st["history"][-1] == {"date": "2026-06-15", "sourced": 2, "true": 1, "false": 1}
    assert st["seen_lead_ids"] == ["x", "y"]


def test_apply_commit_sliding_window_caps_seen():
    st = {"seen_lead_ids": ["a", "b", "c"], "page_cursor": 1, "last_run": None, "history": []}
    state.apply_commit(st, "2026-06-15", ["d", "e"], 0, 0, seen_cap=3)
    assert st["seen_lead_ids"] == ["c", "d", "e"]


def test_save_load_state_roundtrip(tmp_path):
    st = {"seen_lead_ids": ["x"], "page_cursor": 2, "last_run": "2026-06-15", "history": []}
    state.save_state(str(tmp_path), st)
    assert state.load_state(str(tmp_path)) == st


def test_load_state_default_when_absent(tmp_path):
    st = state.load_state(str(tmp_path / "nope"))
    assert st == {"seen_lead_ids": [], "page_cursor": 1, "last_run": None, "history": []}


def test_status_set_get_roundtrip(tmp_path):
    state.status_set(str(tmp_path), "phase1_done", True)
    state.status_set(str(tmp_path), "w2_steps", ["campaign", "sequence"])
    assert state.status_get(str(tmp_path), "phase1_done") is True
    assert state.status_get(str(tmp_path), "w2_steps") == ["campaign", "sequence"]


def test_load_status_default_when_absent(tmp_path):
    assert state.load_status(str(tmp_path)) == {
        "phase1_done": False, "w2_steps": [], "edit_in_progress": False, "last_run": None}
