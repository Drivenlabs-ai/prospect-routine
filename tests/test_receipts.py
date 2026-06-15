"""Ledger de reçus : clé d'idempotence + repli sur la dernière ligne par (campagne, lead)."""
from prospect_engine import receipts


def test_lead_key_prefers_linkedin_url():
    assert receipts.lead_key({"linkedinUrl": "https://lk/in/x", "email": "x@y.z"}) == "https://lk/in/x"


def test_lead_key_falls_back_to_email():
    assert receipts.lead_key({"email": "x@y.z"}) == "x@y.z"


def test_lead_key_none_when_no_identifier():
    assert receipts.lead_key({"fullName": "X Y"}) is None


def test_append_then_lookup_returns_receipt(tmp_path):
    rec = {"campaign_id": "cam_1", "lead_key": "k1", "contact_id": "ctc_1",
           "lead_id": "lea_1", "stage": "varset", "ok": True}
    receipts.append_receipt(str(tmp_path), rec)
    found = receipts.lookup(str(tmp_path), "cam_1", "k1")
    assert found is not None
    assert found["stage"] == "varset"
    assert found["lead_id"] == "lea_1"


def test_ledger_folds_to_latest_line_per_key(tmp_path):
    receipts.append_receipt(str(tmp_path), {"campaign_id": "cam_1", "lead_key": "k1", "stage": "created", "ok": True})
    receipts.append_receipt(str(tmp_path), {"campaign_id": "cam_1", "lead_key": "k1", "stage": "launched", "ok": True})
    ledger = receipts.read_ledger(str(tmp_path))
    assert ledger[("cam_1", "k1")]["stage"] == "launched"


def test_lookup_isolated_per_campaign(tmp_path):
    receipts.append_receipt(str(tmp_path), {"campaign_id": "cam_1", "lead_key": "k1", "stage": "launched", "ok": True})
    assert receipts.lookup(str(tmp_path), "cam_2", "k1") is None


def test_lookup_none_when_empty(tmp_path):
    assert receipts.lookup(str(tmp_path), "cam_1", "k1") is None
