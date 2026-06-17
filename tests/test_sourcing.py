"""Sourcing People DB : pagination, exclusion des déjà-vus, projection, arrêts (target/quota/épuisement)."""
from prospect_engine import lemlist, sourcing


def _r(url, name="X Y", title="Gérant", company="Agence"):
    return {"lead_linkedin_url": url, "full_name": name, "title": title,
            "current_exp_company_name": company, "location": "Lyon", "lead_id": url[-1]}


def _page(*urls):
    return (200, {"results": [_r(u) for u in urls], "limitation": 1999})


def test_source_projects_people_db_result_to_lead(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: _page("https://lk/a"))
    out = sourcing.source("KEY", filters=[], seen=set(), target=1)
    lead = out["candidats"][0]
    assert lead["linkedinUrl"] == "https://lk/a"
    assert lead["fullName"] == "X Y" and lead["jobTitle"] == "Gérant" and lead["companyName"] == "Agence"


def test_source_excludes_seen(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: _page("https://lk/a", "https://lk/b"))
    out = sourcing.source("KEY", filters=[], seen={"https://lk/a"}, target=5)
    assert [c["linkedinUrl"] for c in out["candidats"]] == ["https://lk/b"]


def test_source_stops_at_target(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: _page("https://lk/a", "https://lk/b", "https://lk/c"))
    out = sourcing.source("KEY", filters=[], seen=set(), target=2)
    assert len(out["candidats"]) == 2


def test_source_dedups_within_results(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: _page("https://lk/a", "https://lk/a"))
    out = sourcing.source("KEY", filters=[], seen=set(), target=5)
    assert len(out["candidats"]) == 1


def test_source_paginates_until_target(monkeypatch):
    pages = {1: _page(*[f"https://lk/{i}" for i in range(100)]),
             2: _page("https://lk/x", "https://lk/y")}
    monkeypatch.setattr(lemlist, "search_people", lambda key, filters, page, size: pages[page])
    out = sourcing.source("KEY", filters=[], seen=set(), target=101, size=100)
    assert len(out["candidats"]) == 101 and out["pages_used"] == 2


def test_source_marks_exhausted_on_short_page(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: _page("https://lk/a"))
    out = sourcing.source("KEY", filters=[], seen=set(), target=50, size=100)
    assert out["exhausted"] is True


def test_source_propagates_limitation(monkeypatch):
    monkeypatch.setattr(lemlist, "search_people", lambda *a, **k: (200, {"results": [_r("https://lk/a")], "limitation": 42}))
    out = sourcing.source("KEY", filters=[], seen=set(), target=1)
    assert out["limitation"] == 42
