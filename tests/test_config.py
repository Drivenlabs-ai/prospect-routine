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


def test_load_config_missing_prompt_raises(tmp_path):
    cfg_path = _campaign(tmp_path, seq=("icebreaker",))
    # demande une étape dont le prompt n'existe pas
    import json as _j
    p = tmp_path / "campaign.json"
    data = _j.loads(p.read_text())
    data["sequence"] = ["icebreaker", "followup"]
    p.write_text(_j.dumps(data))
    with pytest.raises(SystemExit):
        config.load_config(cfg_path)
