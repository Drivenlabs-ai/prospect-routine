"""Pré-filtre local : évite des create-lead inutiles. La correction reste tenue par le natif."""
from prospect_engine import dedup


def _lead(url):
    return {"linkedinUrl": url, "fullName": "X Y"}


def test_allows_fresh_lead():
    out = dedup.dedup_check([_lead("https://lk/a")], ledger={}, campaign_id="cam_1")
    assert [l["linkedinUrl"] for l in out["allowed"]] == ["https://lk/a"]
    assert out["skipped"] == []


def test_does_not_skip_when_loaded_in_other_campaign():
    ledger = {("cam_2", "https://lk/a"): {"stage": "varset"}}
    out = dedup.dedup_check([_lead("https://lk/a")], ledger=ledger, campaign_id="cam_1")
    assert len(out["allowed"]) == 1


def test_dedup_check_flags_already_loaded():
    leads = [{"linkedinUrl": "https://lk/a"}, {"linkedinUrl": "https://lk/b"}]
    ledger = {("cam_1", "https://lk/a"): {"stage": "varset"}}
    out = dedup.dedup_check(leads, ledger, "cam_1")
    assert [l["linkedinUrl"] for l in out["allowed"]] == ["https://lk/b"]
    assert out["skipped"][0]["reason"] == "already_loaded"


def test_dedup_check_flags_no_identifier():
    out = dedup.dedup_check([{"fullName": "Sans URL"}], {}, "cam_1")
    assert out["allowed"] == [] and out["skipped"][0]["reason"] == "no_identifier"
