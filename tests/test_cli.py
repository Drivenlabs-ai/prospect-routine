"""Intégration CLI : l'entrée stable `python3 scripts/routine.py <cmd>` dispatche correctement.
Couvre les commandes sans réseau (resolve, status, dedup-check, commit-state)."""
import json
import subprocess
import sys
from pathlib import Path

ROUTINE = Path(__file__).resolve().parent.parent / "scripts" / "routine.py"


def run(*args):
    return subprocess.run([sys.executable, str(ROUTINE), *args], capture_output=True, text=True)


def _campaign(tmp_path):
    cfg = tmp_path / "campaign.json"
    cfg.write_text(json.dumps({"campaign_id": "cam_1", "slug": "agence-immo",
                               "state_dir": str(tmp_path / "state")}))
    return str(cfg)


def test_cli_resolve_by_slug(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps([{"slug": "agence-immo", "campaign_id": "cam_1"},
                               {"slug": "saas-cto", "campaign_id": "cam_2"}]))
    r = run("resolve", "--registry", str(reg), "--slug", "agence-immo")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["campaign_id"] == "cam_1"


def test_cli_status_set_then_get(tmp_path):
    cfg = _campaign(tmp_path)
    run("status", "--config", cfg, "--set", "phase1_done=true")
    r = run("status", "--config", cfg, "--get", "phase1_done")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"phase1_done": True}


def test_cli_commit_state_then_dedup_flags_seen(tmp_path):
    cfg = _campaign(tmp_path)
    sourced = tmp_path / "sourced.json"
    sourced.write_text(json.dumps(["https://lk/a"]))
    r1 = run("commit-state", "--config", cfg, "--date", "2026-06-15",
             "--sourced-file", str(sourced), "--true", "1", "--false", "0")
    assert r1.returncode == 0, r1.stderr

    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps([{"linkedinUrl": "https://lk/a", "fullName": "A B"},
                                 {"linkedinUrl": "https://lk/b", "fullName": "C D"}]))
    r2 = run("dedup-check", "--config", cfg, "--input", str(leads))
    assert r2.returncode == 0, r2.stderr
    out = json.loads(r2.stdout)
    assert [l["linkedinUrl"] for l in out["allowed"]] == ["https://lk/b"]
    assert out["skipped"][0]["reason"] == "already_seen"
