"""Config & registre : clé API, chargement campaign.json + prompts, résolution slug↔campaign_id."""
import json

import pytest

from prospect_engine import config


def test_read_key_extracts_value(tmp_path):
    f = tmp_path / "k.local.md"
    f.write_text("---\nlemlist_api_key: abc123XYZ\n---\n")
    assert config.read_key(str(f)) == "abc123XYZ"


def test_read_key_missing_raises(tmp_path):
    f = tmp_path / "k.local.md"
    f.write_text("nothing here\n")
    with pytest.raises(SystemExit):
        config.read_key(str(f))


def _registry(tmp_path):
    reg = tmp_path / "campaigns-registry.json"
    reg.write_text(json.dumps([
        {"slug": "agence-immo", "campaign_id": "cam_1", "folder": "Agence Immo",
         "channels": ["linkedin"], "status": "active", "config_path": "x/campaign.json"},
        {"slug": "saas-cto", "campaign_id": "cam_2", "folder": "SaaS CTO",
         "channels": ["email"], "status": "active", "config_path": "y/campaign.json"}]))
    return str(reg)


def test_resolve_campaign_by_slug(tmp_path):
    out = config.resolve_campaign(_registry(tmp_path), slug="saas-cto")
    assert out["campaign_id"] == "cam_2"


def test_resolve_campaign_by_campaign_id(tmp_path):
    out = config.resolve_campaign(_registry(tmp_path), campaign_id="cam_1")
    assert out["slug"] == "agence-immo"


def test_resolve_campaign_unknown_raises(tmp_path):
    with pytest.raises(SystemExit):
        config.resolve_campaign(_registry(tmp_path), slug="ghost")


def _campaign(tmp_path, seq=("icebreaker",)):
    pdir = tmp_path / "prompts"
    pdir.mkdir()
    (pdir / "icpFit.md").write_text("Décide si ce profil est une agence immo.")
    for s in seq:
        (pdir / f"{s}.md").write_text(f"Rédige le message {s}.")
    cfg = tmp_path / "campaign.json"
    cfg.write_text(json.dumps({"campaign_id": "cam_1", "slug": "agence-immo",
                               "sequence": list(seq), "prompts_dir": "prompts",
                               "state_dir": str(tmp_path / "state"), "dry_run": True}))
    return str(cfg)


def test_load_config_reads_config_and_prompts(tmp_path):
    cfg, prompts = config.load_config(_campaign(tmp_path))
    assert cfg["campaign_id"] == "cam_1"
    assert "icpFit" in prompts and "icebreaker" in prompts
    assert prompts["icebreaker"].strip() == "Rédige le message icebreaker."


def test_load_cfg_only_reads_json_without_prompts(tmp_path):
    # un campaign.json dont les prompts n'existent pas : load_cfg_only ne doit PAS échouer
    cfg_path = tmp_path / "campaign.json"
    cfg_path.write_text(json.dumps({"campaign_id": "cam_9", "sequence": ["icebreaker"],
                                    "prompts_dir": "prompts", "state_dir": str(tmp_path)}))
    cfg = config.load_cfg_only(str(cfg_path))
    assert cfg["campaign_id"] == "cam_9"


def test_load_config_loads_message_prompts_without_sequence_field(tmp_path):
    # campaign.json SANS `sequence` (la structure vit dans Lemlist) : les prompts de message
    # se chargent quand même, par découverte des fichiers du dossier.
    cfg_path = tmp_path / "campaign.json"
    cfg_path.write_text(json.dumps({"campaign_id": "cam_1", "prompts_dir": "prompts",
                                    "state_dir": str(tmp_path)}))
    pdir = tmp_path / "prompts"
    pdir.mkdir()
    (pdir / "icpFit.md").write_text("scoring")
    (pdir / "closing.md").write_text("le closing")
    cfg, prompts = config.load_config(str(cfg_path))
    assert "icpFit" in prompts and "closing" in prompts


def test_load_config_missing_icpFit_raises(tmp_path):
    cfg_path = tmp_path / "campaign.json"
    cfg_path.write_text(json.dumps({"campaign_id": "cam_1", "prompts_dir": "prompts",
                                    "state_dir": str(tmp_path)}))
    (tmp_path / "prompts").mkdir()  # pas d'icpFit.md
    with pytest.raises(SystemExit):
        config.load_config(str(cfg_path))


def test_register_campaign_writes_json_and_appends_registry(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text("[]")
    cj = tmp_path / "v" / "campaign.json"
    config.register_campaign(str(reg), str(cj), {"campaign_id": "cam_1", "slug": "agence-immo"},
                             {"slug": "agence-immo", "campaign_id": "cam_1", "status": "active"})
    assert json.loads(cj.read_text())["campaign_id"] == "cam_1"
    assert json.loads(reg.read_text())[0]["slug"] == "agence-immo"


def test_register_campaign_idempotent_updates_existing_slug(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps([{"slug": "agence-immo", "campaign_id": "old", "status": "paused"}]))
    cj = tmp_path / "campaign.json"
    config.register_campaign(str(reg), str(cj), {"campaign_id": "cam_2"},
                             {"slug": "agence-immo", "campaign_id": "cam_2", "status": "active"})
    entries = json.loads(reg.read_text())
    assert len(entries) == 1 and entries[0]["campaign_id"] == "cam_2" and entries[0]["status"] == "active"
